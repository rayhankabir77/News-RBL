import os
import json
import threading
import hmac
import hashlib
import urllib.parse
from flask import Flask, request, Response
from telebot import TeleBot, types
import firebase_admin
from firebase_admin import credentials, db

# --- ১. ফায়ারবেস ও টেলিগ্রাম এনভায়রনমেন্ট কনফিগারেশন ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTDB_URL = os.getenv("RTDB_URL")
FIREBASE_ADMIN_ENV = os.getenv("FIREBASE_ADMIN")

if not BOT_TOKEN or not RTDB_URL or not FIREBASE_ADMIN_ENV:
    raise ValueError("Error: Required environment variables are missing!")

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

# ২টি রিকোয়ার্ড চ্যানেল
CHANNEL_1 = '@raybilofficial'
CHANNEL_2 = '@earnglowofficial'

user_states = {}

# --- ২. মাল্টি-ল্যাঙ্গুয়েজ রিসোর্স ডিকশনারি (English & Bangla) ---
TEXTS = {
    'en': {
        'welcome_msg': "🚀 **Welcome to EARN MONEY BD!** 🚀\n\nEarn unlimited RBL easily using your mobile phone! 💰\n\n📢 **Join our 2 channels below and click 'Verify ✅' to start!**",
        'join_chan_1': "📢 Channel 1",
        'join_chan_2': "📢 Channel 2",
        'verify_btn': "Verify ✅",
        'not_joined': "❌ You have not joined all channels! Please join both channels and try again.",
        'verified_success': "Congratulations 🎉, you have successfully verified. You can now start earning!",
        'verified_referred': "Congratulations 🎉, you have successfully verified.\nℹ️ You were referred by {referrer_id}\n\nPlease select an option below.",
        'home_msg': "Welcome to the Home Menu.",
        'dashboard': (
            "📊 **Your EARN MONEY BD Dashboard** 📊\n\n"
            "👤 **Name:** {name}\n"
            "🆔 **User ID (UID):** `{uid}`\n"
            "👥 **Total Referrals:** {total_refer} users\n\n"
            "💰 **Main Balance:** {main_balance} RBL\n"
            "⏳ **Pending Balance:** {pending_balance} RBL\n"
            "✅ **Completed Tasks:** {completed_task}"
        ),
        'sponsor': (
            "📢 **Advertising & Sponsorship** 📢\n\n"
            "Promote your brand or website to our active users through our bot!\n\n"
            "🤝 **Contact Admin for sponsorship:**\n"
            "👉 **Admin:** @Rayhankabirooo"
        ),
        'support': (
            "🤝 **EARN MONEY BD - Support Center** 🤝\n"
            "For any issues with withdrawals or tasks, we are here to help.\n\n"
            "👉 **Developer Support:** @mdrayhankabirrabbil"
        ),
        'support_btn': "Message Now 💬",
        'refer': (
            "👥 **EARN MONEY BD - Referral Center** 👥\n\n"
            "🎁 **Referral Bonus:** Earn **1.75 RBL** once your referred friend verifies and earns at least **5 RBL**!\n"
            "👉 **Your Total Referrals:** `{total_refer}` users\n\n"
            "🔗 **Your Unique Referral Link:**\n"
            "`{refer_link}`\n\n"
            "*Share this link to start earning RBL!*"
        ),
        'rules_msg': "📋 To view the complete rules of EARN MONEY BD, click the button below:",
        'rules_btn': "Rules 📋",
        'task_menu': "Select the type of task you want to complete.",
        'task_link': "Link Visit 🌐",
        'task_watch': "Watch AD 📺",
        'task_other': "Other Task 💼",
        'task_link_msg': "Visit links to boost your earnings. Click below to start.",
        'task_watch_msg': "Watch ads to earn. Click below to watch.",
        'task_other_msg': "Complete other micro-tasks. Click below to start.",
        'withdraw_min_refer': "❌ You need at least 2 referrals to withdraw. We require this to ensure genuine user activity.",
        'withdraw_insufficient': "❌ Insufficient balance. You need at least {min_limit} RBL to withdraw.",
        'withdraw_gateway': "Select your payment gateway:\n*(Note: 40 RBL = $0.28)*",
        'withdraw_amount_prompt': "Enter the amount you wish to withdraw (Minimum {min_limit} RBL):",
        'withdraw_number_prompt': "Enter your {method} account/wallet address (Time limit: 2 minutes):",
        'withdraw_invalid_amount': "Please enter a valid numeric amount:",
        'withdraw_success': "Your withdrawal of {amount} RBL has been submitted successfully. A fee of {fee:.2f} RBL has been deducted. Admin will process it soon.",
        'timeout': "⏰ Time's up! Your request has been cancelled. Please try again.",
        'operator_prompt': "Select your mobile operator:"
    },
    'bn': {
        'welcome_msg': "🚀 **EARN MONEY BD বটের আকর্ষণীয় আয়ের প্ল্যাটফর্মে আপনাকে স্বাগতম 😊!** 🚀\n\nমোবাইল দিয়ে খুব সহজে আনলিমিটেড RBL আয় করুন! 💰\n\n📢 **কাজ শুরু করতে নিচের ২টি চ্যানেলে জয়েন করুন এবং 'ভেরিফাই ✅' বাটনে ক্লিক করুন!**",
        'join_chan_1': "📢 চ্যানেল 1",
        'join_chan_2': "📢 চ্যানেল 2",
        'verify_btn': "ভেরিফাই ✅",
        'not_joined': "❌ আপনি এখনো সবগুলো চ্যানেলে জয়েন করেননি! দয়া করে ২টি চ্যানেলেই জয়েন করে আবার ভেরিফাই ✅ বাটনে ক্লিক করুন।",
        'verified_success': "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি কাজ করতে পারবেন।",
        'verified_referred': "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি কাজ করতে পারবেন।\nℹ️ আপনাকে রেফার করেছে {referrer_id}\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।",
        'home_msg': "আপনি হোম মেনুতে চলে এসেছেন।",
        'dashboard': (
            "📊 **আপনার EARN MONEY BD ড্যাশবোর্ড** 📊\n\n"
            "👤 **নাম:** {name}\n"
            "🆔 **ইউজার আইডি (UID):** `{uid}`\n"
            "👥 **টোটাল রেফার:** {total_refer} জন\n\n"
            "💰 **মেইন ব্যালেন্স:** {main_balance} RBL\n"
            "⏳ **পেন্ডিং ব্যালেন্স:** {pending_balance} RBL\n"
            "✅ **টোটাল কমপ্লিট টাস্ক:** {completed_task} টি"
        ),
        'sponsor': (
            "📢 **বিজ্ঞাপন ও স্পন্সরশিপ অফার** 📢\n\n"
            "আপনার ব্র্যান্ড, কিংবা ওয়েবসাইটের প্রচারণা আমাদের বটের মাধ্যমে ইউজারের কাছে পৌঁছে দিন! আমাদের রয়েছে অত্যন্ত সক্রিয় ইউজার বেস।\n\n"
            "🤝 **স্পন্সর বা বিজ্ঞাপনের জন্য সরাসরি যোগাযোগ করুন:**\n"
            "👉 **অ্যাডমিন:** @Rayhankabirooo"
        ),
        'support': (
            "🤝 **EARN MONEY BD - সাপোর্ট সেন্টার** 🤝\n"
            "উইথড্র কিংবা কাজ সংক্রান্ত যেকোনো সমস্যায় আমরা সবসময় আপনার পাশে আছি।\n\n"
            "🛠️ **যেকোনো প্রয়োজনে সরাসরি ডেভেলপারের সাথে যোগাযোগ করুন:**\n"
            "👉 **ডেভেলপার সাপোর্ট:** @mdrayhankabirrabbil"
        ),
        'support_btn': "মেসেজ করুন 💬",
        'refer': (
            "👥 **EARN MONEY BD - রেফারেল সেন্টার** 👥\n\n"
            "🎁 **রেফারেল বোনাস:** আপনার রেফার লিংকে কেউ জয়েন করে ভেরিফাই হওয়ার পর যখন সে নিজে কমপক্ষে **৫ RBL** আয় করবে, তখন আপনি পাবেন **১.৭৫ RBL** বোনাস!\n"
            "👉 **আপনার মোট রেফার সংখ্যা:** `{total_refer}` জন\n\n"
            "🔗 **আপনার ইউনিক রেফারেল লিংক:**\n"
            "`{refer_link}`\n\n"
            "*উপরের লিংকটি কপি করে বন্ধুদের মাঝে শেয়ার করে এখনই RBL ইনকাম শুরু করুন!*"
        ),
        'rules_msg': "📋 EARN MONEY BD-এর সম্পূর্ণ নিয়মাবলী দেখতে নিচের বাটনে ক্লিক করুন:",
        'rules_btn': "নিয়মাবলী 📋",
        'task_menu': "আপনি কি ধরনের কাজ করতে চান তা সিলেক্ট করুন।",
        'task_link': "লিঙ্ক ভিজিট 🌐",
        'task_watch': "অ্যাড দেখুন 📺",
        'task_other': "অন্যান্য কাজ 💼",
        'task_link_msg': "Link visit করে আপনার ইনকাম বাড়িয়ে নিন। নিচে থাকা Visit এর মধ্যে ক্লিক করুন।",
        'task_watch_msg': "বিভিন্ন ধরনের বিজ্ঞাপন দেখে আয় করুন। নিচে থাকা watch button এ ক্লিক করুন।",
        'task_other_msg': "অন্যান্য কাজ করতে নিচে Work এ ক্লিক করুন।",
        'withdraw_min_refer': "❌ উইথড্র করতে মিনিমাম ২টা রেফার লাগবে। আমরা চেক করতে চাই আপনি সিরিয়াস কাজ করেছেন কি না।",
        'withdraw_insufficient': "❌ আপনার ব্যালেন্স এ পর্যাপ্ত টাকা নেই। উইথড্র করার জন্য মিনিমাম {min_limit} RBL ব্যালেন্স লাগবে।",
        'withdraw_gateway': "উইথড্র করার পেমেন্ট গেটওয়ে সিলেক্ট করুন:\n*(মনে রাখবেন: 40 RBL = $0.28)*",
        'withdraw_amount_prompt': "কত RBL উইথড্র করতে চান লিখুন (মিনিমাম {min_limit} RBL হতে হবে):",
        'withdraw_number_prompt': "আপনার {method} নম্বর/অ্যাড্রেসটি দিন (সময়: ২ মিনিট):",
        'withdraw_invalid_amount': "দয়া করে সঠিক সংখ্যায় অ্যামাউন্ট দিন:",
        'withdraw_success': "আপনার {amount} RBL উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে। চার্জ {fee:.2f} RBL কেটে নেওয়া হয়েছে। এডমিন দ্রুত পেমেন্ট কমপ্লিট করবে।",
        'timeout': "⏰ সময় শেষ হয়ে গেছে! আপনার রিকোয়েস্টটি বাতিল করা হয়েছে। আবার চেষ্টা করুন।",
        'operator_prompt': "আপনার মোবাইল অপারেটর সিলেক্ট করুন:"
    }
}


