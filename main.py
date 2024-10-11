import requests, json, re, os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()
session = requests.session()
# 机场的地址
url = os.getenv('URL')
# 配置用户名（一般是邮箱）
email = os.getenv('EMAIL')
# 配置用户名对应的密码 和上面的email对应上
passwd = os.getenv('PASSWD')
# server酱
SCKEY = os.getenv('SCKEY')

login_url = '{}/auth/login'.format(url)
check_url = '{}/user/checkin'.format(url)
info_url='{}/user/profile'.format(url)

header = {
        'origin': url,
        'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
}
data = {
        'email': email,
        'passwd': passwd
}

try:
    print('进行登录...'+str(header)+str(data))
    response = json.loads(session.post(url=login_url,headers=header,data=data).text)
    print(response['msg'])

    # 获取账号名称
    info_html = session.get(url=info_url, headers=header).text
        
    # 进行签到
    result = json.loads(session.post(url=check_url,headers=header).text)
    print(result['msg'])
    content = result['msg']
    # 进行推送
    if SCKEY != '':
        push_url = 'https://sctapi.ftqq.com/{}.send?title=机场签到&desp={}'.format(SCKEY, content)
        requests.post(url=push_url)
        print('推送成功')
except:
    content = '签到失败'
    print(content)
    if SCKEY != '':
        push_url = 'https://sctapi.ftqq.com/{}.send?title=机场签到&desp={}'.format(SCKEY, content)
        requests.post(url=push_url)
