import time

from func import *
from config import *
"""
   再config.py文件中输入谷歌验证器密钥，测试得出的结果跟你绑定 的验证码是否相同
"""

while True:
    get_google_code(secret,True)
    time.sleep(5)