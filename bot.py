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

# --- ২. ইংরেজি বাটন ও টেক্সট কনফিগারেশন ---
TEXTS = {
    'welcome_msg': (
        "🚀 Welcome to EARNGLOW! 🚀\n\n"
        "Start earning unlimited EGW currency effortlessly, right from your mobile phone! 💰 "
        "This is a premier and secure platform designed to help you generate a steady digital income on the go.\n\n"
        "How to Start:\n"
        "Simply join our 2 official channels listed below and tap the 'Verify ✅' button to activate your account and begin your earning journey!"
    ),
    'not_joined': (
        "❌ Oops!\n"
        "You haven't joined all our channels yet. Please join all the required channels first and then click the 'Verify ✅' button again. Thank you!"
    ),
    'verified_success': (
        "🎉 Congratulations! 🎉\n"
        "Your account has been successfully verified. You are now fully authorized to start completing tasks and earning EGW currency."
    ),
    'verified_referred': (
        "🎉 Congratulations! 🎉\n"
        "Your account has been successfully verified! You are now fully authorized to start completing tasks and earning EGW currency.\n\n"
        "ℹ️ Referred By: {referrer_id}\n\n"
        "👇 Please select your required option from the menu below:"
    ),
    'home_msg': "Welcome to the Home Menu.",
    'dashboard': (
        "📊 **Your EARNGLOW Dashboard** 📊\n\n"
        "👤 **Name:** {name}\n"
        "🆔 **User ID (UID):** `{uid}`\n"
        "👥 **Active Referrals:** {active_refer} users\n"
        "⏳ **Pending Referrals:** {pending_refer} users\n\n"
        "💰 **Main Balance:** {main_balance} EGW\n"
        "⏳ **Pending Balance:** {pending_balance} EGW\n"
        "✅ **Completed Tasks:** {completed_task}"
    ),
    'sponsor': (
        "📢 Advertising & Sponsorship Offers! 📢\n\n"
        "Promote your business, brand, Telegram channel, or website directly to all active users through our bot! 📈 "
        "We have a highly active and fast-growing user base, ensuring maximum exposure and rapid growth for your project. 🚀\n\n"
        "🎯 Why Choose Us?\n"
        "👥 100% real and highly active users.\n"
        "⚡️ Instant notifications delivered to all users simultaneously.\n"
        "📊 High conversion rates at the most affordable pricing.\n\n"
        "🤝 For sponsorships or advertising inquiries, contact us directly:"
    ),
    'support': (
        "🤝 EARNGLOW - Support Center 🤝\n\n"
        "Whether it's about withdrawals or task-related issues, we are always here to assist you! Our team is dedicated to resolving your problems as quickly as possible. ⚡️\n\n"
        "🛠️ For any assistance, contact our helpdesk directly:\n"
        "👉 Official Customer Support:"
    ),
    'refer': (
        "👥 **EARNGLOW - Referral Center** 👥\n\n"
        "🎁 **Referral Bonus:** Earn **1.75 EGW** once your referred friend verifies and earns at least **5 EGW** on their own!\n\n"
        "👉 **Active Referrals:** `{active_refer}` users\n"
        "⏳ **Pending Referrals:** `{pending_refer}` users\n\n"
        "🔗 **Your Unique Referral Link:**\n"
        "`{refer_link}`\n\n"
        "*Share this link to start earning EGW!*"
    ),
    'rules_msg': (
        "📋 **EARNGLOW Rules & Regulations** 📋\n\n"
        "Please select a category below to read detailed rules on our official channel:"
    ),
    'task_menu': "Please select the type of task you would like to perform from the options below and start earning right away!",
    'task_link_msg': "Visit links to boost your earnings. Click below to start.",
    'task_watch_msg': "Watch ads to earn. Click below to watch.",
    'task_other_msg': "Complete other micro-tasks. Click below to start.",
    'withdraw_min_balance_fail': "❌ You need a minimum of 40 EGW to withdraw. Please complete tasks and refer friends to earn 40 EGW, then click on withdraw again.",
    'withdraw_min_refer_fail': "❌ A minimum of 5 referrals is required to withdraw. We want to check if you have worked seriously.",
    'withdraw_insufficient': "❌ Insufficient balance. You need at least {min_limit} EGW to withdraw.",
    'withdraw_gateway': "Select your payment gateway:\n*(Note: 40 EGW = $0.28)*",
    'withdraw_amount_prompt': "Enter the amount of EGW you wish to withdraw (Minimum {min_limit} EGW):",
    'withdraw_number_prompt': "Enter your {method} account/wallet address (Time limit: 2 minutes):",
    'withdraw_invalid_amount': "Please enter a valid numeric amount:",
    'withdraw_success': "Your withdrawal of {amount} EGW has been submitted successfully. A fee of {fee:.2f} EGW has been deducted. Admin will process it soon.",
    'timeout': "⏰ Time's up! Your request has been cancelled. Please try again."
}


