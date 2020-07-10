#!/usr/bin/env python
# coding: utf-8

# In[1]:


'''

整體功能描述

'''


# In[2]:


'''

Application 主架構

'''

# 引用Web Server套件
from flask import Flask, request, abort

# 從linebot 套件包裡引用 LineBotApi 與 WebhookHandler 類別
from linebot import (
    LineBotApi, WebhookHandler
)

# 引用無效簽章錯誤
from linebot.exceptions import (
    InvalidSignatureError
)

# 載入json處理套件
import json, re, sys

# 載入基礎設定檔
secretFileContentJson=json.load(open("./line_secret_key",'r',encoding='utf8'))
server_url=secretFileContentJson.get("server_url")

#複製的，載入基礎設定檔
channel_access_token = secretFileContentJson.get("channel_access_token")
self_user_id = secretFileContentJson.get("self_user_id")
rich_menu_id = secretFileContentJson.get("rich_menu_id")
server = secretFileContentJson.get("kafka_server")
redis_port = secretFileContentJson.get("redis_port")
redis_server = secretFileContentJson.get("redis_server")


# 設定Server啟用細節
app = Flask(__name__,static_url_path = "/素材" , static_folder = "./素材/")

# 生成實體物件
line_bot_api = LineBotApi(secretFileContentJson.get("channel_access_token"))
handler = WebhookHandler(secretFileContentJson.get("secret_key"))

