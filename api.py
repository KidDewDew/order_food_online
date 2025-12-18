import shared
from flask import (make_response,session)
from captcha.image import ImageCaptcha  #验证码生成

import db

# 在这里添加url_rule到app
def add_url_rules(app):
    app.add_url_rule("/api/get_verify_code", view_func=api_get_verify_code)
    app.add_url_rule("/api/get_item_cover/<item_id>", view_func=get_item_cover)

def api_get_verify_code():
    codes = shared.generate_random_codes(4,shared.RANDOM_STR_vc)
    session['verify_code'] = codes
    image = ImageCaptcha()
    verify_code_image = image.generate(chars=codes)
    response = make_response(verify_code_image.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

def get_item_cover(item_id):
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT image_url FROM item_images LIMIT 1 WHERE item_id=%s",(item_id,))
        r = cursor.fetchall()
        if len(r) == 0:
            return "",404
        return r[0][0],200
    except Exception as e:
        return "",404
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