def get_home_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🛠️ Task', '👥 Refer')
    markup.row('📊 Dashboard', '💳 Withdraw')
    markup.row('📢 Sponsor', '🤝 Help Center')
    markup.row('📜 Rules & Regulations', '🛒 Shop now')
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

        # --- অ্যান্টি-অ্যাবিউস ও রেফারেল স্ট্যাটাস ট্র্যাকিং লজিক (৫ EGW হলেই কেবল কনভার্ট হবে) ---
        referred_by = user_data.get('referred_by', 'direct')
        refer_reward_paid = user_data.get('refer_reward_paid', False)

        if new_balance >= 5 and referred_by != 'direct' and not refer_reward_paid:
            updates['refer_reward_paid'] = True
            ref_ref = db.reference(f'user/{referred_by}')
            ref_data = ref_ref.get()
            if ref_data:
                current_active_refer = ref_data.get('active_refer', 0)
                current_pending_refer = ref_data.get('pending_refer', 0)
                
                # রেফারার ডাটাবেজ আপডেট
                ref_ref.update({
                    'main_balance': ref_data.get('main_balance', 0) + 1.75,
                    'active_refer': current_active_refer + 1,
                    'pending_refer': max(0, current_pending_refer - 1)
                })
                
                # ref_info আপডেট: পেন্ডিং থেকে সরিয়ে অ্যাক্টিভে নেওয়া
                db.reference(f'ref_info/{referred_by}/pending/{userid}').delete()
                db.reference(f'ref_info/{referred_by}/active/{userid}').set(True)
                
                try:
                    notify_text = f"🎉 Congratulations! Your referred user `{userid}` has earned 5 EGW! You received a referral bonus of 1.75 EGW and they are now an Active Referral!"
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
                bot.send_message(chat_id, TEXTS['timeout'])
            except Exception as e:
                print(f"Error sending timeout msg: {e}")

def start_timeout_timer(chat_id, seconds):
    if chat_id in user_states and 'timer' in user_states[chat_id]:
        user_states[chat_id]['timer'].cancel()
        
    timer = threading.Timer(seconds, clear_user_state, args=[chat_id, True])
    timer.start()
    if chat_id in user_states:
        user_states[chat_id]['timer'] = timer