# 啟動server對外接口，使Line能丟消息進來
@app.route("/", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'



# In[3]:


'''

消息判斷器

讀取指定的json檔案後，把json解析成不同格式的SendMessage

讀取檔案，
把內容轉換成json
將json轉換成消息
放回array中，並把array傳出。

'''

# 引用會用到的套件
from linebot.models import (
    ImagemapSendMessage,TextSendMessage,ImageSendMessage,LocationSendMessage,FlexSendMessage,VideoSendMessage
)

from linebot.models.template import (
    ButtonsTemplate,CarouselTemplate,ConfirmTemplate,ImageCarouselTemplate
    
)

from linebot.models.template import *

def detect_json_array_to_new_message_array(fileName):
    
    #開啟檔案，轉成json   #記得加encoding = 'utf-8'
    with open(fileName, encoding = 'utf-8') as f:
        jsonArray = json.load(f)
    
    # 解析json
    returnArray = []
    for jsonObject in jsonArray:

        # 讀取其用來判斷的元件
        message_type = jsonObject.get('type')
        
        # 轉換
        if message_type == 'text':
            returnArray.append(TextSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'imagemap':
            returnArray.append(ImagemapSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'template':
            returnArray.append(TemplateSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'image':
            returnArray.append(ImageSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'sticker':
            returnArray.append(StickerSendMessage.new_from_json_dict(jsonObject))  
        elif message_type == 'audio':
            returnArray.append(AudioSendMessage.new_from_json_dict(jsonObject))  
        elif message_type == 'location':
            returnArray.append(LocationSendMessage.new_from_json_dict(jsonObject))
        elif message_type == 'flex':
            returnArray.append(FlexSendMessage.new_from_json_dict(jsonObject))  
        elif message_type == 'video':
            returnArray.append(VideoSendMessage.new_from_json_dict(jsonObject))    


    # 回傳
    return returnArray


# In[4]:


'''

handler處理關注消息

用戶關注時，讀取 素材 -> 關注 -> reply.json

將其轉換成可寄發的消息，傳回給Line

'''

# 引用套件
from linebot.models import (
    FollowEvent
)

"""
引用套件
連接資料庫

"""
#此部分有error，註解不用
# import peewee


# #改自己的
# db = peewee.PostgresqlDatabase('ddmq64pcoa29to', 
#                         user='mfpcpttczbibhf', 
#                         password='bee6a9b9436c3a55e6ff290647370141cbbfd3b500b256186140f7a605b8420d',
#                         host='ec2-52-202-146-43.compute-1.amazonaws.com', 
#                         port=5432)

# # 定義LineUserProfile 資料表
# class LineUserProfile(peewee.Model):
#     # 定義欄位
#     displayName = peewee.CharField()
#     pictureUrl = peewee.CharField()
#     statusMessage = peewee.CharField()
#     userId = peewee.CharField()
    
#     # 指定使用的資料庫
#     class Meta:
#         database = db

# # 創造資料庫
# db.create_tables([LineUserProfile])




#使用者輸入資料匯入kafka，並從kafka收取答案回應使用者
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError


def kafkaproducer(server, topic, ID, query):
    global producer
    return_value = 0

    def error_cb(err):
        print('Error: %s' % err)

    props = {
        'bootstrap.servers': server,  # <-- 置換成要連接的Kafka集群
        'error_cb': error_cb                    # 設定接收error訊息的callback函數
    }
    # 步驟2. 產生一個Kafka的Producer的實例
    if producer is None:
        producer = Producer(props)
    # 步驟3. 指定想要發佈訊息的topic名稱
    topicName = topic
    try:
        # produce(topic, [value], [key], [partition], [on_delivery], [timestamp], [headers])
        producer.produce(topicName, key=ID, value=query)
        producer.flush()
        return_value+=1
    except:
        return_value = 0
    producer.flush()
    return return_value

def kafkaconsumer(server, groupid, topic, ID):
    global consumer

    def try_decode_utf8(data):
        if data:
            return data.decode('utf-8')
        else:
            return None

    def my_assign(consumer_instance, partitions):
        for p in partitions:
            p.offset = 0
        consumer_instance.assign(partitions)

    def error_cb(err):
        pass

    props = {
        'bootstrap.servers': server,
        'group.id': groupid,
        'auto.offset.reset': 'earliest',
        'session.timeout.ms': 6000,
        'error_cb': error_cb
    }
    return_answer = {}
    if consumer is None:
        consumer = Consumer(props)
    topicName = topic
    consumer.subscribe([topicName])
    records = []
    while len(records) == 0:
        records = consumer.consume(num_messages=1)
        if records is None:
            continue
        for record in records:
            if record is None:
                continue
            if record.error():
                continue
            else:
                msgKey = try_decode_utf8(record.key())
                msgValue = try_decode_utf8(record.value())

                if str(msgKey) != ID:
                    records = []
                else:
                    return_answer[msgKey] = msgValue

    #     consumer.close()
    return return_answer


def pro_kafkaconsumer(server, groupid, topic, ID):
    global pconsumer

    def try_decode_utf8(data):
        if data:
            return data.decode('utf-8')
        else:
            return None

    def my_assign(consumer_instance, partitions):
        for p in partitions:
            p.offset = 0
        consumer_instance.assign(partitions)

    def error_cb(err):
        pass

    props = {
        'bootstrap.servers': server,
        'group.id': groupid,
        'auto.offset.reset': 'earliest',
        'session.timeout.ms': 6000,
        'error_cb': error_cb
    }
    return_answer = {}
    if pconsumer is None:
        pconsumer = Consumer(props)
    topicName = topic
    pconsumer.subscribe([topicName],on_assign=my_assign)
    records = []
    while len(records) == 0:
        records = pconsumer.consume(num_messages=1)
        if records is None:
            continue
        for record in records:
            if record is None:
                continue
            if record.error():
                continue
            else:
                msgKey = try_decode_utf8(record.key())
                msgValue = try_decode_utf8(record.value())

                if str(msgKey) != ID:
                    records = []
                else:
                    return_answer[msgKey] = msgValue

    #     consumer.close()
    return return_answer



'''

# 新好友歡迎(insert user id)
新使用者加入，即把使用者user_id匯入至kafka

'''

#匯入套件
import time, requests

# 關注事件處理
@handler.add(FollowEvent)
def process_follow_event(event):
    
    # 讀取並轉換
    result_message_array =[]
    replyJsonPath = "素材/關注/reply.json"
    result_message_array = detect_json_array_to_new_message_array(replyJsonPath)
        
    #複製的 將菜單綁至用戶上
    user_id = line_bot_api.get_profile(event.source.user_id)
    linkRichMenuId = rich_menu_id
    linkMenuEndpoint = 'https://api.line.me/v2/bot/user/%s/richmenu/%s' % (event.source.user_id, linkRichMenuId)
    linkMenuRequestHeader = {'Content-Type': 'image/jpeg', 'Authorization': 'Bearer %s' % channel_access_token}
    lineLinkMenuResponse = requests.post(linkMenuEndpoint, headers=linkMenuRequestHeader)
    app.logger.info("Link Menu to %s status :" % user_id, lineLinkMenuResponse)

    # 消息發送
    line_bot_api.reply_message(
        event.reply_token,
        result_message_array
    )
    
    nowtime = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    # 取出消息內User的資料
    user_profile = line_bot_api.get_profile(event.source.user_id)
    user_profile_dict = vars(user_profile)
    print(user_profile_dict,
        user_profile_dict.get("display_name"),
        user_profile_dict.get("picture_url"),
        user_profile_dict.get("status_message"),
        user_profile_dict.get("user_id"),
        nowtime
    )
    
    #此部分有error，註解不用
#     new_user = LineUserProfile.create(
#         displayName = user_profile_dict.get("display_name"),
#         pictureUrl = user_profile_dict.get("picture_url") if user_profile_dict.get("picture_url") is not None else "",
#         statusMessage = user_profile_dict.get("status_message") if user_profile_dict.get("status_message") is not None else "",
#         userId = user_profile_dict.get("user_id")
#     )
    
    
    #新加入者資料匯入kafka
    
    global producer  #
    global server  #
    
    ID = user_profile_dict.get("user_id")  #
    kafkaproducer(server=server, topic='Join', ID=ID, query=nowtime)  #



# In[5]:


'''

handler處理文字消息

收到用戶回應的文字消息，
按文字消息內容，往素材資料夾中，找尋以該內容命名的資料夾，讀取裡面的reply.json

轉譯json後，將消息回傳給用戶

'''

# 引用套件
from linebot.models import (
    MessageEvent, TextMessage
)
import os
import redis, datetime

#引用副程式
import app_1_news, Msg_Template, stockprice, kchart, Technical_Analysis, Institutional_Investors
emoji_upinfo = u'\U0001F447'

# 文字消息處理
@handler.add(MessageEvent,message=TextMessage)
def process_text_message(event):
    global producer#
    global consumer#
    global server#
    global r#
    
    nowtime = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    msg = str(event.message.text).upper().strip()
    # 取出消息內User的資料
    profile = line_bot_api.get_profile(event.source.user_id)
#     print(profile)
     
    #取出userid, displayname 丟回全域變數
    profile_dict = vars(profile)    
    print("使用者輸入內容 =", msg, " ,LINE名字 =", profile_dict.get("display_name"), " ,使用者 =", profile_dict.get("user_id"), " ,輸入內容時間 =", nowtime)
            
    ID = profile_dict.get("user_id")#
    text = event.message.text  #
    query = str(text)  #
    groupid = str(ID)  #
    
    #使用者及使用者輸入內容匯入kafka(2020070041700先註解kafka有問題)
    kafkaproducer(server=server, topic='2_resquest', ID=ID, query=query)  #

    if msg == '股票推薦':
        line_bot_api.push_message(ID, TextSendMessage(text='請稍等，\n資料產生中!!'))
        
        user_type =str(r.get(ID))  
        user_type+='_'
        user_type+=str(datetime.datetime.now().strftime('%Y%m%d'))
        res = pro_kafkaconsumer(server=server, groupid='groupid', topic='promote_stock', ID=user_type)  #此ID為type1(kafka內的)
        Stock_list = [i for i in eval(res[user_type]).keys()]
        Str ="股票推薦清單" + emoji_upinfo
        Str+='\n'
        Str+="======================="
        Str+='\n'
        for stl in Stock_list:
            Str+=stl
            Str+='\n'

        Str+='======================'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=Str))
        
        
    elif msg == '.2-1_10%內可接受範圍':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.2-3_50%內可接受範圍':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
    
    elif msg == '.2-4_100%以上':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.3-1_1個月內':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.3-4_1年以上':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.4-1_每天花費1~2小時':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.4-3_每月花費1~2小時':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.5-1_高風險高報酬':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.6-1_投資一定有風險':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
        
    elif msg == '.7-1_我很積極布局':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))

    elif msg == '.7-2_我要觀察一陣子':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))

    elif msg == '.7-4_認賠殺出':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))

    elif msg == '.8-1_我喜愛賺價差':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))

    elif msg == '.8-2_我喜愛超高報酬':
        res = kafkaconsumer(server=server, groupid=groupid, topic='1_resquest', ID=ID)  #
        res = res[ID]  #
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=str(res)))
    
    # 個股新聞
    elif re.match('N[0-9]{4}', msg):  
        stockNumber = msg[1:5]
        content = app_1_news.single_stock(stockNumber)
        line_bot_api.push_message(ID, TextSendMessage('即將給您編號' + stockNumber + '\n個股新聞!'))
        line_bot_api.push_message(ID, content)
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    # 每週新聞回顧
    elif re.match("每週新聞回顧", msg):
        line_bot_api.push_message(ID, TextSendMessage("我們將給您最新的周回顧，\n請點選圖片連結!!"))
        line_bot_api.push_message(ID, app_1_news.weekly_finance_news())
    
    # 查詢某檔股票股價
    elif re.match('S[0-9]', msg):  
        stockNumber = msg[1:]
        stockName = stockprice.get_stock_name(stockNumber)
        if stockName == "no":
            line_bot_api.push_message(ID, TextSendMessage("股票編號錯誤"))
        else:
            line_bot_api.push_message(ID, TextSendMessage('稍等一下,\n查詢編號' + stockNumber + '\n的股價中...'))
            content_text = stockprice.getprice(stockNumber, msg)
            content = Msg_Template.stock_reply(stockNumber, content_text)
            line_bot_api.push_message(ID, content)
    
    #K線圖     #OK
    elif re.match("K[0-9]{4}", msg):
        stockNumber = msg[1:]
        content = Msg_Template.kchart_msg + "\n" + Msg_Template.kd_msg
        line_bot_api.push_message(ID, TextSendMessage(content))
        line_bot_api.push_message(ID, TextSendMessage('稍等一下,\nK線圖繪製中...'))
        k_imgurl = kchart.draw_kchart(stockNumber)
        line_bot_api.push_message(ID, ImageSendMessage(original_content_url=k_imgurl, preview_image_url=k_imgurl))
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    #MACD指標     #OK
    elif re.match("MACD[0-9]", msg):
        stockNumber = msg[4:]
        content = Msg_Template.macd_msg
        line_bot_api.push_message(ID, TextSendMessage('稍等一下,\n將給您編號' + stockNumber + '\nMACD指標...'))
        line_bot_api.push_message(ID, TextSendMessage(content))
        MACD_imgurl = Technical_Analysis.MACD_pic(stockNumber, msg)
        line_bot_api.push_message(ID,
            ImageSendMessage(original_content_url=MACD_imgurl, preview_image_url=MACD_imgurl))
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    #RSI指標  #OK
    elif re.match('RSI[0-9]', msg):
        stockNumber = msg[3:]
        line_bot_api.push_message(ID, TextSendMessage('稍等一下,\n將給您編號' + stockNumber + '\nRSI指標...'))
        RSI_imgurl = Technical_Analysis.stock_RSI(stockNumber)
        line_bot_api.push_message(ID, ImageSendMessage(original_content_url=RSI_imgurl, preview_image_url=RSI_imgurl))
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    #BBAND指標      #OK
    elif re.match("BBAND[0-9]", msg):
        stockNumber = msg[5:]
        content = Msg_Template.bband_msg
        line_bot_api.push_message(ID, TextSendMessage(content))
        line_bot_api.push_message(ID, TextSendMessage('稍等一下,\n將給您編號' + stockNumber + '\nBBand指標...'))
        BBANDS_imgurl = Technical_Analysis.BBANDS_pic(stockNumber, msg)
        line_bot_api.push_message(ID,
            ImageSendMessage(original_content_url=BBANDS_imgurl, preview_image_url=BBANDS_imgurl))
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    #畫近一年股價走勢圖      #OK
    elif re.match("P[0-9]{4}", msg):
        stockNumber = msg[1:]
        line_bot_api.push_message(ID, TextSendMessage('稍等一下,\n將給您編號' + stockNumber + '\n股價走勢圖!'))
        trend_imgurl = stockprice.stock_trend(stockNumber, msg)
        line_bot_api.push_message(ID,
            ImageSendMessage(original_content_url=trend_imgurl, preview_image_url=trend_imgurl))
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    # 個股年收益率分析圖 #OK
    elif re.match('E[0-9]{4}', msg):
        targetStock = msg[1:]
        line_bot_api.push_message(ID, TextSendMessage('分析' + targetStock + '中，\n年收益率圖產生中，\n稍等一下。'))
        imgurl2 = stockprice.show_return(targetStock, msg)  
        line_bot_api.push_message(ID, ImageSendMessage(original_content_url=imgurl2, preview_image_url=imgurl2))
        btn_msg = Msg_Template.stock_reply_other(targetStock)
        line_bot_api.push_message(ID, btn_msg)
    
    #三大法人買賣資訊  #OK
    elif re.match('F[0-9]', msg):
        stockNumber = msg[1:]
        line_bot_api.push_message(ID, TextSendMessage('稍等一下,\n將給您編號' + stockNumber + '\n三大法人買賣資訊...'))
        content = Institutional_Investors.institutional_investors(stockNumber)
        line_bot_api.push_message(ID, TextSendMessage(content))
        btn_msg = Msg_Template.stock_reply_other(stockNumber)
        line_bot_api.push_message(ID, btn_msg)
    
    # 籌碼面分析圖    #失敗_有空從做此步
