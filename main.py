import requests, json, os, time, sys
from geeked import Geeked

# 机场的地址
url = os.environ.get('URL')
# 配置用户名（一般是邮箱）
config = os.environ.get('CONFIG')
# server酱
SCKEY = os.environ.get('SCKEY') or ''
# 浏览器 Cookie：推荐模式，跳过账号密码与验证码，不受验证码风控影响
COOKIE = (os.environ.get('COOKIE') or '').strip()

# GeeTest V4 验证码 ID（从 ikuuu.org 提取）
CAPTCHA_ID = 'cc96d05ba8b60f9112f76e18526fcb73'

login_url = '{}/auth/login'.format(url)
check_url = '{}/user/checkin'.format(url)

MAX_RETRIES = 3
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'


def snippet(text, n=300):
        """截取响应片段，便于在日志里定位问题"""
        text = (text or '').strip()
        return text[:n]


def push(content):
        """通过 server酱 推送结果"""
        if not SCKEY:
                return
        try:
                requests.post(
                        'https://sctapi.ftqq.com/{}.send'.format(SCKEY),
                        params={'title': '机场签到', 'desp': content},
                        timeout=20,
                )
                print('推送成功')
        except Exception as ex:
                print('推送失败: {}'.format(ex))


def parse_checkin(body):
        """解析签到响应：成功返回 msg，失败抛异常"""
        text = (body or '').strip()
        if not text:
                raise RuntimeError('签到接口返回空内容')
        if text.startswith('<'):
                raise RuntimeError('签到接口返回 HTML（Cookie 失效被跳转到登录页，或被站点拦截）：{}'.format(snippet(text)))
        try:
                data = json.loads(text)
        except Exception as ex:
                raise RuntimeError('签到响应不是合法 JSON（{}）：{}'.format(ex, snippet(text)))
        return data.get('msg') or data.get('message') or json.dumps(data, ensure_ascii=False)


def checkin_with_cookie():
        """用浏览器 Cookie 直接签到，跳过登录与验证码"""
        headers = {
                'cookie': COOKIE,
                'user-agent': UA,
                'referer': '{}/user'.format(url),
                'origin': url,
                'accept': 'application/json, text/plain, */*',
                'x-requested-with': 'XMLHttpRequest',
        }
        res = requests.post(check_url, headers=headers, timeout=30, allow_redirects=False)
        print('签到接口 HTTP {} | content-type: {}'.format(res.status_code, res.headers.get('content-type')))
        if res.status_code in (301, 302, 303, 307, 308):
                raise RuntimeError('签到被重定向到 {}，说明 Cookie 已失效，请重新获取后更新 COOKIE'.format(res.headers.get('location')))
        if res.status_code >= 400:
                raise RuntimeError('签到 HTTP {}：{}'.format(res.status_code, snippet(res.text)))
        return parse_checkin(res.text)


def diagnose_captcha():
        """验证码服务诊断：打印 /load 原始响应，用于判断是 IP 风控还是接口变化"""
        try:
                import uuid
                callback = 'geetest_{}'.format(int(time.time() * 1000))
                params = {
                        'captcha_id': CAPTCHA_ID,
                        'challenge': str(uuid.uuid4()),
                        'client_type': 'web',
                        'risk_type': 'ai',
                        'lang': 'eng',
                        'callback': callback,
                }
                headers = {'user-agent': UA, 'referer': url or '', 'origin': url or ''}
                res = requests.get('https://gcaptcha4.geevisit.com/load', params=params, headers=headers, timeout=20)
                print('[诊断] GeeTest /load HTTP {}，响应长度 {}'.format(res.status_code, len(res.text)))
                print('[诊断] 响应片段: {}'.format(snippet(res.text, 500)))
                if '"data"' not in res.text:
                        print('[诊断] 响应中没有 data 字段 —— 通常是机房 IP 被 GeeTest 风控/拒绝，建议改用 COOKIE 模式')
        except Exception as ex:
                print('[诊断] 诊断请求本身失败: {}'.format(ex))


def solve_captcha():
        """使用 GeekedTest 求解 GeeTest V4 验证码（纯 Python，无需浏览器），支持重试"""
        for attempt in range(1, MAX_RETRIES + 1):
                try:
                        print('验证码求解尝试 {}/{}...'.format(attempt, MAX_RETRIES))
                        geeked = Geeked(CAPTCHA_ID, 'ai')
                        result = geeked.solve()
                        print('验证码求解成功')
                        return result
                except Exception as ex:
                        print('验证码求解失败 (尝试 {}/{}): {}'.format(attempt, MAX_RETRIES, ex))
                        if attempt < MAX_RETRIES:
                                print('等待 2 秒后重试...')
                                time.sleep(2)
        print('所有重试均失败')
        diagnose_captcha()
        return None


def sign(order, user, pwd):
        """账号密码 + 验证码登录后签到（验证码不可用时请改用 COOKIE 模式）"""
        session = requests.session()
        header = {
                'origin': url,
                'user-agent': UA,
        }
        print('===账号{}进行登录...==='.format(order))
        print('账号：{}'.format(user))

        captcha = solve_captcha()
        if captcha is None:
                print('验证码求解失败，跳过此账号')
                return False

        data = {
                'email': user,
                'passwd': pwd,
                'captcha_result[lot_number]': captcha['lot_number'],
                'captcha_result[captcha_output]': captcha['captcha_output'],
                'captcha_result[pass_token]': captcha['pass_token'],
                'captcha_result[gen_time]': captcha['gen_time'],
        }
        try:
                res = session.post(url=login_url, headers=header, data=data, timeout=30, allow_redirects=False)
                print('登录接口 HTTP {}'.format(res.status_code))
                response = json.loads(res.text)
                print(response.get('msg'))
                if response.get('ret') != 1:
                        print('登录失败: {}'.format(response.get('msg')))
                        push('登录失败: {}'.format(response.get('msg')))
                        return False

                res2 = session.post(url=check_url, headers=header, timeout=30, allow_redirects=False)
                msg = parse_checkin(res2.text)
                print(msg)
                push(msg)
                return True
        except Exception as ex:
                print('签到失败: {}'.format(ex))
                push('签到失败: {}'.format(ex))
                return False
        finally:
                print('===账号{}签到结束===\n'.format(order))


if __name__ == '__main__':
        if not url:
                print('缺少 URL 环境变量')
                push('缺少 URL 环境变量')
                sys.exit(1)

        results = []

        if COOKIE:
                print('===COOKIE 模式：跳过账号密码与验证码===')
                try:
                        msg = checkin_with_cookie()
                        print(msg)
                        push(msg)
                        results.append(True)
                except Exception as ex:
                        print('签到失败: {}'.format(ex))
                        push('签到失败: {}'.format(ex))
                        results.append(False)
        else:
                print('===账号密码模式（需要求解验证码）===')
                if not config:
                        print('缺少 CONFIG 环境变量（账号密码），也没有设置 COOKIE')
                        push('缺少配置')
                        sys.exit(1)
                configs = [line for line in config.splitlines() if line.strip()]
                if len(configs) % 2 != 0 or len(configs) == 0:
                        print('配置文件格式错误（每两行为一组：邮箱、密码）')
                        push('配置文件格式错误')
                        sys.exit(1)
                user_quantity = len(configs) // 2
                for i in range(user_quantity):
                        results.append(sign(i, configs[i * 2], configs[i * 2 + 1]))

        if not any(results):
                print('所有账号签到失败')
                sys.exit(1)

        print('全部完成')