# --- ৫. স্টার্ট হ্যান্ডলার ও ভেরিফিকেশন গেটওয়ে ---
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
            bot.send_message(chat_id, TEXTS['home_msg'], reply_markup=get_home_menu())
            return

        welcome_text = TEXTS['welcome_msg']
        
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("📢 Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
        btn2 = types.InlineKeyboardButton("📢 Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        btn_verify = types.InlineKeyboardButton("Verify ✅", callback_data=f"verify:{referrer_id}")
        
        markup.row(btn1, btn2)
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
            
            is_joined = (status1 in ['member', 'creator', 'administrator'] and 
                         status2 in ['member', 'creator', 'administrator'])
        except Exception:
            is_joined = False

        if not is_joined:
            bot.answer_callback_query(call.id, TEXTS['not_joined'], show_alert=True)
            return

        bot.answer_callback_query(call.id)

        user_ref = db.reference(f'user/{user_id}')
        if user_ref.get():
            bot.send_message(chat_id, TEXTS['verified_success'], reply_markup=get_home_menu())
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
            "active_refer": 0,
            "pending_refer": 0
        }
        
        user_ref.set(user_data)
        
        # ইউজার রেজিস্টার হওয়ার সাথে সাথে ref_info ডিরেক্টরি তৈরি করা
        db.reference(f'ref_info/{user_id}').set({
            'initialized': True
        })
        
        if valid_referrer != 'direct':
            # রেফারারের পেন্ডিং রেফার সংখ্যা বাড়ানো এবং ref_info-তে জমা করা
            referrer_user_ref = db.reference(f'user/{valid_referrer}')
            referrer_user_data = referrer_user_ref.get() or {}
            current_pending = referrer_user_data.get('pending_refer', 0)
            
            referrer_user_ref.update({
                'pending_refer': current_pending + 1
            })
            
            # ref_info ডাটাবেজে পেন্ডিং হিসেবে যুক্ত করা
            db.reference(f'ref_info/{valid_referrer}/pending/{user_id}').set(True)
            
            # রেফারারকে ইনস্ট্যান্ট নোটিফিকেশন পাঠানো
            try:
                ref_notify = f"👤 User `{user_id}` has joined using your referral link. They are now a Pending Referral! Once they earn 5 EGW, they will become an Active Referral."
                bot.send_message(int(valid_referrer), ref_notify, parse_mode="Markdown")
            except Exception:
                pass

            bot.send_message(chat_id, TEXTS['verified_referred'].format(referrer_id=valid_referrer), reply_markup=get_home_menu())
        else:
            bot.send_message(chat_id, TEXTS['verified_success'], reply_markup=get_home_menu())

    except Exception as e:
        print(f"Error in verification: {e}")


# --- ৬. টাস্ক ও ক্যাটাকরি লজিক ---
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
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Work 💼", web_app=types.WebAppInfo(url="https://earnglow.shop/others.html"))
        )
        bot.send_message(chat_id, TEXTS['task_other_msg'], reply_markup=markup)
    elif category == 'link_visit':
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Visit 🌐", web_app=types.WebAppInfo(url="https://earnglow.shop/link.html"))
        )
        bot.send_message(chat_id, TEXTS['task_link_msg'], reply_markup=markup)
    elif category == 'watch_ad':
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Watch 📺", web_app=types.WebAppInfo(url="https://earnglow.shop/watch.html"))
        )
        bot.send_message(chat_id, TEXTS['task_watch_msg'], reply_markup=markup)


