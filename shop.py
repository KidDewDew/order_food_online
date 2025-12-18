import json
import os
import random
from logging import exception

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
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor(dictionary=True)
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
    except Exception as e:
        return e
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def shop_page(shop_id):
    # 需要判断一下这个店是不是属于这个用户
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM user_shop WHERE shop_id=%s", (shop_id,))
        r = cursor.fetchall()
        if len(r) == 0:
            return "<h1>这家店铺不存在哦</h1>",404
        shop_username = r[0][0]
        if shop_username == session.get("username",None):
            isShopper = True
        else: isShopper = False
        cursor.execute("SELECT shop_name,shop_position FROM shop WHERE shop_id=%s",(shop_id,))
        r = cursor.fetchall()
        if len(r) == 0:
            return "<h1>这家店铺不存在哦</h1>",404
        return render_template("shop.html",
                               shop_name=r[0][0],
                               shop_id=shop_id,
                               shop_position=r[0][1],
                               isShopper=isShopper)
    except Exception as e:
        return e
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 获取店铺最新的items列表
def get_shop_items(shop_id):
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT item.item_id,rest_num,price,item_name FROM shop_items INNER JOIN item "
                       "ON shop_items.item_id = item.item_id WHERE shop_id = %s",(shop_id,))
        return jsonify(cursor.fetchall()),200
    except mysql.connector.errors.Error as e:
        print(e)
        return jsonify({"errorMsg":""}),400
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def check_shop_belong(shop_id):
    username = session.get('username')
    r = db.do_query("SELECT shop_id FROM user_shop WHERE username=%s LIMIT 1",(username,))
    if len(r) == 0:
        return False
    return r[0][0] == shop_id

# 给店铺添加一个新餐品
def add_shop_item(shop_id):

    if not shared.check_logined_and_role("shopper"): #验证权限
        return "{\"errorMsg\":\"请登录\"}"

    item_name = request.form.get("item_name",None)
    price = request.form.get("price",None)
    images = request.files.getlist("images") # 餐品图片(集)
    try:
        # 检查该店铺是否存在以及是否属于该用户
        if not check_shop_belong(shop_id):
            return jsonify({"errorMsg":"异常操作"}),403
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO item (item_name,price) VALUES (%s,%s)",(item_name,price))
        item_id = cursor._last_insert_id
        cursor.execute("INSERT INTO shop_items (shop_id,item_id,rest_num) VALUES (%s,%s,0)",(shop_id,item_id))
        print("_last_insert_id =",item_id)

        # 记录这些图片
        for image in images:
            _,suffix = os.path.splitext(image.filename)
            image_url = "/static/image/item_image/"+shared.generate_random_id() + suffix
            # 这里直接假设不会出现名称冲突(因为概率极小，而且即使发生影响也不是很大)
            image.save('.'+image_url)
            # 记录
            cursor.execute("INSERT INTO item_images (item_id,image_url) VALUES (%s,%s)"
                           ,(item_id,image_url))
        conn.commit()
        return "{}",200
    except Exception as e:
        if conn: conn.rollback()
        print(e)
        return jsonify({"errorMsg":"数据库操作失败"}),500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 删除一个餐品
def delete_shop_item(shop_id):
    if not shared.check_logined_and_role("shopper"): #验证权限
        return "{\"errorMsg\":\"请登录\"}",400
    if not check_shop_belong(shop_id): #检查用户是否有shopper权限
        return jsonify({"errorMsg": "异常操作"}), 403

    # 检查是否有涉及该餐品并且尚未完成的订单
    # 如果有，则禁止删除，必须等待订单结束后才能删除餐品
    # to-do

    item_id = request.args.get("item_id",None)

    if not item_id:
        return "{\"errorMsg\":\"\"}",400

    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        # 注意，不会把item彻底删除，它仍存在于item表。但shop不再记录它
        cursor.execute("DELETE shop_")
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# 计算餐品的总价格
def calcItemsPrice(items):
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()  # 事务开始
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
    except Exception as e:
        raise e  # 抛出异常，防止错误计算价格
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


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
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def pay_order(shop_id):

    if not shared.check_logined_and_role("customer"): #只允许顾客用户下单
        return "{\"errorMsg\":\"请登录\"}",400

    # 获取点餐列表json
    order_content = request.form.get("order_items",None)

    if not order_content: return "{}",400

    order_items = json.loads(order_content)

    username = session.get('username',None)
    if not username:
        return jsonify({"errorMsg":""}),400

    # [!] 查询这位用户有没有历史订单，如果有，这次创建订单和上次创建订单的时间间隔至少大于 > 20s.

    r = db.do_query("SELECT create_time FROM alipay_trade WHERE username = %s ORDER BY create_time DESC LIMIT 1",
                   (username,))
    #if r == None or len(r) > 0: // to-do

    # [!] 验证order_items，如果验证通过，则减去库存。
    if not verify_order_items_then_sub(shop_id,order_items):
        return jsonify({"errorMsg":"点餐失败，可能是您点的餐品刚刚被卖完了"}),400

    # 验证成功，开始创建alipay付款url，并记录本交易中的订单
    total_amount = calcItemsPrice(order_items)

    # 获取支付url和商品编号
    pay_url,out_trade_no = pay.create_alipay_order_url("点餐订单",100.0,"")
    # 记录交易
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alipay_trade (username,pay_url,out_trade_no,total_amount,order_content) "
                       "VALUES (%s,%s,%s,%s,%s)",(username,pay_url,out_trade_no,total_amount,order_content))
        conn.commit()
        return jsonify({"pay_url":pay_url}),200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"errorMsg":""}),400
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

