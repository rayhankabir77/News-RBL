import os
import json
import threading
from flask import Flask
from telebot import TeleBot, types
import firebase_admin
from firebase_admin import credentials, db

# Flask সার্ভার সেটআপ
app = Flask(__name__)

@app.route('/check')
def check():
    return "OK", 200

@app.route('/')
def home():
    return "Bot is running!", 200

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# এনভায়রনমেন্ট ভ্যারিয়েবল লোড
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTDB_URL = os.getenv("RTDB_URL")
FIREBASE_ADMIN_ENV = os.getenv("FIREBASE_ADMIN")

if not BOT_TOKEN or not RTDB_URL or not FIREBASE_ADMIN_ENV:
    raise ValueError("Error: Required environment variables are missing in Render Dashboard!")

# ফায়ারবেস ইনিশিয়ালাইজেশন
try:
    if FIREBASE_ADMIN_ENV.strip().startswith("{"):
        cred_dict = json.loads(FIREBASE_ADMIN_ENV)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate(FIREBASE_ADMIN_ENV)

    firebase_admin.initialize_app(cred, {
        'databaseURL': RTDB_URL
    })
except Exception as e:
    raise RuntimeError(f"Failed to initialize Firebase Admin SDK: {e}")

bot = TeleBot(BOT_TOKEN)

# ৪টি চ্যানেলের ইউজারনেম
CHANNEL_1 = '@earnmoneybd1111'
CHANNEL_2 = '@bbbbbbbbbb11111100'
SPONSOR_1 = '@raybilofficial'
SPONSOR_2 = '@earnglowofficial'

# টেম্পোরারি স্টেট স্টোর
user_states = {}

def clear_user_state(chat_id, notify_timeout=False):
    state = user_states.pop(chat_id, None)
    if state:
        timer = state.get('timer')
        if timer:
            timer.cancel()
        if notify_timeout:
            try:
                bot.send_message(chat_id, "⏰ সময় শেষ হয়ে গেছে! আপনার রিকোয়েস্টটি বাতিল করা হয়েছে। আবার চেষ্টা করুন।")
            except Exception as e:
                print(f"Error sending timeout msg: {e}")

def start_timeout_timer(chat_id, seconds):
    if chat_id in user_states and 'timer' in user_states[chat_id]:
        user_states[chat_id]['timer'].cancel()
        
    timer = threading.Timer(seconds, clear_user_state, args=[chat_id, True])
    timer.start()
    if chat_id in user_states:
        user_states[chat_id]['timer'] = timer

# সুন্দর আইকনসহ হোম মেনু লেআউট
def get_home_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('➕ Create Account', '📋 Task')
    markup.row('📢 Sponsor Now', '📊 Dashboard')
    markup.row('💳 Withdrawal', '🤝 Support')
    markup.row('👨‍💻 Developer Profile')
    return markup
