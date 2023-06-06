import nonebot
from nonebot import get_driver
from nonebot import get_bot
from nonebot import require
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import Arg, CommandArg, ArgPlainText
from pydantic import BaseModel, Extra
import requests
import time
import json
import re
import ddddocr
from bs4 import BeautifulSoup as BS
import pymysql

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

ocr = ddddocr.DdddOcr(show_ad=False)

class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""
    bupt_news_send_hour: str
    bupt_news_send_minute: str
    bupt_news_send_private: list
    bupt_news_send_group: list
    bupt_news_filter: list
    bupt_news_sql_host: str
    bupt_news_sql_user: str
    bupt_news_sql_pwd: str
    bupt_student_user: str
    bupt_student_pwd: str

global_config = get_driver().config
config = Config.parse_obj(global_config)

class webview:
    config : Config
    headers = {"User-Agent":'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'}
    webvpn = 'https://webvpn.bupt.edu.cn'
    session = requests.session()
    login_code = 401
    redirect = {}
    service = {'my':'http://my.bupt.edu.cn/system/resource/code/auth/clogin.jsp?owner=1664271694'}
    url = {'my':''}

    def __init__(self,conf:Config):
        self.config = conf

# encap get method
    def get(self,url,params = None):
        return self.session.get(url=url, headers=self.headers, params=params)

# encap post method
    def post(self,url,data = None):
        return self.session.post(url=url, headers=self.headers, data=data)
    
# login to webvpn
    def login_webvpn(self):
        response = self.get(self.webvpn + '/login')
        doc = BS(response.text,features='lxml')
        try:
            captcha_id = doc.select('input[name="captcha_id"]')[0].attrs.get('value')
            data = {
                'auth_type':'local',
                'username' : self.config.bupt_student_user,
                'sms_code' : '',
                'password' : self.config.bupt_student_pwd,
                'captcha'   : '',
                'needCaptcha' : 'false',
                'captcha_id' : captcha_id
            }
            response = self.post(self.webvpn+'/do-login',data = data)
            nonebot.logger.info(f'login to webvpn return {response.status_code}')
            if response.status_code != 200:
                return None
        except Exception as e:
            nonebot.logger.error(str(e))
            pass
        
        # get redirect infomation
        cur_time = int(round(time.time() * 1000))
        response = self.get(self.webvpn + '/user/portal_groups',{'_t':cur_time})
        try:
            for item in json.loads(response.text)['data'][0]['resource']:
                self.redirect[item['detail'].split('.')[0]] = item['redirect']
        except Exception:
            return None
        
        # get login url
        response = self.get(self.webvpn + self.redirect['my'])
        return response.url[:response.url.find('?')]
        
# login authentication  
    def login(self):
        login_url = 'https://auth.bupt.edu.cn/authserver/login'
        
        # check webvpn
        login_url = self.login_webvpn()
        if login_url == None:   return 401
        status_code = 401

        try:
            response = self.get(login_url,{'service':self.service['my']})
            doc = BS(response.text,features='lxml')
            execution = doc.select('input[name="execution"]')[0].attrs.get('value')

            # construct login data
            data = {
                'username': self.config.bupt_student_user,
                'password': self.config.bupt_student_pwd,
                'submit': "登录",
                'type': 'username_password',
                'execution': execution,
                '_eventId': "submit"
            }
            
            # verify code
            code = self.decode(login_url[:login_url.find('/login')],doc.find_all('script'))
            if code != '':
                data['captcha'] = code
            
            response = self.post(login_url,data)

            status_code = response.status_code
            nonebot.logger.info(f'authenticate return {status_code}')
            if status_code == 200:
                self.url['my'] = self.webvpn + self.redirect['my']

            self.login_code = status_code
            return status_code

        except Exception as e:
            print(e)
            self.login_code = 401
            return 401

# decode verify code picture
    def decode(self,base,js_list):
        capt = ''
        for ele in js_list:
            if ele.text.find('captchaUrl()') != -1:
                capt = ele.text
                break
        if capt == '':
            return

        # get verify code id
        id = re.findall('id: \'[0-9]*\'', capt)[0].replace('\'','')
        id = id[id.find(': ') + 2:]
        
        # get image data stream
        img_data = self.get(base + '/captcha?captchaId=' + id).content
        
        # call ocr
        res = ocr.classification(img_data).replace('l','1')
        return res

# check login status
    def login_check(self):
        if self.login_code != 200:
            nonebot.logger.error('not logged in')
            return False
        return True

# get article details        
    def get_detail(self,sec_url):
        if not self.login_check(): return ''

        response = self.get(self.url['my']+sec_url)
        doc = BS(response.text,features='lxml',from_encoding='utf-8')
        
        # get article node
        node = doc.find('div',class_='singlemainbox').find('form').find('div')
        
        # print(node)
        # get title, post and content
        title = node.find('h1').text
        post = node.find('span',class_='pdept').text
        content = node.find('div',class_='singleinfo').text
        
        return title + post + content