#     elif re.match('C[0-9]', msg):
#         targetStock = msg[1:]
#         line_bot_api.push_message(ID, TextSendMessage('分析' + targetStock + '中，\n籌碼面分析圖產生中，\n稍等一下。'))
#         imgurl2 = Institutional_Investors.institutional_investors_pic(targetStock)
#         if imgurl2 == "股票代碼錯誤!":
#             line_bot_api.push_message(ID, TextSendMessage("股票代碼錯誤!"))
        
#         line_bot_api.push_message(ID, ImageSendMessage(original_content_url=imgurl2, preview_image_url=imgurl2))
#         btn_msg = Msg_Template.stock_reply_other(targetStock)
#         line_bot_api.push_message(ID, btn_msg)
    
    #功能說明
    elif msg == '功能說明':
        line_bot_api.reply_message(event.reply_token, \
            TextSendMessage(text='您好～\n在此說明我的功能!\n\nK+個股代號(舉例:K2330)，\n=>會產生出2330的K線圖。\n\nN+個股代號(舉例:N2330)，\n=>會顯示近期2330的新聞連結。\n\nS+個股代號(舉例:S2330)，\n=>會顯示最近2330的\n開、高、收、低價格。\n\nMACD+個股代號(舉例:MACD2330)，\n=>會產生出2330的MACD指標圖。\n\nRSI+個股代號(舉例:RSI2330)，\n=>會產生出2330的RSI指標圖。\n\nBBAND+個股代號(舉例:BBAND2330)，\n=>會產生出2330的BBAND指標圖。\n\nP+個股代號(舉例:P2330)，\n=>會產生出2330的一年股價走勢圖。\n\nE+個股代號(舉例:E2330)，\n=>會產生出2330的年收益率分析圖。\n\nF+個股代號(舉例:F2330)，\n=>會產生出2330三大法人買賣資訊。\n\n或者點選"股票推薦"，\n推薦適合您的股票名單。\n\n功能說明完畢，\n謝謝觀看!!'))
    
    #問候語回應
    elif msg in ("你好", "哈嘍", 'HI', 'hi', '嗨', "妳好", "您好", "Hi", "hI"):
        line_bot_api.reply_message(event.reply_token, \
            TextSendMessage(text='您好～歡迎加入股市小子!\n下方圖文選單可以點選!\n或請點選下方"功能說明"，\n會詳列出我的功能說明!'))
    

    else:
        pass 


    # 讀取本地檔案，並轉譯成消息
    result_message_array =[]
    replyJsonPath = "素材/"+event.message.text+"/reply.json"
    result_message_array = detect_json_array_to_new_message_array(replyJsonPath)
    
    # 發送
    line_bot_api.reply_message(
    event.reply_token,
    result_message_array
    )

