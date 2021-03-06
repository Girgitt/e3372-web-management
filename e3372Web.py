#!/usr/bin/python
# coding:utf-8
from flask import Flask, render_template, jsonify, request
import sys
import pprint
import requests
import xmltodict
import json
import time
import logging
import traceback
from logging.handlers import RotatingFileHandler
from decorators import socket_timeout

logger = logging.getLogger('my_logger')
logger.setLevel(logging.ERROR)
handler = RotatingFileHandler('logs/configlog.log', maxBytes=2000, backupCount=5)
# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class CustomFlask(Flask):  # custom the flask var as {#var#}
    jinja_options = Flask.jinja_options.copy()
    jinja_options.update(dict(
        block_start_string='{%',
        block_end_string='%}',
        variable_start_string='{#',
        variable_end_string='#}',
        comment_start_string='<#',
        comment_end_string='#>',
    ))


# app = Flask(__name__)
app = CustomFlask(__name__)


class HuaweiE3372(object):
    BASE_URL = 'http://{host}'
    COOKIE_URL = '/html/index.html'
    XML_APIS = [
        '/api/monitoring/converged-status',
        '/api/device/basic_information',
        '/api/device/information',
        '/api/device/signal',
        '/api/net/net-mode',
        # below API would refer to refresh periodly
        '/api/monitoring/status',
        '/api/monitoring/check-notifications',
        '/api/monitoring/traffic-statistics',
        '/api/dialup/mobile-dataswitch',
        '/api/monitoring/traffic-statistics',
        '/api/net/current-plmn',
    ]
    session = None

    def __init__(self, host='192.168.8.1'):
        self.host = host
        self.base_url = self.BASE_URL.format(host=host)
        self.session = requests.Session()
        r = self.session.get(self.base_url + self.COOKIE_URL)

    def get(self, path, headers=None):
        try:
            logger.debug("returning GET (raw text):\n%s" % self.session.get(self.base_url + path, headers=headers).text)
            return xmltodict.parse(self.session.get(self.base_url + path, headers=headers).text).get('response', None)
        except:
            logger.exception("could not parse:\n%s" % self.session.get(self.base_url + path, headers=headers).text)

    def get_request_headers(self, content_type=None):
        SessionToken = xmltodict.parse(self.session.get(self.base_url + "/api/webserver/SesTokInfo").text).get(
            'response', None)

        if content_type is None:
            content_type = "application/x-www-form-urlencoded; charset=UTF-8"

        if SessionToken is not None:
            logger.debug("using SessionToken")
            Session = SessionToken.get("SesInfo")  # cookie
            Token = SessionToken.get("TokInfo")  # token
            headers = {'Cookie': Session, '__RequestVerificationToken': Token, "Content-Type": content_type}
        else:
            logger.debug("using token only")
            Token = xmltodict.parse(self.session.get(self.base_url + "/api/webserver/token").text).get('response',
                                                                                                       None).get(
                "token")
            headers = {'__RequestVerificationToken': Token, "Content-Type": content_type}
        logger.debug("returning headers:%s" % headers)
        return headers

    def postSMS(self, path, number, text):
        headers = self.get_request_headers()
        APIurl = self.base_url + path
        Length = str(len(text))  # text length
        post_data = "<request><Index>-1</Index><Phones><Phone>" + number + "</Phone></Phones><Sca></Sca><Content>" + text + "</Content><Length>" + Length + "</Length><Reserved>1</Reserved><Date>-1</Date></request>"
        logging.debug(post_data)
        return xmltodict.parse(self.session.post(url=APIurl, data=post_data, headers=headers).text)
    
    def postSMSdelete(self, path, sms_id):
        headers = self.get_request_headers()
        APIurl = self.base_url + path
        post_data = "<request><Index>" + sms_id + "</Index></request>"
        logging.debug(post_data)
        return xmltodict.parse(self.session.post(url=APIurl, data=post_data, headers=headers).text)

    def postSMSlist(self, path, max_count=50, ascending_sort=False, inbox='received'):

        if max_count > 50:
            max_count = 50

        if max_count < 0:
            max_count = 1
        ascending = 0
        
        if ascending_sort:
            ascending = 1

        if inbox not in ['received', 'sent']:
            logging.error("unsupported inbox arg value; forcing received")
            inbox = 'received'

        headers = self.get_request_headers(content_type="text/xml")
        APIurl = self.base_url + path
        if inbox == 'received':
            post_data = "<request><PageIndex>1</PageIndex><ReadCount>"+str(max_count)+"</ReadCount><BoxType>1</BoxType><SortType>0</SortType><Ascending>"+str(ascending)+"</Ascending><UnreadPreferred>1</UnreadPreferred></request>"
        elif inbox == 'sent':
            post_data = "<request><PageIndex>1</PageIndex><ReadCount>"+str(max_count)+"</ReadCount><BoxType>2</BoxType><SortType>0</SortType><Ascending>"+str(ascending)+"</Ascending><UnreadPreferred>1</UnreadPreferred></request>"

        logging.debug(post_data)
        return xmltodict.parse(self.session.post(url=APIurl, data=post_data, headers=headers).text)

    def postdataswitch(self, path, dataswitch):
        headers = self.get_request_headers()
        APIurl = self.base_url + path
        post_data = "<request><dataswitch>" + dataswitch + "</dataswitch>"
        logging.debug(post_data)
        return xmltodict.parse(self.session.post(url=APIurl, data=post_data, headers=headers).text)