def get_user_lang(user_id):
    user_data = db.reference(f'user/{user_id}').get()
    if user_data and 'lang' in user_data:
        return user_data['lang']
    if user_id in user_states and 'lang' in user_states[user_id]:
        return user_states[user_id]['lang']
    return 'bn'


def get_home_menu(lang):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == 'bn':
        markup.row('📋 নিয়মাবলী (Rules)', '📋 টাস্ক (Task)')
        markup.row('📢 স্পন্সর', '📊 ড্যাশবোর্ড')
        markup.row('💳 উইথড্র', '🤝 সাপোর্ট')
        markup.row('👥 রেফার')
    else:
        markup.row('📋 Rules', '📋 Task')
        markup.row('📢 Sponsor Now', '📊 Dashboard')
        markup.row('💳 Withdrawal', '🤝 Support')
        markup.row('👥 Refer')
    return markup


# --- ৩. Flask ওয়েব সার্ভার ও সিকিউর API গেটওয়ে ---
app = Flask(__name__)

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
        action = data.get('action', '') 

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
        new_balance = current_main_balance + 1

        updates = {
            'main_balance': new_balance
        }

        # --- অ্যান্টি-অ্যাবিউস রেফারেল ট্র্যাকিং লজিক ---
        referred_by = user_data.get('referred_by', 'direct')
        refer_reward_paid = user_data.get('refer_reward_paid', False)

        # যদি ইউজার ভেরিফাইড থাকে, রেফার লিংকে এসে থাকে এবং ৫ RBL আর্ন করে, তবে রেফারার বোনাস পাবে
        if new_balance >= 5 and referred_by != 'direct' and not refer_reward_paid:
            updates['refer_reward_paid'] = True
            ref_ref = db.reference(f'user/{referred_by}')
            ref_data = ref_ref.get()
            if ref_data:
                ref_ref.update({
                    'main_balance': ref_data.get('main_balance', 0) + 1.75,
                    'total_refer': ref_data.get('total_refer', 0) + 1
                })
                try:
                    ref_lang = ref_data.get('lang', 'bn')
                    if ref_lang == 'bn':
                        notify_text = f"🎉 আপনার আমন্ত্রিত ইউজার `{userid}` ৫ RBL আয়ের মাইলফলক স্পর্শ করায় আপনি ১.৭৫ RBL রেফারেল বোনাস পেয়েছেন!"
                    else:
                        notify_text = f"🎉 Your referred user `{userid}` has earned 5 RBL, and you have received a referral bonus of 1.75 RBL!"
                    bot.send_message(int(referred_by), notify_text, parse_mode="Markdown")
                except Exception:
                    pass

        user_ref.update(updates)

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