# --- ৭. উইথড্রয়াল লজিক ও কন্ডিশনাল সিকিউরিটি চেক ---
def handle_withdrawal_action(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        main_balance = user_data.get('main_balance', 0)
        
        # ১. মিনিমাম ব্যালেন্স ৪০ EGW চেক
        if main_balance < 40:
            bot.send_message(chat_id, TEXTS['withdraw_min_balance_fail'])
            return

        # ২. মিনিমাম ৫টি একটিভ রেফারেল চেক
        active_refer = user_data.get('active_refer', 0)
        if active_refer < 5:
            bot.send_message(chat_id, TEXTS['withdraw_min_refer_fail'])
            return

        # ৩. গেটওয়ে সিলেকশন ওপেন করা
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Bkash (বিকাশ)", callback_data="withdraw_method:Bkash"),
            types.InlineKeyboardButton("TON Wallet (টন ওয়ালেট)", callback_data="withdraw_method:TON")
        )
        bot.send_message(chat_id, TEXTS['withdraw_gateway'], reply_markup=markup, parse_mode="Markdown")
            
    except Exception as e:
        print(f"Error checking withdrawal: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_method:'))
def select_withdraw_method(call):
    chat_id = call.message.chat.id
    method = call.data.split(':')[1]
    bot.answer_callback_query(call.id)

    try:
        user_states[chat_id] = {
            'method': method,
            'min_limit': 40
        }

        if method == 'Bkash':
            user_states[chat_id]['step'] = 'bkash_number'
            start_timeout_timer(chat_id, 120)
            bot.send_message(chat_id, TEXTS['withdraw_number_prompt'].format(method=method))

        elif method == 'TON':
            user_states[chat_id]['step'] = 'ton_address'
            start_timeout_timer(chat_id, 120)
            bot.send_message(chat_id, TEXTS['withdraw_number_prompt'].format(method=method))

    except Exception as e:
        print(f"Error selecting withdraw method: {e}")


@bot.callback_query_handler(func=lambda call: call.data == 'skip_memo')
def handle_skip_memo(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    
    if chat_id in user_states and user_states[chat_id].get('step') == 'ton_memo':
        user_states[chat_id]['ton_memo'] = "No Memo"
        user_states[chat_id]['step'] = 'ton_amount'
        start_timeout_timer(chat_id, 120)
        
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
            
        bot.send_message(chat_id, "Enter the amount of EGW you wish to withdraw (Minimum 40 EGW):")


# --- ৮. সকল টেক্সট মেসেজ ও বাটন ইন্টারঅ্যাকশন হ্যান্ডলার ---
@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text.strip()
    
    # কোনো অ্যাক্টিভ স্টেট থাকলে তা আগে রান করা হবে
    if chat_id in user_states and 'step' in user_states[chat_id]:
        process_user_steps(message)
        return

    # বাটন ও অ্যাকশন ডিকশনারি
    menu_actions = {
        '🛠️ Task': 'task',
        '👥 Refer': 'refer',
        '📊 Dashboard': 'dashboard',
        '💳 Withdraw': 'withdraw',
        '📢 Sponsor': 'sponsor',
        '🤝 Help Center': 'support',
        '📜 Rules & Regulations': 'rules',
        '🛒 Shop now': 'shop'
    }
    
    action = menu_actions.get(text)
    if not action:
        return 

    clear_user_state(chat_id)
    
    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        
        if action == 'dashboard':
            completed_tasks = user_data.get('completed_task', 0)
            dashboard_text = TEXTS['dashboard'].format(
                name=user_data.get('name', 'N/A'),
                uid=user_id,
                active_refer=user_data.get('active_refer', 0),
                pending_refer=user_data.get('pending_refer', 0),
                main_balance=user_data.get('main_balance', 0),
                pending_balance=user_data.get('pending_balance', 0),
                completed_task=completed_tasks
            )
            bot.send_message(chat_id, dashboard_text, reply_markup=get_home_menu(), parse_mode="Markdown")
            
        elif action == 'rules':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("🎁 Referral Rules", url="https://t.me/earnglowofficial/6"))
            markup.row(types.InlineKeyboardButton("🌐 Link Visit Rules", url="https://t.me/earnglowofficial/7"))
            markup.row(types.InlineKeyboardButton("📺 Watch Video Rules", url="https://t.me/earnglowofficial/8"))
            markup.row(types.InlineKeyboardButton("💼 Other Task Rules", url="https://t.me/earnglowofficial/9"))
            markup.row(types.InlineKeyboardButton("💳 Withdrawal Rules", url="https://t.me/earnglowofficial/10"))
            
            bot.send_message(chat_id, TEXTS['rules_msg'], reply_markup=markup, parse_mode="Markdown")
            
        elif action == 'task':
            text_msg = TEXTS['task_menu']
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("Link Visit 🌐", callback_data="task_category:link_visit"),
                types.InlineKeyboardButton("Watch AD 📺", callback_data="task_category:watch_ad")
            )
            markup.row(
                types.InlineKeyboardButton("Other Task 💼", callback_data="task_category:other")
            )
            bot.send_message(chat_id, text_msg, reply_markup=markup)

        elif action == 'sponsor':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("Message Us 💬", url="https://t.me/EarnGlowSupport"))
            bot.send_message(chat_id, TEXTS['sponsor'], reply_markup=markup, parse_mode="Markdown")

        elif action == 'support':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("Help Center 🛠️", url="https://t.me/EarnGlowSupport"))
            bot.send_message(chat_id, TEXTS['support'], reply_markup=markup, parse_mode="Markdown")

        elif action == 'refer':
            bot_info = bot.get_me()
            refer_link = f"https://t.me/{bot_info.username}?start={user_id}"
            refer_text = TEXTS['refer'].format(
                active_refer=user_data.get('active_refer', 0),
                pending_refer=user_data.get('pending_refer', 0),
                refer_link=refer_link
            )
            bot.send_message(chat_id, refer_text, parse_mode="Markdown")
            
        elif action == 'withdraw':
            handle_withdrawal_action(message)
            
        elif action == 'shop':
            try:
                # ডিকশনারিতে admin key এর ভেতর shop_message খোঁজা
                shop_msg = db.reference('admin/shop_message').get()
                if shop_msg:
                    markup = types.InlineKeyboardMarkup()
                    markup.row(types.InlineKeyboardButton("Open Shop 🛒", url="https://earnglow.shop"))
                    bot.send_message(chat_id, shop_msg, reply_markup=markup, parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, "Shop is coming very soon!")
            except Exception as e:
                print(f"Error checking shop message: {e}")
                bot.send_message(chat_id, "Shop is coming very soon!")
            
    except Exception as e:
        print(f"Error handling menu button {text}: {e}")


