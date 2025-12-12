import shared
from flask import (make_response,session)
from captcha.image import ImageCaptcha  #验证码生成

# 在这里添加url_rule到app
def add_url_rules(app):
    app.add_url_rule("/api/get_verify_code", view_func=api_get_verify_code)

def api_get_verify_code():
    codes = shared.generate_random_codes(4,shared.RANDOM_STR_vc)
    session['verify_code'] = codes
    image = ImageCaptcha()
    verify_code_image = image.generate(chars=codes)
    response = make_response(verify_code_image.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response