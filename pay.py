import random
from datetime import datetime

import shared
import db
from flask import (make_response, session, render_template, request)

#?WIDout_trade_no=1000&WIDsubject=%E7%83%A4%E8%98%91%E8%8F%87&WIDtotal_amount=112&WIDbody=%E6%AF%8F%E4%BD%8D%E7%9A%84

# 在这里添加url_rule到app
def add_url_rules(app):
    app.add_url_rule("/pay/alipay_return", view_func=alipay_return)
    app.add_url_rule("/pay/alipay_notify", view_func=alipay_notify)


def create_alipay_order_url(subject,total_amount,describe):
    out_trade_no = shared.generate_random_id()
    # 由于Alipay给python的接口文档太少了，所以这里构建的付款url是指向tomcat 8080端口的
    url = (f"http://47.120.51.172:8080/alipay-wappay/wappay/pay.jsp?"
           f"WIDout_trade_no={out_trade_no}"
           f"&WIDsubject={subject}"
           f"&WIDtotal_amount={total_amount}"
           f"&WIDbody={describe}")
    return url,out_trade_no

def alipay_return():
    pass

def alipay_notify():
    pass