# In[6]:


'''

handler處理Postback Event

載入功能選單與啟動特殊功能

解析postback的data，並按照data欄位判斷處理

現有三個欄位
menu, folder, tag

若folder欄位有值，則
    讀取其reply.json，轉譯成消息，並發送

若menu欄位有值，則
    讀取其rich_menu_id，並取得用戶id，將用戶與選單綁定
    讀取其reply.json，轉譯成消息，並發送

'''
from linebot.models import (
    PostbackEvent
)

from urllib.parse import parse_qs 

@handler.add(PostbackEvent)
def process_postback_event(event):
    
    query_string_dict = parse_qs(event.postback.data)
    
    print(query_string_dict)
    if 'folder' in query_string_dict:
    
        result_message_array =[]

        replyJsonPath = '素材/'+query_string_dict.get('folder')[0]+"/reply.json"
        result_message_array = detect_json_array_to_new_message_array(replyJsonPath)
  
        line_bot_api.reply_message(
            event.reply_token,
            result_message_array
        )
    elif 'menu' in query_string_dict:
 
        linkRichMenuId = open("素材/"+query_string_dict.get('menu')[0]+'/rich_menu_id', 'r').read()
        line_bot_api.link_rich_menu_to_user(event.source.user_id,linkRichMenuId)
        
        replyJsonPath = '素材/'+query_string_dict.get('menu')[0]+"/reply.json"
        result_message_array = detect_json_array_to_new_message_array(replyJsonPath)
  
        line_bot_api.reply_message(
            event.reply_token,
            result_message_array
        )


# In[ ]:


'''

Application 運行（開發版）

'''
# if __name__ == "__main__":
#     app.run(host='0.0.0.0')


# In[ ]:


'''

Application 運行（heroku版）

'''



if __name__ == "__main__":
    
    producer,consumer = None,None
    pconsumer = None
    
    r = redis.Redis(host=redis_server, port=redis_port, decode_responses=True)
    
    app.run(host='0.0.0.0',port=os.environ['PORT'])


# In[ ]:




