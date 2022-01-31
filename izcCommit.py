import datetime
import os
import re
import time

import pymysql
import configparser
import requests
from requests import utils
from urllib.parse import quote
import json

pattern = re.compile(r'[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}')
headers = {
    'Host': 'dw10.fdzcxy.edu.cn',
    'Connection': 'keep-alive',
    'responseType': 'json',
    'terminal': 'H5',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    '__device__': 'unknown',
    'Accept': 'application/json, text/plain, */*',
    'Cache-Control': 'no-cache',
    'clientType': 'mobile/h5_5.0',
    'deviceType': 'unknown',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


def get_stu_info() -> list[dict]:
    conf = configparser.ConfigParser()
    conf.read("db.ini", encoding="utf-8")
    host = conf['mysql']['host']
    usr = conf['mysql']['username']
    pwd = conf['mysql']['password']
    db = conf['mysql']['db']

    conn = pymysql.connect(host=host, user=usr, password=pwd, database=db, charset='utf8')
    cur = conn.cursor(pymysql.cursors.DictCursor)

    cur.execute("SELECT * from tbl_stu")
    data = cur.fetchall()
    return data


def sno_import():
    # import sno list
    snos = []
    snos_path = os.path.join(os.path.dirname(__file__), 'snos.txt')
    f = open(snos_path, 'r')
    for line in f.read().splitlines():
        snos.append(line)
    return snos


def izc_commit(stu: dict):
    sno = str(stu['sno'])
    name = stu['name']
    province = stu['province']
    city = stu['city']
    district = stu['district']

    # get SessionID
    url = 'http://dw10.fdzcxy.edu.cn/datawarn/ReportServer?formlet=app/sjkrb.frm&op=h5&userno=' + sno + '#/form'
    session_line = re.search('get sessionID.*', requests.get(url).text)
    session_id = session_line.group(0).split('\'')[1]

    # get Cookie,JSConfId,CallBackConfId,name
    url = 'http://dw10.fdzcxy.edu.cn/datawarn/decision/view/form?sessionID=' + session_id + \
          '&op=fr_form&cmd=load_content&toVanCharts=true&fine_api_v_json=3&widgetVersion=1'
    res = requests.get(url=url, headers=headers)
    items = res.json()['items'][0]['el']['items']

    submit = ''

    for i in items:
        if i['widgetName'] == 'SUBMIT':
            submit = i['listeners'][0]['action']
            break

    cookie = 'JSESSIONID=' + requests.utils.dict_from_cookiejar(res.cookies)['JSESSIONID']
    js_conf_id = pattern.findall(submit)[0]
    call_back_conf_id = pattern.findall(submit)[1]

    url = 'http://dw10.fdzcxy.edu.cn/datawarn/decision/view/form'
    submit_headers = {
        'Host': 'dw10.fdzcxy.edu.cn',
        'Connection': 'keep-alive',
        'terminal': 'H5',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36',
        '__device__': 'unknown',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json, text/plain, */*',
        'Cache-Control': 'no-cache',
        'sessionID': session_id,
        'clientType': 'mobile/h5_5.0',
        'deviceType': 'unknown',
        'Origin': 'http://dw10.fdzcxy.edu.cn',
        'Referer': 'http://dw10.fdzcxy.edu.cn/datawarn/ReportServer?formlet=app/sjkrb.frm&op=h5&userno=' + sno,
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cookie': cookie
    }

    data = {
        'op': 'dbcommit',
        '__parameters__': quote(
            '{"jsConfId":"' + js_conf_id + '","callbackConfId":"' + call_back_conf_id + '","LABEL2":"  每日健康上报","XH":"' + sno + '","XM":"' + name + '","LABEL12":"","LABEL0":"1. 目前所在位置:","SHENG":"' + province + '","SHI":"' + city + '","QU":"' + district + '","LABEL11":"2.填报时间:","SJ":"' + time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime()) + '","LABEL1":"3. 今日体温是否正常？(体温小于37.3为正常)","TWZC":"正常","LABEL6":"目前体温为：","TW":"0","TXWZ":"' + province + city + district + '","LABEL9":"4. 昨日午检体温:","WUJ":"36.4","LABEL8":"5. 昨日晚检体温:","WJ":"36.5","LABEL10":"6. 今日晨检体温:","CJ":"36.4","LABEL3":"7. 今日健康状况？","JK":["健康"],"JKZK":"","QTB":"请输入具体症状：","QT":" ","LABEL4":"8. 近14日你和你的共同居住者(包括家庭成员、共同租住的人员)是否存在确诊、疑似、无症状新冠感染者？","WTSQK":["无以下特殊情况"],"SFXG":"","LABEL5":"9. 今日隔离情况？","GLQK":"无需隔离","LABEL7":"* 本人承诺以上所填报的内容全部真实，并愿意承担相应责任。","CHECK":true,"DWWZ":{},"SUBMIT":"提交信息"}'),
    }

    res = requests.post(url=url, headers=submit_headers, data=data)
    return res.status_code == 200


def izc_check(sno):
    try:
        # get SessionID
        url = 'http://dw10.fdzcxy.edu.cn/datawarn/decision/view/report?viewlet=%252Fapp%252Fdkxq.cpt&__pi__=true&op=h5&xh=' \
              + sno \
              + '&userno=' \
              + sno
        session_line = re.search('get sessionID.*', requests.get(url).text)
        session_id = session_line.group(0).split('\'')[1]

        # get page_content (form)
        url = 'http://dw10.fdzcxy.edu.cn/datawarn/decision/view/report?toVanCharts=true&dynamicHyperlink=true&op=page_content&cmd=json&sessionID=' \
              + session_id \
              + '&fine_api_v_json=3&pn=1&__fr_locale__=zh_CN'
        s = json.loads(requests.get(url).text)
        date = []

        # find date&time from cellData
        for cells in s['pageContent']['detail'][0]['cellData']['rows']:
            for cell in cells['cells']:
                text = cell['text']
                if re.match('\\d+-\\d+-\\d+', text):
                    # append the date
                    date.append(cell['text'].split(' ')[0])

        # date check
        if datetime.datetime.now().strftime('%Y-%m-%d') in date:
            return True
        return False
    except Exception:
        print('Fatal error')
        raise


if __name__ == '__main__':
    # snos = sno_import()
    stus = get_stu_info()

    for stu in stus:
        res = izc_commit(stu)
        if res and izc_check(str(stu['sno'])):
            if res:
                print(stu['name'] + "填报成功！")
            else:
                print(stu['name'] + "检查失败！")
        else:
            print(stu['name'] + "填报失败！")
