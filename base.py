import logging
import requests
import execjs
from bs4 import BeautifulSoup as BS
import time
import json
import ddddocr
import redis
import re
from pypushdeer import PushDeer
ocr = ddddocr.DdddOcr(show_ad=False)

# 设置debug等级
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s')


def encodeInp(input):
    with open('./encodeInp.js',encoding='utf-8') as f:
        js = execjs.compile(f.read())
        return js.call('encodeInp',input)