# --- ৪. ইউজার স্টেট ক্লিয়ার ও টাইমার হেল্পার ---
def clear_user_state(chat_id, notify_timeout=False):
    state = user_states.pop(chat_id, None)
    if state:
        timer = state.get('timer')
        if timer:
            timer.cancel()
        if notify_timeout:
            try:
                lang = get_user_lang(str(chat_id))
                bot.send_message(chat_id, TEXTS[lang]['timeout'])
            except Exception as e:
                print(f"Error sending timeout msg: {e}")

def start_timeout_timer(chat_id, seconds):
    if chat_id in user_states and 'timer' in user_states[chat_id]:
        user_states[chat_id]['timer'].cancel()
        
    timer = threading.Timer(seconds, clear_user_state, args=[chat_id, True])
    timer.start()
    if chat_id in user_states:
        user_states[chat_id]['timer'] = timer


# --- ৫. স্টার্ট হ্যান্ডলার ও ল্যাঙ্গুয়েজ সিলেকশন গেটওয়ে ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    parts = message.text.split()
    referrer_id = parts[1] if len(parts) > 1 else 'direct'

    try:
        user_ref = db.reference(f'user/{user_id}')
        user_snapshot = user_ref.get()

        if user_snapshot:
            lang = user_snapshot.get('lang', 'bn')
            bot.send_message(chat_id, TEXTS[lang]['home_msg'], reply_markup=get_home_menu(lang))
            return

        # নতুন ইউজারদের ভাষা পছন্দ করার স্ক্রিন
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("ENGLISH 🇬🇧", callback_data=f"set_lang:en:{referrer_id}"),
            types.InlineKeyboardButton("BANGLA 🇧🇩", callback_data=f"set_lang:bn:{referrer_id}")
        )
        bot.send_message(chat_id, "CHOOSE YOUR LANGUAGE / ভাষা নির্বাচন করুন", reply_markup=markup)

    except Exception as e:
        print(f"Error in start: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang:'))
def handle_set_lang(call):
    chat_id = call.message.chat.id
    parts = call.data.split(':')
    lang = parts[1]
    referrer_id = parts[2]
    bot.answer_callback_query(call.id)
    
    if chat_id not in user_states:
        user_states[chat_id] = {}
    user_states[chat_id]['lang'] = lang
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
        
    welcome_text = TEXTS[lang]['welcome_msg']
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton(TEXTS[lang]['join_chan_1'], url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
    btn2 = types.InlineKeyboardButton(TEXTS[lang]['join_chan_2'], url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
    btn_verify = types.InlineKeyboardButton(TEXTS[lang]['verify_btn'], callback_data=f"verify:{referrer_id}")
    
    markup.row(btn1, btn2)
    markup.row(btn_verify)
    
    bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith('verify:'))
def handle_verify(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    referrer_id = call.data.split(':')[1]
    first_name = call.from_user.first_name or ""
    last_name = call.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    lang = get_user_lang(user_id)

    try:
        try:
            status1 = bot.get_chat_member(CHANNEL_1, chat_id).status
            status2 = bot.get_chat_member(CHANNEL_2, chat_id).status
            
            is_joined = (status1 in ['member', 'creator', 'administrator'] and 
                         status2 in ['member', 'creator', 'administrator'])
        except Exception:
            is_joined = False

        if not is_joined:
            bot.answer_callback_query(call.id, TEXTS[lang]['not_joined'], show_alert=True)
            return

        bot.answer_callback_query(call.id)

        user_ref = db.reference(f'user/{user_id}')
        if user_ref.get():
            bot.send_message(chat_id, TEXTS[lang]['verified_success'], reply_markup=get_home_menu(lang))
            return

        valid_referrer = 'direct'
        if referrer_id != 'direct' and referrer_id != user_id and referrer_id.isdigit():
            ref_ref = db.reference(f'user/{referrer_id}')
            if ref_ref.get():
                valid_referrer = referrer_id

        user_data = {
            "name": full_name,
            "uid": user_id,
            "main_balance": 0,
            "pending_balance": 0,
            "completed_task": 0,
            "referred_by": valid_referrer,
            "refer_reward_paid": False,
            "total_refer": 0,
            "lang": lang
        }
        
        user_ref.set(user_data)
        
        if valid_referrer != 'direct':
            bot.send_message(chat_id, TEXTS[lang]['verified_referred'].format(referrer_id=valid_referrer), reply_markup=get_home_menu(lang))
        else:
            bot.send_message(chat_id, TEXTS[lang]['verified_success'], reply_markup=get_home_menu(lang))

    except Exception as e:
        print(f"Error in verification: {e}")


# --- ৬. টাস্ক ও মিনি অ্যাপ রিডাইরেকশনস ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('task_category:'))
def handle_task_category(call):
    chat_id = call.message.chat.id
    category = call.data.split(':')[1]
    user_id = str(chat_id)
    bot.answer_callback_query(call.id)
    
    lang = get_user_lang(user_id)
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
        
    if category == 'other':
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Work 💼", web_app=types.WebAppInfo(url="https://earnglow.shop/others.html"))
        )
        bot.send_message(chat_id, TEXTS[lang]['task_other_msg'], reply_markup=markup)
    elif category == 'link_visit':
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Visit 🌐", web_app=types.WebAppInfo(url="https://earnglow.shop/link.html"))
        )
        bot.send_message(chat_id, TEXTS[lang]['task_link_msg'], reply_markup=markup)
    elif category == 'watch_ad':
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Watch 📺", web_app=types.WebAppInfo(url="https://earnglow.shop/watch.html"))
        )
        bot.send_message(chat_id, TEXTS[lang]['task_watch_msg'], reply_markup=markup)


