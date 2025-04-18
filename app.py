import os
import json
from flask import Flask, request, abort
from dotenv import load_dotenv  
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import TextMessage
from linebot.v3.exceptions import InvalidSignatureError
from google.cloud.dialogflow_v2 import SessionsClient
from google.cloud.dialogflow_v2.types import TextInput, QueryInput

load_dotenv()

# Dialogflow Configuration
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
DIALOGFLOW_PROJECT_ID = os.getenv("DIALOGFLOW_PROJECT_ID")
SESSION_ID = "line-bot-session"

# LINE Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

app = Flask(__name__)

# LINE Bot Client
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text_from_user = event.message.text

    is_group = hasattr(event.source, 'type') and event.source.type in ['group', 'room']
    bot_name = "น้องสวพ."
    should_respond = False
    actual_message = text_from_user

    if is_group:
        if text_from_user.startswith(f'@{bot_name}'):
            mention_part = f'@{bot_name}'
            message_start = text_from_user.find(mention_part) + len(mention_part)
            actual_message = text_from_user[message_start:].strip()
            should_respond = True
    else:
        should_respond = True

    if should_respond:
        if not actual_message:
            reply_text = f"สวัสดีค่ะ หนูชื่อ {bot_name} คุณต้องการสอบถามอะไรค่ะ?"
        else:
            user_session_id = f"{SESSION_ID}-{user_id}"
            response = detect_intent_texts(DIALOGFLOW_PROJECT_ID, user_session_id, actual_message, 'th')
            reply_text = response.query_result.fulfillment_text or "ขออภัย ฉันไม่เข้าใจคำถามของคุณ กรุณาถามใหม่อีกครั้ง"

        line_bot_api.reply_message(
            reply_message_request={
                "replyToken": event.reply_token,
                "messages": [TextMessage(text=reply_text)]
            }
        )

def detect_intent_texts(project_id, session_id, text, language_code):
    try:
        session_client = SessionsClient()
        session = session_client.session_path(project_id, session_id)
        text_input = TextInput(text=text, language_code=language_code)
        query_input = QueryInput(text=text_input)
        response = session_client.detect_intent(request={"session": session, "query_input": query_input})
        return response
    except Exception as e:
        app.logger.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อกับ Dialogflow: {str(e)}")
        class MockResponse:
            class MockQueryResult:
                fulfillment_text = "ขออภัย ระบบกำลังมีปัญหาในการเชื่อมต่อ กรุณาลองใหม่ในภายหลัง"
            query_result = MockQueryResult()
        return MockResponse()

@app.route("/")
def home():
    return "LINE Bot with Dialogflow is running!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
