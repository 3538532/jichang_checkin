# -*- coding: utf-8 -*-
"""机场自动签到（仅 Cookie 模式）

工作方式：把浏览器里已登录的 Cookie 放进仓库 Secret COOKIE，
直接 POST /user/checkin 完成签到，跳过账号密码登录和极验验证码。

需要的环境变量
  URL     机场地址，例如 https://cdn.linz.host（Secret URL）
  COOKIE  浏览器 Cookie 原始字符串（Secret COOKIE，必填）
  SCKEY   server酱 推送密钥（Secret SCKEY，可选）
"""

import json
import os
import sys

import requests

url = (os.environ.get('URL') or '').strip().rstrip('/')
COOKIE = (os.environ.get('COOKIE') or '').strip()
SCKEY = (os.environ.get('SCKEY') or '').strip()

check_url = '{}/user/checkin'.format(url)

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')


def snippet(text, n=300):
        """截取响应片段，便于在日志里定位问题"""
        return (text or '').strip()[:n]


def push(content):
        """通过 server酱 推送结果（未配置 SCKEY 时跳过）"""
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
        """解析签到响应：返回提示文案，异常时抛出可读错误"""
        text = (body or '').strip()
        if not text:
                raise RuntimeError('签到接口返回空内容')
        if text.startswith('<'):
                raise RuntimeError(
                        '签到接口返回 HTML（Cookie 已失效被跳转到登录页，或被站点拦截）：{}'.format(snippet(text))
                )
        try:
                data = json.loads(text)
        except Exception as ex:
                raise RuntimeError('签到响应不是合法 JSON（{}）：{}'.format(ex, snippet(text)))
        # 说明：重复签到时 ret=0 且 msg="您似乎已经签到过了..."，属正常状态，所以不按 ret 判失败。
        # 真正的失效信号是 302 跳转登录页或返回 HTML，上面已分别拦截。
        return data.get('msg') or data.get('message') or json.dumps(data, ensure_ascii=False)


def checkin():
        """用浏览器 Cookie 直接签到"""
        if not COOKIE:
                raise RuntimeError('未配置 Secret COOKIE（浏览器 Cookie），无法签到')
        headers = {
                'cookie': COOKIE,
                'user-agent': UA,
                'referer': '{}/user'.format(url),
                'origin': url,
                'accept': 'application/json, text/plain, */*',
                'x-requested-with': 'XMLHttpRequest',
        }
        res = requests.post(check_url, headers=headers, timeout=30, allow_redirects=False)
        print('签到接口 HTTP {} | content-type: {}'.format(
                res.status_code, res.headers.get('content-type')))
        if res.status_code in (301, 302, 303, 307, 308):
                raise RuntimeError(
                        '签到被重定向到 {}，说明 Cookie 已失效，请重新获取后更新 Secret COOKIE'.format(
                                res.headers.get('location'))
                )
        if res.status_code >= 400:
                raise RuntimeError('签到 HTTP {}：{}'.format(res.status_code, snippet(res.text)))
        return parse_checkin(res.text)


if __name__ == '__main__':
        if not url:
                print('缺少 URL 环境变量')
                push('缺少 URL 环境变量')
                sys.exit(1)

        try:
                msg = checkin()
        except Exception as ex:
                print('签到失败: {}'.format(ex))
                push('签到失败: {}'.format(ex))
                sys.exit(1)

        print(msg)
        push(msg)
        print('全部完成')
