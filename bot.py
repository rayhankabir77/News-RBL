
import os
import json
import threading
import random
import string
import hmac
import hashlib
import urllib.parse
from flask import Flask, request, Response
from telebot import TeleBot, types
import firebase_admin
from firebase_admin import credentials, db

# --- ১. Flask ওয়েব সার্ভার ও সিকিউর API গেটওয়ে ---
app = Flask(__name__)

# টেলিগ্রাম WebApp initData ভেরিফিকেশন সিকিউর হেল্পার
def verify_telegram_init_data(init_data: str, bot_token: str):
    try:
        parsed_data = urllib.parse.parse_qsl(init_data)
        data_dict = dict(parsed_data)
        
        received_hash = data_dict.pop('hash', None)
        if not received_hash:
            return False, None
        
        sorted_items = sorted(data_dict.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)
        
        secret_key = hmac.new(b"WebApps", bot_token.encode('utf-8'), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(calculated_hash, received_hash):
            user_str = data_dict.get('user')
            if user_str:
                return True, json.loads(user_str)
            return True, {}
        return False, None
    except Exception as e:
        print(f"Error verifying initData: {e}")
        return False, None


# earnglow.shop থেকে সফল কাজের ডাটা রিসিভ করার এন্ডপয়েন্ট
@app.route('/add', methods=['POST', 'OPTIONS'])
def add_credit():
    if request.method == 'OPTIONS':
        response = Response()
        response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response

    try:
        data = request.json or {}
        init_data_str = data.get('intdata') or data.get('initData')
        userid = str(data.get('userid', ''))
        name = data.get('name', '')
        action = data.get('action', '') # 'link' অথবা 'watch'

        if not init_data_str or not userid or not name or action not in ['link', 'watch']:
            response = Response(response=json.dumps({"success": False, "error": "Invalid request payload"}), status=400, mimetype="application/json")
            response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
            return response

        is_valid, telegram_user = verify_telegram_init_data(init_data_str, BOT_TOKEN)
        if not is_valid or not telegram_user:
            response = Response(response=json.dumps({"success": False, "error": "Invalid initData signature"}), status=401, mimetype="application/json")
            response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
            return response

        telegram_uid = str(telegram_user.get('id', ''))
        if telegram_uid != userid:
            response = Response(response=json.dumps({"success": False, "error": "UserID mismatch with session"}), status=403, mimetype="application/json")
            response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
            return response

        user_ref = db.reference(f'user/{userid}')
        user_data = user_ref.get()
        if not user_data:
            response = Response(response=json.dumps({"success": False, "error": "User does not exist"}), status=404, mimetype="application/json")
            response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
            return response

        current_main_balance = user_data.get('main_balance', 0)
        user_ref.update({
            'main_balance': current_main_balance + 1
        })

        response = Response(response=json.dumps({"success": True, "message": "Credit added successfully"}), status=200, mimetype="application/json")
        response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
        return response

    except Exception as e:
        print(f"Error in /add endpoint: {e}")
        response = Response(response=json.dumps({"success": False, "error": "Server error"}), status=500, mimetype="application/json")
        response.headers.add('Access-Control-Allow-Origin', 'https://earnglow.shop')
        return response


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


# --- ২. ফায়ারবেস ও টেলিগ্রাম এনভায়রনমেন্ট চেক ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTDB_URL = os.getenv("RTDB_URL")
FIREBASE_ADMIN_ENV = os.getenv("FIREBASE_ADMIN")

if not BOT_TOKEN or not RTDB_URL or not FIREBASE_ADMIN_ENV:
    raise ValueError("Error: Required environment variables are missing in Render Dashboard!")

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

# ৪টি চ্যানেলের বিবরণ
CHANNEL_1 = '@earnmoneybd1111'
CHANNEL_2 = '@bbbbbbbbbb11111100'
SPONSOR_1 = '@raybilofficial'
SPONSOR_2 = '@earnglowofficial'

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

def get_home_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('➕ Create Account', '📋 Task')
    markup.row('📢 Sponsor Now', '📊 Dashboard')
    markup.row('💳 Withdrawal', '🤝 Support')
    markup.row('👨‍💻 Developer Profile', '👥 Refer')
    return markup


# --- ৩. আকর্ষণীয় স্টার্ট হ্যান্ডলার ও ভেরিফিকেশন ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    parts = message.text.split()
    referrer_id = parts[1] if len(parts) > 1 else 'direct'

    try:
        user_ref = db.reference(f'user/{user_id}')
        user_snapshot = user_ref.get()

        if user_snapshot:
            bot.send_message(chat_id, "EARN MONEY BD বটের হোম মেনু:", reply_markup=get_home_menu())
            return

        welcome_text = (
            f"🌟 **আসসালামু আলাইকুম, {full_name}!** 🌟\n"
            f"**EARN MONEY BD** বটের আকর্ষণীয় আয়ের প্ল্যাটফর্মে আপনাকে স্বাগতম 😊।\n\n"
            f"টেলিগ্রামের সবচেয়ে সেরা বটের মাধ্যমে ঘরে বসে মোবাইল দিয়ে খুব সহজে আনলিমিটেড টাকা আয় করুন! 💰\n\n"
            f"📩 **জিমেইল আইডি বিক্রি করে:** প্রতি অ্যাকাউন্ট ১২ টাকা!\n"
            f"🌐 **সহজ লিংক ভিজিট করে:** প্রতিদিন নতুন নতুন লিংক ভিজিট করুন আর সহজে টাকা আয় করুন!\n"
            f"📺 **ভিডিও বিজ্ঞাপন দেখে:** বিজ্ঞাপন বা ছোট ছোট ভিডিও দেখে আনলিমিটেড ইনকাম করুন!\n"
            f"👥 **রেফার করে:** প্রতি সফল রেফারে পাচ্ছেন ২ টাকা বোনাস!\n"
            f"📱 **অন্যান্য আকর্ষণীয় কাজ:** মিনি অ্যাপে সহজে বিভিন্ন কাজ সম্পন্ন করে বড় অংকের রিওয়ার্ড লুফে নিন!\n\n"
            f"🚀 **কাজ শুরু করতে নিচের ২টি চ্যানেল ও ২টি স্পন্সর চ্যানেলে জয়েন করুন এবং 'ভেরিফাই ✅' বাটনে ক্লিক করুন!**"
        )
        
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("📢 চ্যানেল 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
        btn2 = types.InlineKeyboardButton("📢 চ্যানেল 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        btn3 = types.InlineKeyboardButton("📢 স্পন্সর 1 ", url=f"https://t.me/{SPONSOR_1.replace('@', '')}")
        btn4 = types.InlineKeyboardButton("📢 blue স্পন্সর 2 ", url=f"https://t.me/{SPONSOR_2.replace('@', '')}")
        btn_verify = types.InlineKeyboardButton("ভেরিফাই ✅", callback_data=f"verify:{referrer_id}")
        
        markup.row(btn1, btn2)
        markup.row(btn3, btn4)
        markup.row(btn_verify)

        bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        print(f"Error in start: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('verify:'))
def handle_verify(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    referrer_id = call.data.split(':')[1]
    first_name = call.from_user.first_name or ""
    last_name = call.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    try:
        try:
            status1 = bot.get_chat_member(CHANNEL_1, chat_id).status
            status2 = bot.get_chat_member(CHANNEL_2, chat_id).status
            status3 = bot.get_chat_member(SPONSOR_1, chat_id).status
            status4 = bot.get_chat_member(SPONSOR_2, chat_id).status
            
            is_joined = (status1 in ['member', 'creator', 'administrator'] and 
                         status2 in ['member', 'creator', 'administrator'] and
                         status3 in ['member', 'creator', 'administrator'] and
                         status4 in ['member', 'creator', 'administrator'])
        except Exception:
            is_joined = False

        if not is_joined:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো সবগুলো চ্যানেলে জয়েন করেননি! দয়া করে ৪টি চ্যানেলেই জয়েন করে আবার ভেরিফাই ✅ বাটনে ক্লিক করুন।", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        user_ref = db.reference(f'user/{user_id}')
        if user_ref.get():
            bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন।", reply_markup=get_home_menu())
            return

        user_data = {
            "name": full_name,
            "uid": user_id,
            "main_balance": 0,
            "pending_balance": 0,
            "completed_task": 0,
            "referred_by": referrer_id if (referrer_id != user_id and referrer_id.isdigit()) else 'direct',
            "total_refer": 0
        }

        if referrer_id != 'direct' and referrer_id != user_id and referrer_id.isdigit():
            ref_ref = db.reference(f'user/{referrer_id}')
            ref_data = ref_ref.get()

            if ref_data:
                ref_ref.update({
                    'main_balance': (ref_data.get('main_balance', 0) + 2),
                    'total_refer': (ref_data.get('total_refer', 0) + 1)
                })
                try:
                    bot.send_message(int(referrer_id), f"আপনার রেফার লিংক এ একজন জয়েন করেছে। তার uid {user_id}")
                except Exception:
                    pass

                user_ref.set(user_data)
                bot.send_message(chat_id, f"অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি কাজ করতে পারবেন।\nℹ️ আপনাকে রেফার করেছে {referrer_id}\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।", reply_markup=get_home_menu())
            else:
                user_data['referred_by'] = 'direct'
                user_ref.set(user_data)
                bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি কাজ করতে পারবেন।\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।", reply_markup=get_home_menu())
        else:
            user_ref.set(user_data)
            bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি কাজ করতে পারবেন।\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।", reply_markup=get_home_menu())

    except Exception as e:
        print(f"Error in verification: {e}")


# --- ৪. Create Account (সহজ জিমেইল অ্যাকাউন্ট সাবমিশন) ---
@bot.message_handler(func=lambda m: m.text == '➕ Create Account')
def handle_create_account(message):
    chat_id = message.chat.id
    
    text = (
        "admin এর gamil অ্যাকাউন্ট প্রয়োজন জিমেইল তৈরি করে ইনকাম করতে পারবেন।\n\n"
        "Rate 12 টাকা প্রতি অ্যাকাউন্ট\n"
        "পাসওয়ার্ড @topsell#& ব্যবহার করতে হবে না হলে বাতিল করা হবে।"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("I Agree", callback_data="agree:admin"),
        types.InlineKeyboardButton("Back", callback_data="back_to_home_menu")
    )
    bot.send_message(chat_id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('agree:'))
def handle_agree(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
        
    user_states[chat_id] = {
        'step': 'admin_get_gmail'
    }
    start_timeout_timer(chat_id, 300)
    bot.send_message(chat_id, "Gmail এর username দিন (শেষে অবশ্যই @gmail.com হতে হবে):")


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_home_menu')
def back_to_home_menu(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    bot.delete_message(chat_id, call.message.message_id)
    bot.send_message(chat_id, "আপনি হোম এ চলে এসেছেন।", reply_markup=get_home_menu())


# --- ৫. Task ক্যাটাগরি এবং Mini App ইন্টিগ্রেশন ---
@bot.message_handler(func=lambda m: m.text == '📋 Task')
def handle_view_tasks(message):
    chat_id = message.chat.id
    
    text = "আপনি কি ধরনের কাজ করতে চান তা সিলেক্ট করুন।"
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Link Visit", callback_data="task_category:link_visit"),
        types.InlineKeyboardButton("Watch AD", callback_data="task_category:watch_ad")
    )
    markup.row(
        types.InlineKeyboardButton("Other Task", callback_data="task_category:other")
    )
    bot.send_message(chat_id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('task_category:'))
def handle_task_category(call):
    chat_id = call.message.chat.id
    category = call.data.split(':')[1]
    bot.answer_callback_query(call.id)
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
        
    if category == 'other':
        text = "অন্যান্য কাজ করতে নিচে Work এ ক্লিক করুন।"
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Work 💼", web_app=types.WebAppInfo(url="https://earnglow.shop/others.html"))
        )
        bot.send_message(chat_id, text, reply_markup=markup)
    elif category == 'link_visit':
        text = "link visit করে আপনার ইনকাম বাড়িয়ে নিন। নিচে থাকা Visit এর মধ্যে ক্লিক করুন।"
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Visit 🌐", web_app=types.WebAppInfo(url="https://earnglow.shop/link.html"))
        )
        bot.send_message(chat_id, text, reply_markup=markup)
    elif category == 'watch_ad':
        text = "বিভিন্ন ধরনের বিজ্ঞাপন দেখে আয় করুন। নিচে থাকা watch button এ ক্লিক করুন। আর বিজ্ঞাপন দেখুন।"
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Watch 📺", web_app=types.WebAppInfo(url="https://earnglow.shop/watch.html"))
        )
        bot.send_message(chat_id, text, reply_markup=markup)


# --- 👥 রেফার ও ৬. ড্যাশবোর্ড/সাপোর্ট এবং সুন্দর মেসেজ প্রেজেন্টেশন ---
@bot.message_handler(func=lambda m: m.text in ['📢 Sponsor Now', '📊 Dashboard', '🤝 Support', '👨‍💻 Developer Profile', '👥 Refer'])
def handle_menu_buttons(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text

    clear_user_state(chat_id)

    try:
        user_data = db.reference(f'user/{user_id}').get() or {}

        if text == '📊 Dashboard':
            completed_tasks = user_data.get('completed_task', 0)
            
            dashboard_text = (
                f"📊 **আপনার EARN MONEY BD ড্যাশবোর্ড** 📊\n\n"
                f"👤 **নাম:** {user_data.get('name', 'N/A')}\n"
                f"🆔 **ইউজার আইডি (UID):** `{user_id}`\n"
                f"👥 **টোটাল রেফার:** {user_data.get('total_refer', 0)} জন\n\n"
                f"💰 **মেইন ব্যালেন্স:** {user_data.get('main_balance', 0)} টাকা\n"
                f"⏳ **পেন্ডিং ব্যালেন্স:** {user_data.get('pending_balance', 0)} টাকা\n"
                f"✅ **টোটাল কমপ্লিট টাস্ক:** {completed_tasks} টি"
            )
            bot.send_message(chat_id, dashboard_text, reply_markup=get_home_menu(), parse_mode="Markdown")

        elif text == '📢 Sponsor Now':
            sponsor_text = (
                f"📢 **বিজ্ঞাপন ও স্পন্সরশিপ অফার** 📢\n\n"
                f"আপনার ব্র্যান্ড, কিংবা ওয়েবসাইটের প্রচারণা আমাদের বটের মাধ্যমে ইউজারের কাছে পৌঁছে দিন! আমাদের রয়েছে অত্যন্ত সক্রিয় ইউজার বেস।\n\n"
                f"🤝 **স্পন্সর বা বিজ্ঞাপনের জন্য সরাসরি যোগাযোগ করুন:**\n"
                f"👉 **অ্যাডমিন:** @Rayhankabirooo\n\n"
                f"*আপনার ব্যবসায়িক প্রচারণায় আমরা সবসময় পাশে আছি!*"
            )
            bot.send_message(chat_id, sponsor_text, parse_mode="Markdown")

        elif text == '🤝 Support':
            support_text = (
                f"🤝 **EARN MONEY BD - সাপোর্ট সেন্টার** 🤝\n"
                f"উইথড্র কিংবা কাজ সংক্রান্ত যেকোনো সমস্যায় আমরা সবসময় আপনার পাশে আছি।\n\n"
                f"🛠️ **যেকোনো প্রয়োজনে সরাসরি ডেভেলপার রায়হান কবিরের সাথে যোগাযোগ করুন:**\n"
                f"👉 **ডেভেলপার সাপোর্ট:** @Rayhankabirooo\n\n"
                f"*আমরা ২৪ ঘণ্টার মধ্যে আপনার সমস্যা সমাধান করার চেষ্টা করব।*"
            )
            bot.send_message(chat_id, support_text, parse_mode="Markdown")

        elif text == '👨‍💻 Developer Profile':
            dev_text = (
                f"👨‍💻 **RAYBIL ডেভেলপার প্রোফাইল** 👨‍💻\n\n"
                f"🤖 **আমাদের সার্ভিসসমূহ:**\n"
                f"টেলিগ্রাম আর্নিং বট, ইনভেস্টমেন্ট বট, প্রফেশনাল ওয়েবসাইট (ই-কমার্স, ব্লগ, অফিশিয়াল সাইট) এবং প্রফেশনাল অ্যান্ড্রোয়েড অ্যাপ তৈরি করতে আমাদের সাথে যোগাযোগ করুন!\n\n"
                f"👉 **ডেভেলপার:** @Rayhankabirooo\n"
                f"👉 **RAYBIL টিম সাপোর্ট:** @Raybilsupport\n\n"
                f"*সর্বোত্তম কোয়ালিটি ও দ্রুত সার্ভিসের নিশ্চয়তা আমরা দিচ্ছি।*"
            )
            bot.send_message(chat_id, dev_text, parse_mode="Markdown")

        elif text == '👥 Refer':
            bot_info = bot.get_me()
            refer_link = f"https://t.me/{bot_info.username}?start={user_id}"
            
            refer_text = (
                f"👥 **EARN MONEY BD - রেফারেল সেন্টার** 👥\n\n"
                f"🎁 **রেফারেল বোনাস:** প্রতি সফল রেফারে পাচ্ছেন **২ টাকা** নগদ বোনাস!\n"
                f"👉 **আপনার মোট রেফার সংখ্যা:** `{user_data.get('total_refer', 0)}` জন\n\n"
                f"🔗 **আপনার ইউনিক রেফারেল লিংক:**\n"
                f"`{refer_link}`\n\n"
                f"*উপরের রেফারেল লিংকটি কপি করে আপনার বন্ধুদের মাঝে শেয়ার করে এখনই আনলিমিটেড টাকা ইনকাম শুরু করুন!*"
            )
            bot.send_message(chat_id, refer_text, parse_mode="Markdown")

    except Exception as e:
        print(f"Error handling menu button {text}: {e}")


# --- ৭. উইথড্রয়াল গেটওয়ে এবং কন্ডিশন সেটআপ (সহজ মেইন ব্যালেন্স উইথড্রয়াল) ---
@bot.message_handler(func=lambda m: m.text == '💳 Withdrawal')
def handle_withdrawal(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        total_refer = user_data.get('total_refer', 0)
        
        # পরিবর্তন: উইথড্র করতে মিনিমাম ২টা রেফার থাকতেই হবে (সকল উইথড্র মেথডের জন্য প্রযোজ্য)
        if total_refer < 2:
            msg = (
                "❌ উইথড্র করতে মিনিমাম 2 টা রেফার লাগবে। "
                "আমরা চেক করতে চাই আপনি সিরিয়াস কাজ করেছেন কি না যে কষ্ট করে কাজ করতে পারে সে মাত্র 2 টা রেফার অনায়াসে করতে পারবে।"
            )
            bot.send_message(chat_id, msg)
            return

        main_balance = user_data.get('main_balance', 0)
        
        # মোবাইল রিচার্জ ২০ টাকা এবং অন্যান্য মেথডে ৩০ টাকা উইথড্র করা যাবে
        if main_balance < 20:
            bot.send_message(chat_id, "❌ আপনার ব্যালেন্স এ পর্যাপ্ত টাকা নেই। উইথড্র করার জন্য মিনিমাম ২০ টাকা ব্যালেন্স লাগবে।")
        else:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("বিকাশ (ফি ৫৳)", callback_data="withdraw_method:Bkash"),
                types.InlineKeyboardButton("নগদ (ফি ৫৳)", callback_data="withdraw_method:Nagad")
            )
            markup.row(
                types.InlineKeyboardButton("মোবাইল রিচার্জ (ফি ০৳)", callback_data="withdraw_method:Recharge")
            )
            markup.row(
                types.InlineKeyboardButton("TON Wallet (ফি ৫৳)", callback_data="withdraw_method:TON")
            )
            bot.send_message(chat_id, "উইথড্র করার পেমেন্ট গেটওয়ে সিলেক্ট করুন:", reply_markup=markup)
            
    except Exception as e:
        print(f"Error checking withdrawal: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_method:'))
def select_withdraw_method(call):
    chat_id = call.message.chat.id
    method = call.data.split(':')[1]
    user_id = str(chat_id)
    bot.answer_callback_query(call.id)

    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        main_balance = user_data.get('main_balance', 0)

        if method in ['Bkash', 'Nagad']:
            if main_balance < 30:
                bot.send_message(chat_id, f"❌ {method} এ উইথড্র দিতে মিনিমাম ৩০ টাকা ব্যালেন্স লাগবে।")
            else:
                user_states[chat_id] = {
                    'step': 'withdraw_number',
                    'method': method,
                    'fee': 5
                }
                start_timeout_timer(chat_id, 120)
                bot.send_message(chat_id, f"আপনার {method} নম্বরটি দিন (সময়: ২ মিনিট):")

        elif method == 'TON':
            if main_balance < 50:
                bot.send_message(chat_id, "❌ TON ওয়ালেটে উইথড্র দিতে মিনিমাম ৫০ টাকা ব্যালেন্স লাগবে।")
            else:
                user_states[chat_id] = {
                    'step': 'withdraw_number',
                    'method': 'TON',
                    'fee': 5
                }
                start_timeout_timer(chat_id, 120)
                bot.send_message(chat_id, "আপনার TON ওয়ালেট অ্যাড্রেসটি দিন (সময়: ২ মিনিট):")

        elif method == 'Recharge':
            if main_balance < 20:
                bot.send_message(chat_id, "❌ মোবাইল রিচার্জ করতে মিনিমাম ২০ টাকা ব্যালেন্স লাগবে।")
            else:
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("Grameenphone", callback_data="operator:Grameenphone"),
                    types.InlineKeyboardButton("Robi", callback_data="operator:Robi"),
                    types.InlineKeyboardButton("Airtel", callback_data="operator:Airtel")
                )
                markup.row(
                    types.InlineKeyboardButton("Teletalk", callback_data="operator:Teletalk"),
                    types.InlineKeyboardButton("Banglalink", callback_data="operator:Banglalink"),
                    types.InlineKeyboardButton("Others", callback_data="operator:Others")
                )
                bot.send_message(chat_id, "আপনার মোবাইল অপারেটর সিলেক্ট করুন:", reply_markup=markup)

    except Exception as e:
        print(f"Error selecting withdraw method: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('operator:'))
def select_recharge_operator(call):
    chat_id = call.message.chat.id
    operator = call.data.split(':')[1]
    bot.answer_callback_query(call.id)

    user_states[chat_id] = {
        'step': 'recharge_number',
        'operator': operator
    }
    start_timeout_timer(chat_id, 120)
    bot.send_message(chat_id, f"আপনার মোবাইল নম্বরটি দিন (অপারেটর: {operator}, সময়: ২ মিনিট):")


# --- ৮. সকল ইউজার ইনপুট স্টেট ও কন্ডিশন ভ্যালিডেশন ---
@bot.message_handler(func=lambda m: m.chat.id in user_states)
def process_user_steps(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    state = user_states[chat_id]
    step = state.get('step')
    text = message.text.strip()

    if text in ['➕ Create Account', '📋 Task', '📢 Sponsor Now', '📊 Dashboard', '💳 Withdrawal', '🤝 Support', '👨‍💻 Developer Profile', '👥 Refer']:
        clear_user_state(chat_id)
        handle_menu_buttons(message)
        return

    # === বিকাশ, নগদ, এবং টন এর উইথড্র প্রসেস ===
    if step == 'withdraw_number':
        state['number'] = text
        state['step'] = 'withdraw_amount'
        start_timeout_timer(chat_id, 60)
        min_limit = 30 if state['method'] != 'TON' else 50
        bot.send_message(chat_id, f"কত টাকা উইথড্র করতে চান লিখুন (মিনিমাম {min_limit} টাকা হতে হবে):")

    elif step == 'withdraw_amount':
        try:
            amount = int(text)
        except ValueError:
            bot.send_message(chat_id, "দয়া করে সঠিক সংখ্যায় অ্যামাউন্ট দিন:")
            return

        min_limit = 30 if state['method'] != 'TON' else 50
        if amount < min_limit:
            bot.send_message(chat_id, f"❌ উইথড্র করার মিনিমাম অ্যামাউন্ট {min_limit} টাকা। আবার লিখুন:")
            return

        if 'timer' in state:
            state['timer'].cancel()

        try:
            user_ref = db.reference(f'user/{user_id}')
            user_data = user_ref.get() or {}
            main_balance = user_data.get('main_balance', 0)

            if main_balance < amount or amount <= 0:
                bot.send_message(chat_id, "❌ আপনার মেইন ব্যালেন্স এ পর্যাপ্ত টাকা নেই।")
            else:
                user_ref.update({
                    'main_balance': main_balance - amount
                })

                # উইথড্র ডাটা সরাসরি withdrow নোডে জমা হচ্ছে
                db.reference('withdrow').push({
                    'uid': user_id,
                    'method': state['method'],
                    'number': state['number'],
                    'amount': amount,
                    'status': 'pending',
                    'fee': state.get('fee', 0),
                    'type': 'withdraw'
                })

                fee_msg = f" (উইথড্র ফি {state['fee']} টাকা কেটে নেওয়া হবে)" if state.get('fee', 0) > 0 else ""
                bot.send_message(chat_id, f"আপনার {amount} টাকা উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে।{fee_msg}। এডমিন দ্রুত পেমেন্ট কমপ্লিট করবে।")

        except Exception as e:
            print(f"Error processing main withdraw: {e}")
            bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")

        clear_user_state(chat_id)

    # === মোবাইল রিচার্জ ইনপুট প্রসেস ===
    elif step == 'recharge_number':
        state['number'] = text
        state['step'] = 'recharge_amount'
        start_timeout_timer(chat_id, 60)
        bot.send_message(chat_id, "কত টাকা মোবাইল রিচার্জ করতে চান লিখুন (মিনিমাম ২০ টাকা):")

    elif step == 'recharge_amount':
        try:
            amount = int(text)
        except ValueError:
            bot.send_message(chat_id, "দয়া করে সঠিক সংখ্যায় অ্যামাউন্ট দিন:")
            return

        if amount < 20:
            bot.send_message(chat_id, "❌ মিনিমাম রিচার্জের পরিমাণ ২০ টাকা। আবার লিখুন:")
            return

        if 'timer' in state:
            state['timer'].cancel()

        try:
            user_ref = db.reference(f'user/{user_id}')
            user_data = user_ref.get() or {}
            main_balance = user_data.get('main_balance', 0)

            if main_balance < amount or amount <= 0:
                bot.send_message(chat_id, "❌ আপনার মেইন ব্যালেন্স এ পর্যাপ্ত টাকা নেই।")
            else:
                user_ref.update({
                    'main_balance': main_balance - amount
                })

                db.reference('withdrow').push({
                    'uid': user_id,
                    'method': 'Mobile Recharge',
                    'operator': state['operator'],
                    'number': state['number'],
                    'amount': amount,
                    'status': 'pending',
                    'fee': 0,
                    'type': 'withdraw'
                })

                bot.send_message(chat_id, f"আপনার {amount} টাকা মোবাইল রিচার্জ রিকোয়েস্ট সফলভাবে জমা হয়েছে। কোনো চার্জ কাটা হয়নি।")

        except Exception as e:
            print(f"Error processing recharge withdraw: {e}")
            bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")

        clear_user_state(chat_id)

    # === অ্যাডমিন টাস্ক জিমেইল সাবমিশন প্রসেস ===
    elif step == 'admin_get_gmail':
        if not text.endswith('@gmail.com'):
            bot.send_message(chat_id, "❌ ভুল ইউজারনেম! শেষে অবশ্যই @gmail.com থাকতে হবে। আবার চেষ্টা করুন:")
            return
            
        state['gmail'] = text
        state['step'] = 'admin_get_password'
        start_timeout_timer(chat_id, 300)
        bot.send_message(chat_id, "পাসওয়ার্ড দিন (অবশ্যই @topsell#& হতে হবে):")

    elif step == 'admin_get_password':
        if text != '@topsell#&':
            bot.send_message(chat_id, "❌ ভুল পাসওয়ার্ড! পাসওয়ার্ড হুবহু @topsell#& হতে হবে। আবার চেষ্টা করুন:")
            return
            
        if 'timer' in state:
            state['timer'].cancel()

        try:
            safe_gmail = state['gmail'].replace('.', '_').replace('@', '_at_')
            
            db.reference(f'submit/admin/{safe_gmail}').set({
                'uid': user_id,
                'username': state['gmail'],
                'pass': text,
                'status': 'pending'
            })
            
            user_ref = db.reference(f'user/{user_id}')
            user_data = user_ref.get() or {}
            current_pending = user_data.get('pending_balance', 0)
            user_ref.update({
                'pending_balance': current_pending + 12
            })

            bot.send_message(chat_id, "আপনার কাজ সফল ভাবে সাবমিট করা হয়েছে। এডমিন রিভিউ করে ২৪ ঘণ্টার মধ্যে আপনাকে জানানো হবে।", reply_markup=get_home_menu())
        except Exception as e:
            print(f"Error saving admin task: {e}")
            bot.send_message(chat_id, "সাবমিট করতে সমস্যা হয়েছে, আবার চেষ্টা করুন।", reply_markup=get_home_menu())
            
        clear_user_state(chat_id)


# ইনলাইন বাটন থেকে হোম মেনুতে ফিরে যাওয়া
@bot.callback_query_handler(func=lambda call: call.data == "back_to_home")
def back_to_home(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    clear_user_state(chat_id)
    bot.send_message(chat_id, "মূল হোম মেনু সিলেক্ট করুন।", reply_markup=get_home_menu())


if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