class DataBase:
    db = None
    cursor = None

    def connect_mysql(self,config:Config):
        try:
            self.db = pymysql.connect(
                host=config.bupt_news_sql_host,
                port=3306,
                user=config.bupt_news_sql_user,
                passwd=config.bupt_news_sql_pwd,
                database='azure_server_data',
                charset='utf8'
            )
            self.cursor = self.db.cursor(pymysql.cursors.DictCursor)
            nonebot.logger.info('Connect to MySQL success')

        except Exception as e:
            nonebot.logger.error(f"Connect to MySQL failed. Exception: {str(e)}")

    def get_unsend(self):
        if self.db == None:
            return []

        sql = '''select news_id,title,author from bupt_daily_news
                where send=0 order by time desc;'''
        try:
            self.cursor.execute(sql)
            self.db.commit()
            return self.cursor.fetchall()

        except Exception as e:
            nonebot.logger.error(str(e))
            return []

    def get_news_list(self,number = 10, type_='notice'):
        if self.db == None:
            return None

        cond = f'where type="{type_}"' if type_ != 'all' else ''
        sql = f'select news_id,title,author from bupt_daily_news_latest {cond} limit {number};'
        try:
            self.cursor.execute(sql)
            self.db.commit()
            return self.cursor.fetchall()

        except Exception as e:
            nonebot.logger.error(str(e))
            return []

    def get_news_url(self,news_id):
        if self.db == None:
            return None

        sql = f'select url from bupt_daily_news_latest where news_id = {news_id};'
        try:
            self.cursor.execute(sql)
            self.db.commit()
            return self.cursor.fetchall()

        except Exception as e:
            nonebot.logger.error(str(e))
            return []

    def update_news_status(self,news_id):
        if self.db == None:
            return None

        sql = f'update bupt_daily_news set send=1 where news_id={news_id};'
        try:
            self.cursor.execute(sql)
            self.db.commit()
            return True

        except Exception as e:
            nonebot.logger.error(str(e))
            return False

db = DataBase()
db.connect_mysql(config)

@scheduler.scheduled_job("cron",hour=config.bupt_news_send_hour,minute=config.bupt_news_send_minute, id="bupt_news_report")
async def get_lastest_news():
    bot = get_bot()

    unsend_list = db.get_unsend()
    if len(unsend_list) == 0:
        return

    response = ''
    for x in unsend_list:
        flag = True
        for y in config.bupt_news_filter: 
            if y in x["title"]:
                flag = False
                break
        if flag:
            response += f'{x["news_id"]}:[{x["author"]}] {x["title"]}\n'
    if len(response) > 0:
        for id in config.bupt_news_send_private:
            await bot.send_private_msg(user_id=id,message=response)
        for id in config.bupt_news_send_group:
            await bot.send_group_msg(group_id=id,message=response)
    
    for item in unsend_list:
        db.update_news_status(item['news_id'])


latest = on_command("latest", rule=to_me(), aliases={"最新通知"},priority=5)

@latest.handle()
async def handle_latest(matcher: Matcher, args: Message=CommandArg()):
    arg = args.extract_plain_text().strip()
    num = 1
    news_type = 'notice'
    if arg != '': 
        arg = arg.split()
        try:
            num = int(arg[0])
        except Exception:
            await latest.reject("参数1不对哦, 请填写查询数量")
        
        if len(arg) >= 2:
            if arg[1] == '通知':    news_type = 'notice'
            elif arg[1] == '公告':  news_type = 'public'
            elif arg[1] == '全部':  news_type = 'all'
            else: await latest.reject("参数2不对哦, 请填写查询类型(通知/公告/全部)")

    if num > 30:
        await latest.reject("参数不对哦, 查询数量不能超过30")

    news_list = db.get_news_list(number=num,type_=news_type)
    msg = '【{}】{}[{}]:{}\n'
    response = ''
    for no_ in range(0,len(news_list)):
        x = news_list[no_]
        response += msg.format(no_+1,x['news_id'],x['author'],x['title'])

    await latest.finish(response if response != '' else None)


detail = on_command("detail",rule=to_me(), aliases={"详情","详细"},priority=5)

@detail.handle()
async def handle_first_command(matcher:Matcher, args: Message=CommandArg()):
    arg = args.extract_plain_text().strip()
    if arg != '':
        matcher.set_arg("news_id",args)

@detail.got("news_id", prompt="请输入查询id:")
async def handle_detail(news_id:Message=Arg(), news_id_str: str = ArgPlainText("news_id")):
    url_res = db.get_news_url(news_id=news_id_str)
    if len(url_res) == 0:
        await detail.reject(f"没有id为'{news_id}'的记录")
    else:
        url = url_res[0]['url']
        wv = webview(config)
        for i in range(0,3):
            if wv.login() == 200:
                break
            wv = webview(config)   # update crawler
            nonebot.logger.warning('log in failed. retrying in 5 sec...') # retry
            time.sleep(3)
        
        msg = wv.get_detail(url)
        try:
            await detail.finish(msg if msg != '' else '信息门户登录异常 :(')
        except Exception:
            await detail.finish('bot大概被风控惹 :(')
        
        
        

    

        
    
