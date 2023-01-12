from base import *
from send_msg import send_msg
from base import ocr

# new crawler
class crawler:
    in_school = True
    headers = {"User-Agent":'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'}
    webvpn = 'https://webvpn.bupt.edu.cn'
    session = requests.session()
    login_code = 401
    redirect = {}
    service = {
        'my':'http://my.bupt.edu.cn/system/resource/code/auth/clogin.jsp?owner=1664271694'
    }
    redis = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)
    
    url = {'my':''}
    
    info_dest={
        'notice':{
            'url':'list.jsp?{}urltype=tree.TreeTempUrl&wbtreeid=1154',
            'tag':'【校内通知】',
            'redis':'bupt_notice'
        },
        'ncov':{
            'url':'list.jsp?{}urltype=tree.TreeTempUrl&wbtreeid=2012',
            'tag':'【防控通知】',
            'redis':'bupt_ncov'
        },
        'public':{
            'url':'list.jsp?{}urltype=tree.TreeTempUrl&wbtreeid=1305',
            'tag':'【公示公告】',
            'redis':'bupt_public'
        }
    }

# initialize
    def __init__(self, in_school = True):
        self.in_school = in_school

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
                'username' : self.redis.get('bupt_user_name'),
                'sms_code' : '',
                'password' : self.redis.get('bupt_user_pwd'),
                'captcha'   : '',
                'needCaptcha' : 'false',
                'captcha_id' : captcha_id
            }
            response = self.post(self.webvpn+'/do-login',data = data)
            logging.info('login to webvpn return %d',response.status_code)
            if response.status_code != 200:
                return None
        except Exception:
            pass
        
        # get redirect infomation
        cur_time = int(round(time.time() * 1000))
        response = self.get(self.webvpn + '/user/portal_groups',{'_t':cur_time})
        try:
            for item in json.loads(response.text)['data'][0]['resource']:
                self.redirect[item['detail'].split('.')[0]] = item['redirect']
            # print(self.redirect)
        except Exception:
            # print(response.text)
            return None
        
        # get login url
        response = self.get(self.webvpn + self.redirect['my'])
        return response.url[:response.url.find('?')]
        
# login authentication  
    def login(self):
        login_url = 'https://auth.bupt.edu.cn/authserver/login'
        
        # check webvpn
        if not self.in_school:
            login_url = self.login_webvpn()
        if login_url == None:
            return 401
        status_code = 401

        response = self.get(login_url,{'service':self.service['my']})
        doc = BS(response.text,features='lxml')
        execution = doc.select('input[name="execution"]')[0].attrs.get('value')

        # construct login data
        data = {
            'username': self.redis.get('bupt_user_name'),
            'password': self.redis.get('bupt_user_pwd'),
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
        logging.info('authenticate return %d',status_code)
        if status_code == 200:
            self.url['my'] = self.webvpn + self.redirect['my'] if not self.in_school else 'http://my.bupt.edu.cn/'

        self.login_code = status_code
        return status_code

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
        # with open('./code.png','wb')as fp:
        #     fp.write(img_data)
        
        # call ocr
        res = ocr.classification(img_data).replace('l','1')
        logging.info('decode: %s',res)
        return res

# check login status
    def login_check(self):
        if self.login_code != 200:
            logging.error('not logged in')
            # send_msg(type='private',to=self.redis.get('qbot_root'),msg='athentication failed.')
            exit()
   
# catch news list         

    def catch(self):
        self.login_check()
        
        # catch notice, ncov and publish 
        for key in self.info_dest:
            get_new = 0
            try:
                node = self.info_dest[key]
                tag = node['tag']
                redis_key = node['redis']
                sec_url = node['url']
                
                # catch list
                logging.info('catching infomation of type [%s]...',key)
                response = self.get(self.url['my'] + sec_url.format(''))
                response = self.get(self.url['my'] + sec_url.format(''))
                doc = BS(response.text,features='lxml')
                
                # get total page
                page_url = doc.find(class_='p_no').find('a').attrs.get('href')
                page_node = page_url[page_url.find('total'):page_url.find('&',page_url.find('&')+1)-1]
                
                score = 0
                for i in range(1,3 if type == 'notice' else 2):
                    response = self.get(self.url['my'] + sec_url.format(page_node + str(i) + '&'))
                    doc = BS(response.text,features='lxml')
                    for ele in doc.select('.newslist > li'):
                        score = score + 1
                        # get link to details
                        href = ele.find('a').attrs.get('href')
                        
                        # get id, title, time
                        id = str(href[href.find('wbnewsid=')+9:])
                        title = ele.find('a').attrs.get('title')
                        # time_ = int(time.time())
                        time_ = int(time.mktime(time.strptime(ele.find(class_='time').text,'%Y-%m-%d')))
                        
                        # check and insert
                        pre = self.redis.zcard(redis_key)
                        self.redis.zadd(redis_key,mapping={id:score})
                        cur = self.redis.zcard(redis_key)
                        
                        # new item added
                        if cur > pre:
                            # print
                            brief = 'id:{} time:{} title:{}'.format(id,time_,title)
                            print(brief)
                            
                            # new count added
                            get_new = get_new + 1
                            
                            # filter
                            if key == 'public' and title.find('外协事项公示') >= 0 :
                                pass
                            else:
                                # get detail
                                detail = '{}[id={}]\n{}'.format(tag,id,self.get_detail(href))
                            
                                # send message
                                res = send_msg(type='group',to='926797189',msg=detail)
                                if res != None:
                                    self.push(msg='exception: \n' + str(res))
                                else:
                                    time.sleep(0.5)
                                    send_msg(type='private',to='1015620755',msg=detail)            
                                    time.sleep(1)

                                self.push(msg=brief)
                            
                        if cur > 100:
                            # pop cache
                            self.redis.zpopmax(redis_key,count = cur - 100)

                
                logging.info('news of type [%s] update : %d',key,get_new)
                
            except Exception as exp:
                logging.error('catching abort caused by:\n %s',str(exp))
                res = send_msg(type='private',to=self.redis.get('qbot_root'),msg='exception: \n'+str(exp))
                if res != None:
                    self.push(msg='exception: ' + str(exp))
                return
            
        logging.info('all done.')

# get article details        
    def get_detail(self,sec_url):
        self.login_check()

        response = self.get(self.url['my']+sec_url)
        doc = BS(response.text,features='lxml',from_encoding='utf-8')
        
        # get article node
        node = doc.find('div',class_='singlemainbox').find('form').find('div')
        
        # print(node)
        # get title, post and content
        title = node.find('h1').text
        post = node.find('span',class_='pdept').text
        content = node.find('div',class_='singleinfo').text
        
        return '[' + title + ']\n' + post + '\n' + content
    
    def push(self,key=None, msg=None):
        if key == None:
            key=self.redis.get('pushdeer_root')
        if len(key) == 0 or msg == None:
            logging.warn('incomplete arguments.')
            return
        
        try:
            pushdeer = PushDeer(pushkey=key)
            pushdeer.send_text('[BUPT_Daily] ' + msg)
            logging.info('msg push success')
        except Exception as e:
            logging.warn(e)
    
        
        
        

    

        
    