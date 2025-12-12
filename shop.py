import json
import os
import random

import mysql.connector.errors

import shared
import db
from flask import (make_response, session, render_template, redirect, request, jsonify)

import pay

# 在这里添加url_rule到app
def add_url_rules(app):
    app.add_url_rule("/shoplist", view_func=shoplist_page)
    app.add_url_rule("/shop/<int:shop_id>", view_func=shop_page)
    app.add_url_rule("/shop/<int:shop_id>/create_pay",view_func=pay_order)
    app.add_url_rule("/shop/<int:shop_id>/get_items",view_func=get_shop_items)
    app.add_url_rule("/shop/<int:shop_id>/add_item", view_func=add_shop_item, methods=["POST"])

def shoplist_page():
    cursor = db.get_cursor(dictionary=True)
    cursor.execute(f"SELECT shop_id,shop_name,shop_position FROM shop")
    shoplist = cursor.fetchall()
    for i in range(20):
        shoplist.append({
            "shop_id":i,
            "shop_name":"苏大烧烤店",
            "shop_position":"苏州大学本部校区食堂门口",
            "status":random.randint(0,1)
        })
    return render_template("shoplist.html",
                           normal_status=shared.ShopStatus_Normal,reserve_status=shared.ShopStatus_Reserve,
                           shoplist=shoplist)

def shop_page(shop_id):
    cursor = db.get_cursor()
    cursor.execute("SELECT shop_name,shop_position FROM shop WHERE shop_id=%s",(shop_id,))
    r = cursor.fetchall()
    cursor.close()
    if len(r) == 0:
        return "<h1>这家店铺不存在哦</h1>",404
    return render_template("shop.html",shop_name=r[0][0],shop_position=r[0][1])

# 获取店铺最新的items列表
def get_shop_items(shop_id):
    try:
        cursor = db.get_cursor(dictionary=True)
        cursor.execute("SELECT item_id,rest_num,price,item_name FROM shop_items INNER JOIN item "
                       "ON shop_items.item_id = item.item_id WHERE shop_id = %s",(shop_id,))
        return jsonify(cursor.fetchall()),200
    except mysql.connector.errors.Error as e:
        return jsonify({"errorMsg":""}),400
    finally:
        cursor.close()

def check_shop_belong(shop_id):
    cursor = db.get_cursor()
    username = session.get('username')
    cursor.execute("SELECT shop_id FROM user_shop WHERE username=%s LIMIT 1",(username,))
    r = cursor.fetchall()
    cursor.close()
    if len(r) == 0:
        return False
    return r[0][0] == shop_id

# 给店铺添加一个新餐品
def add_shop_item(shop_id):
    item_name = request.form.get("item_name",None)
    price = request.form.get("price",None)
    images = request.files.getlist("images") # 餐品图片(集)
    try:
        # 检查该店铺是否存在以及是否属于该用户
        if not check_shop_belong(shop_id):
            return jsonify({"errorMsg":"异常操作"}),403
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT shop_id FROM shop")
        cursor.execute("INSERT INTO item (item_name,price) VALUES (%s,%s)",(item_name,price))
        item_id = cursor._last_insert_id
        cursor.execute("INSERT INTO shop_items (shop_id,item_id,rest_num) VALUES (%s,%s,0)",(shop_id,item_id))
        print("_last_insert_id =",item_id)

        # 记录这些图片
        for image in images:
            _,suffix = os.path.splitext(image.filename)
            image_url = "/static/image/item_image/"+shared.generate_random_id() + suffix
            # 这里直接假设不会出现名称冲突(因为概率非常小，而且即使发生影响也不是很大)
            image.save(image_url)
        conn.commit()
    except mysql.connector.errors.Error as e:
        conn.rollback()
    finally:
        cursor.close()

# 计算餐品的总价格
def calcItemsPrice(items):
    cursor = db.get_cursor()  # 事务开始
    total_amount = 0.0
    for item in items:
        cursor.execute("SELECT price FROM item WHERE item_id=%s",(item['item_id'],))
        r = cursor.fetchall()
        if len(r) != 1:
            cursor.close()
            return -1.0
        price = r[0][0]
        total_amount += price * item['num']
    cursor.close()
    return total_amount


# 验证订单餐品，如果验证通过，则从数据库减去它们
# items: json数组
def verify_order_items_then_sub(shop_id,items):
    # 验证每个item是否属于该shop，且剩余数量是否足够
    # 查询该店铺的餐品列表

    if len(items) == 0:
        return False

    for item in items:
        if item["num"] <= 0:
            return False

    conn = db.get_db_connection()
    cursor = conn.cursor() #事务开始
    try:
        # 注：shop_id是该表的一个单索引，查询速度很快。
        # FOR UPDATE: 悲观锁，锁定该行，禁止其他连接对该行进行读写。
        placeholders = ','.join(['%s'] * len(items))
        # 只锁定本订单涉及到的餐品
        cursor.execute(f"SELECT item_id,rest_num FROM shop_items WHERE shop_id = %s"
                       f" AND item_id IN ({placeholders}) FOR UPDATE",[shop_id]+[item["item_id"] for item in items])
        itemlist = cursor.fetchall()

        # 如果查询到的item数量!=items数量，大概率意味着item_id不存在于该商铺
        if len(itemlist) == 0 or len(itemlist) != len(items):
            conn.rollback()
            return False

        itemdict = {}
        for item in itemlist:
            itemdict[item[0]] = item[1]
        for item in items:
            item_id = item["item_id"]
            if item_id not in itemdict:
                conn.rollback()
                return False #验证失败，无效item_id，它不属于这个店铺！
            if item["num"] > itemdict[item_id]:
                conn.rollback()
                return False #验证失败，商铺的该item数量不够了。

        # 验证通过，立即更新数据库
        for item in items:
            item_id = item["item_id"]
            sub_num = item["num"]
            cursor.execute("UPDATE shop_items SET rest_num = rest_num-%s WHERE shop_id=%s AND item_id=%s",
                                (sub_num,shop_id,item_id))

        conn.commit() #提交事务,释放独占锁
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        cursor.close()

def pay_order(shop_id):
    # 获取点餐列表json
    order_content = request.form.get("order_items",None)

    if not order_content: return "{}",400

    order_items = json.loads(order_content)

    username = session.get('username',None)
    if not username:
        return jsonify({"errorMsg":""}),400

    # [!] 查询这位用户有没有历史订单，如果有，这次创建订单和上次创建订单的时间间隔至少大于 > 20s.
    cursor = db.get_cursor()
    cursor.execute("SELECT create_time FROM alipay_trade WHERE username = %s ORDER BY create_time DESC LIMIT 1",
                   (username,))
    cursor.fetchall()
    cursor.close()

    # [!] 验证order_items，如果验证通过，则减去库存。
    if not verify_order_items_then_sub(shop_id,order_items):
        return jsonify({"errorMsg":"点餐失败，可能是您点的餐品刚刚被卖完了"}),400

    # 验证成功，开始创建alipay付款url，并记录本交易中的订单
    total_amount = calcItemsPrice(order_items)

    # 获取支付url和商品编号
    pay_url,out_trade_no = pay.create_alipay_order_url("点餐订单",100.0,"")
    # 记录交易
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO alipay_trade (username,pay_url,out_trade_no,total_amount,order_content) "
                   "VALUES (%s,%s,%s,%s,%s)",(username,pay_url,out_trade_no,total_amount,order_content))
    cursor.close()
    conn.commit()
    return jsonify({"pay_url":pay_url}),200