def process_user_steps(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    state = user_states[chat_id]
    step = state.get('step')
    text = message.text.strip()

    # কোনো কারণে ইউজার অন্য মেনু বাটন প্রেস করলে স্টেট ক্যান্সেল করবে
    main_menu_commands = [
        '🛠️ Task', '👥 Refer', '📊 Dashboard', '💳 Withdraw', '📢 Sponsor', '🤝 Help Center', '📜 Rules & Regulations', '🛒 Shop now'
    ]
    if text in main_menu_commands:
        user_states.pop(chat_id, None)
        handle_text_messages(message)
        return

    # === BKASH FLOW ===
    if step == 'bkash_number':
        state['number'] = text
        state['step'] = 'bkash_amount'
        start_timeout_timer(chat_id, 120)
        bot.send_message(chat_id, "Enter the amount of EGW you wish to withdraw (Minimum 40 EGW):")

    elif step == 'bkash_amount':
        process_amount_and_submit(message, state['number'], "Bkash", None)

    # === TON FLOW ===
    elif step == 'ton_address':
        state['ton_address'] = text
        state['step'] = 'ton_memo'
        start_timeout_timer(chat_id, 120)
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("Skip ➡️", callback_data="skip_memo"))
        bot.send_message(chat_id, "Enter your TON Memo (if any, otherwise click the 'Skip' button below):", reply_markup=markup)

    elif step == 'ton_memo':
        state['ton_memo'] = text
        state['step'] = 'ton_amount'
        start_timeout_timer(chat_id, 120)
        bot.send_message(chat_id, "Enter the amount of EGW you wish to withdraw (Minimum 40 EGW):")

    elif step == 'ton_amount':
        process_amount_and_submit(message, state['ton_address'], "TON", state.get('ton_memo', 'No Memo'))


def process_amount_and_submit(message, target, method, memo):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text.strip()
    state = user_states.get(chat_id, {})

    try:
        amount = float(text)
    except ValueError:
        bot.send_message(chat_id, TEXTS['withdraw_invalid_amount'])
        return

    if amount < 40:
        bot.send_message(chat_id, TEXTS['withdraw_insufficient'].format(min_limit=40))
        return

    if 'timer' in state:
        state['timer'].cancel()

    try:
        user_ref = db.reference(f'user/{user_id}')
        user_data = user_ref.get() or {}
        main_balance = user_data.get('main_balance', 0)

        if main_balance < amount or amount <= 0:
            bot.send_message(chat_id, TEXTS['withdraw_insufficient'].format(min_limit=40))
        else:
            user_ref.update({
                'main_balance': main_balance - amount
            })

            # চার্জ হিসাব: ৮০ বা তার বেশি হলে ৮ + ৩%, আর কম হলে শুধু ৮ EGW
            if amount >= 80:
                fee = 8 + (amount * 0.03)
            else:
                fee = 8

            withdraw_data = {
                'uid': user_id,
                'method': method,
                'number_or_address': target,
                'amount': amount,
                'status': 'pending',
                'fee': fee,
                'type': 'withdraw'
            }
            if memo:
                withdraw_data['memo'] = memo

            db.reference('withdraw').push(withdraw_data)

            bot.send_message(chat_id, TEXTS['withdraw_success'].format(amount=amount, fee=fee))

    except Exception as e:
        print(f"Error processing withdraw: {e}")
        bot.send_message(chat_id, "Something went wrong while processing your withdrawal, please try again later.")

    clear_user_state(chat_id)


if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