@app.route("/")
def mainpage():
    try:
        return render_template('index.html', updatetime=str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
    except:
        logger.error("Render mainpage failed")
        return "error"


@app.route('/getdata', methods=['GET'])  # API data return as json
@socket_timeout(10)
def getAPIdata():
    try:
        e3372 = HuaweiE3372()
        dict = {}
        for path in e3372.XML_APIS:
            path_data = e3372.get(path)
            if path_data is not None:
                for key, value in path_data.items():
                    if (value):
                        dict[key] = value
        logger.info("Get dongle data successful")
        return jsonify(**dict)
    except:
        logger.exception("Get dongole data failed")
        return "Unknown error"


@app.route('/sendsms', methods=['POST'])  # send Message using POST
@socket_timeout(10)
def sendsms():
    jsonData = request.data
    dataDict = json.loads(jsonData)
    try:
        e3372 = HuaweiE3372()
        name = dataDict['number']
        text = dataDict['SMStext']
        test = e3372.postSMS("/api/sms/send-sms", name, text).get('response')
        logger.info("Sent Message")
        return "Message status: %s" % test
    except:
        logger.error("Send Message failed")
        return "Unknown error"


@app.route('/deletesms', methods=['POST'])  # delete Message by index using POST
@socket_timeout(10)
def deletesms():
    jsonData = request.data
    dataDict = json.loads(jsonData)
    try:
        e3372 = HuaweiE3372()
        sms_id = dataDict['sms_id']
        result = e3372.postSMSdelete("/api/sms/delete-sms", sms_id).get('response')
        logger.info("Message deleted: %s" % sms_id)
        return "Message delete status: %s" % result
    except Exception as e:
        logger.error("Message delete failed")
        return "Unhandled exception: %s" % e.message


@app.route('/smslist', methods=['GET'])  # get messages
@socket_timeout(10)
def getsmses():
    max_count = 50
    if request.args.get("max_count") is not None:
        max_count = int(request.args.get("max_count"))

    ascending = False
    if request.args.get("ascending_sort") is not None:
        if str(request.args.get("ascending_sort")).upper() in ['1', 'TRUE', 'ON', 'YES']:
            ascending = True
    
    inbox = 'received' 
    if request.args.get("inbox") is not None:
        if str(request.args.get("inbox")).upper() in ['SENT']:
            inbox = 'sent'   

    try:
        e3372 = HuaweiE3372()
        path_data = e3372.postSMSlist("/api/sms/sms-list", max_count=max_count, ascending_sort=ascending, inbox=inbox).get('response', {}).get('Messages', {})
        logger.debug("Get /api/sms/sms-list called")
        logger.debug("result:\n%s" % path_data)
        return jsonify(path_data)
    except:
        logger.exception("Get sms-list failed")
        return "Unknown error"


@app.route('/dataswitch', methods=['POST'])  # mobile data on or off using POST
def dataswitch():
    jsonData = request.data
    dataDict = json.loads(jsonData)
    try:
        dataswitch = dataDict['dataswitch']
        e3372 = HuaweiE3372()
        test = e3372.postdataswitch("/api/dialup/mobile-dataswitch", dataswitch).get('response', None)
        logger.info("Data switched")
        return "Dataswitch status: %s" % test
    except:
        logger.error("data switch failed")
        return "Unknown error"


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