# --- ৭. উইথড্রয়াল মেথড কন্ডিশন সিলেকশন ---
def handle_withdrawal_action(message, lang):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        total_refer = user_data.get('total_refer', 0)
        
        if total_refer < 2:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_min_refer'])
            return

        main_balance = user_data.get('main_balance', 0)
        
        if main_balance < 40:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_insufficient'].format(min_limit=40))
        else:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("Bkash (Bkash)", callback_data="withdraw_method:Bkash"),
                types.InlineKeyboardButton("Nagad (Nagad)", callback_data="withdraw_method:Nagad")
            )
            markup.row(
                types.InlineKeyboardButton("Mobile Recharge", callback_data="withdraw_method:Recharge")
            )
            markup.row(
                types.InlineKeyboardButton("TON Wallet (TON)", callback_data="withdraw_method:TON")
            )
            bot.send_message(chat_id, TEXTS[lang]['withdraw_gateway'], reply_markup=markup, parse_mode="Markdown")
            
    except Exception as e:
        print(f"Error checking withdrawal: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_method:'))
def select_withdraw_method(call):
    chat_id = call.message.chat.id
    method = call.data.split(':')[1]
    user_id = str(chat_id)
    bot.answer_callback_query(call.id)
    
    lang = get_user_lang(user_id)

    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        main_balance = user_data.get('main_balance', 0)
        
        min_limit = 50 if method == 'TON' else 40

        if main_balance < min_limit:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_insufficient'].format(min_limit=min_limit))
            return

        if method in ['Bkash', 'Nagad', 'TON']:
            user_states[chat_id] = {
                'step': 'withdraw_number',
                'method': method,
                'min_limit': min_limit
            }
            start_timeout_timer(chat_id, 120)
            bot.send_message(chat_id, TEXTS[lang]['withdraw_number_prompt'].format(method=method))

        elif method == 'Recharge':
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
            bot.send_message(chat_id, TEXTS[lang]['operator_prompt'], reply_markup=markup)

    except Exception as e:
        print(f"Error selecting withdraw method: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('operator:'))
def select_recharge_operator(call):
    chat_id = call.message.chat.id
    operator = call.data.split(':')[1]
    user_id = str(chat_id)
    bot.answer_callback_query(call.id)
    
    lang = get_user_lang(user_id)

    user_states[chat_id] = {
        'step': 'recharge_number',
        'operator': operator,
        'method': 'Mobile Recharge',
        'min_limit': 40
    }
    start_timeout_timer(chat_id, 120)
    
    if lang == 'bn':
        prompt = f"আপনার মোবাইল নম্বরটি দিন (অপারেটর: {operator}, সময়: ২ মিনিট):"
    else:
        prompt = f"Enter your mobile number (Operator: {operator}, Time: 2 minutes):"
    bot.send_message(chat_id, prompt)


# --- ৮. সকল টেক্সট মেসেজ ও ইনপুট ভ্যালিডেশন হ্যান্ডলার ---
@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text.strip()
    
    # ইউজার কোনো অ্যাক্টিভ ইনপুট স্টেটে থাকলে তা প্রসেস করবে
    if chat_id in user_states and 'step' in user_states[chat_id]:
        process_user_steps(message)
        return

    lang = get_user_lang(user_id)
    
    # মেনু বাটনগুলোকে রি-ডাইরেক্ট করা
    menu_actions = {
        '📋 Rules': 'rules',
        '📋 নিয়মাবলী (Rules)': 'rules',
        
        '📋 Task': 'task',
        '📋 টাস্ক (Task)': 'task',
        
        '📢 Sponsor Now': 'sponsor',
        '📢 স্পন্সর': 'sponsor',
        
        '📊 Dashboard': 'dashboard',
        '📊 ড্যাশবোর্ড': 'dashboard',
        
        '💳 Withdrawal': 'withdraw',
        '💳 উইথড্র': 'withdraw',
        
        '🤝 Support': 'support',
        '🤝 সাপোর্ট': 'support',
        
        '👥 Refer': 'refer',
        '👥 রেফার': 'refer'
    }
    
    action = menu_actions.get(text)
    if not action:
        return 

    clear_user_state(chat_id)
    
    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        
        if action == 'dashboard':
            completed_tasks = user_data.get('completed_task', 0)
            dashboard_text = TEXTS[lang]['dashboard'].format(
                name=user_data.get('name', 'N/A'),
                uid=user_id,
                total_refer=user_data.get('total_refer', 0),
                main_balance=user_data.get('main_balance', 0),
                pending_balance=user_data.get('pending_balance', 0),
                completed_task=completed_tasks
            )
            bot.send_message(chat_id, dashboard_text, reply_markup=get_home_menu(lang), parse_mode="Markdown")
            
        elif action == 'rules':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(TEXTS[lang]['rules_btn'], url="https://t.me/earnglowofficial/6"))
            bot.send_message(chat_id, TEXTS[lang]['rules_msg'], reply_markup=markup, parse_mode="Markdown")
            
        elif action == 'task':
            text_msg = TEXTS[lang]['task_menu']
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton(TEXTS[lang]['task_link'], callback_data="task_category:link_visit"),
                types.InlineKeyboardButton(TEXTS[lang]['task_watch'], callback_data="task_category:watch_ad")
            )
            markup.row(
                types.InlineKeyboardButton(TEXTS[lang]['task_other'], callback_data="task_category:other")
            )
            bot.send_message(chat_id, text_msg, reply_markup=markup)

        elif action == 'sponsor':
            bot.send_message(chat_id, TEXTS[lang]['sponsor'], parse_mode="Markdown")

        elif action == 'support':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(TEXTS[lang]['support_btn'], url="https://t.me/mdrayhankabirrabbil"))
            bot.send_message(chat_id, TEXTS[lang]['support'], reply_markup=markup, parse_mode="Markdown")

        elif action == 'refer':
            bot_info = bot.get_me()
            refer_link = f"https://t.me/{bot_info.username}?start={user_id}"
            refer_text = TEXTS[lang]['refer'].format(
                total_refer=user_data.get('total_refer', 0),
                refer_link=refer_link
            )
            bot.send_message(chat_id, refer_text, parse_mode="Markdown")
            
        elif action == 'withdraw':
            handle_withdrawal_action(message, lang)
            
    except Exception as e:
        print(f"Error handling menu button {text}: {e}")


def process_user_steps(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    state = user_states[chat_id]
    step = state.get('step')
    text = message.text.strip()
    lang = get_user_lang(user_id)

    # ইউজার কোনো কারণে অন্য মেনু বাটনে প্রেস করলে স্টেট ক্যান্সেল করে সেখানে চলে যাবে
    main_menu_commands = [
        '📋 Rules', '📋 Task', '📢 Sponsor Now', '📊 Dashboard', '💳 Withdrawal', '🤝 Support', '👥 Refer',
        '📋 নিয়মাবলী (Rules)', '📋 টাস্ক (Task)', '📢 স্পন্সর', '📊 ড্যাশবোর্ড', '💳 উইথড্র', '🤝 সাপোর্ট', '👥 রেফার'
    ]
    if text in main_menu_commands:
        user_states.pop(chat_id, None)
        handle_text_messages(message)
        return

    # === withdraw_number step ===
    if step == 'withdraw_number':
        state['number'] = text
        state['step'] = 'withdraw_amount'
        start_timeout_timer(chat_id, 60)
        bot.send_message(chat_id, TEXTS[lang]['withdraw_amount_prompt'].format(min_limit=state['min_limit']))

    # === withdraw_amount step ===
    elif step == 'withdraw_amount':
        try:
            amount = float(text)
        except ValueError:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_invalid_amount'])
            return

        min_limit = state['min_limit']
        if amount < min_limit:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_insufficient'].format(min_limit=min_limit))
            return

        if 'timer' in state:
            state['timer'].cancel()

        try:
            user_ref = db.reference(f'user/{user_id}')
            user_data = user_ref.get() or {}
            main_balance = user_data.get('main_balance', 0)

            if main_balance < amount or amount <= 0:
                bot.send_message(chat_id, TEXTS[lang]['withdraw_insufficient'].format(min_limit=min_limit))
            else:
                user_ref.update({
                    'main_balance': main_balance - amount
                })

                # চার্জ হিসাব: ৮০ বা তার বেশি হলে চার্জ ৮ + ৩%, আর কম হলে চার্জ ৮ RBL
                if amount >= 80:
                    fee = 8 + (amount * 0.03)
                else:
                    fee = 8

                db.reference('withdraw').push({
                    'uid': user_id,
                    'method': state['method'],
                    'number': state['number'],
                    'amount': amount,
                    'status': 'pending',
                    'fee': fee,
                    'type': 'withdraw'
                })

                bot.send_message(chat_id, TEXTS[lang]['withdraw_success'].format(amount=amount, fee=fee))

        except Exception as e:
            print(f"Error processing withdraw: {e}")
            if lang == 'bn':
                bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")
            else:
                bot.send_message(chat_id, "Something went wrong while processing your withdrawal, please try again later.")

        clear_user_state(chat_id)

    # === recharge_number step ===
    elif step == 'recharge_number':
        state['number'] = text
        state['step'] = 'recharge_amount'
        start_timeout_timer(chat_id, 60)
        bot.send_message(chat_id, TEXTS[lang]['withdraw_amount_prompt'].format(min_limit=40))

    # === recharge_amount step ===
    elif step == 'recharge_amount':
        try:
            amount = float(text)
        except ValueError:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_invalid_amount'])
            return

        if amount < 40:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_insufficient'].format(min_limit=40))
            return

        if 'timer' in state:
            state['timer'].cancel()

        try:
            user_ref = db.reference(f'user/{user_id}')
            user_data = user_ref.get() or {}
            main_balance = user_data.get('main_balance', 0)

            if main_balance < amount or amount <= 0:
                bot.send_message(chat_id, TEXTS[lang]['withdraw_insufficient'].format(min_limit=40))
            else:
                user_ref.update({
                    'main_balance': main_balance - amount
                })

                if amount >= 80:
                    fee = 8 + (amount * 0.03)
                else:
                    fee = 8

                db.reference('withdraw').push({
                    'uid': user_id,
                    'method': 'Mobile Recharge',
                    'operator': state['operator'],
                    'number': state['number'],
                    'amount': amount,
                    'status': 'pending',
                    'fee': fee,
                    'type': 'withdraw'
                })

                bot.send_message(chat_id, TEXTS[lang]['withdraw_success'].format(amount=amount, fee=fee))

        except Exception as e:
            print(f"Error processing recharge: {e}")
            if lang == 'bn':
                bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")
            else:
                bot.send_message(chat_id, "Something went wrong while processing your withdrawal, please try again later.")

        clear_user_state(chat_id)


if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
