import os
import json
import threading
from telebot import TeleBot, types
import firebase_admin
from firebase_admin import credentials, db

# এনভায়রনমেন্ট ভ্যারিয়েবল থেকে ডেটা নেওয়া
BOT_TOKEN = os.getenv("BOT_TOKEN")
RTDB_URL = os.getenv("RTDB_URL")
FIREBASE_ADMIN_ENV = os.getenv("FIREBASE_ADMIN")

# ফায়ারবেস অ্যাডমিন ইনিশিয়ালাইজেশন
if FIREBASE_ADMIN_ENV.startswith("{"):
    # যদি সরাসরি JSON স্ট্রিং দেওয়া হয় (যেমন Render বা Heroku-তে)
    cred_dict = json.loads(FIREBASE_ADMIN_ENV)
    cred = credentials.Certificate(cred_dict)
else:
    # যদি ফাইল পাথ দেওয়া হয়
    cred = credentials.Certificate(FIREBASE_ADMIN_ENV)

firebase_admin.initialize_app(cred, {
    'databaseURL': RTDB_URL
})

bot = TeleBot(BOT_TOKEN)

CHANNEL_1 = '@earnmoneybd1111'
CHANNEL_2 = '@bbbbbbbbbb11111100'

# মেমোরি ফ্রী রাখার জন্য টেম্পোরারি স্টেট স্টোর
user_states = {}

# --- মেমোরি ক্লিনআপ বা স্টেট মুছে ফেলার ফাংশন ---
def clear_user_state(chat_id, notify_timeout=False):
    """
    ইউজারের টেম্পোরারি মেমোরি এবং টাইমার রিলিজ করে সার্ভার ফ্রী করার ফাংশন।
    এটি ডাটাবেসের ডেটা মুছে ফেলে না, শুধু সার্ভারের র‌্যাম ফ্রী করে।
    """
    state = user_states.pop(chat_id, None)
    if state:
        timer = state.get('timer')
        if timer:
            timer.cancel()  # ব্যাকগ্রাউন্ডের একটিভ টাইমার বন্ধ করে
        if notify_timeout:
            try:
                bot.send_message(chat_id, "⏰ সময় শেষ হয়ে গেছে! আপনার রিকোয়েস্টটি বাতিল করা হয়েছে। আবার চেষ্টা করুন।")
            except Exception as e:
                print(f"Error sending timeout msg: {e}")

def start_timeout_timer(chat_id, seconds):
    """টাইমআউট টাইমার চালু করা"""
    # আগের কোনো টাইমার থাকলে তা বাতিল করা
    if chat_id in user_states and 'timer' in user_states[chat_id]:
        user_states[chat_id]['timer'].cancel()
        
    timer = threading.Timer(seconds, clear_user_state, args=[chat_id, True])
    timer.start()
    if chat_id in user_states:
        user_states[chat_id]['timer'] = timer


# হোম মেনু কিবোর্ড
def get_home_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('➕ Create Gmail Account')
    markup.row('📊 DASHBOARD', '💳 Withdraw')
    markup.row('👥 Refer', '🤝 Support')
    return markup


# --- /start সেকশন ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    # রেফারেল আইডি বের করা (যেমন: /start 12345)
    parts = message.text.split()
    referrer_id = parts[1] if len(parts) > 1 else 'direct'

    try:
        user_ref = db.reference(f'user/{user_id}')
        user_snapshot = user_ref.get()

        # ১. ইউজার ডাটাবেসে থাকলে
        if user_snapshot:
            bot.send_message(chat_id, "আপনি আগে থেকেই আমাদের সাথে যুক্ত।", reply_markup=get_home_menu())
            return

        # ২. নতুন ইউজার হলে চ্যানেল জয়েনিং বাটন পাঠানো (ডেটাবেসে এখনই সেভ হবে না)
        welcome_text = (
            f"আলাইকুম {full_name}, EARN MONEY BD bot এ আপনাকে স্বাগতম 😊।\n\n"
            f"এখানে আপনি Gmail ID বিক্রি করে টাকা আয় করতে পারবেন। প্রতিটা Gmail এর মূল্য ১২ টাকা।\n\n"
            f"কাজ করতে আমাদের দুইটা চ্যানেল এ জয়েন করুন এবং পরে ভেরিফাই বাটন এ ক্লিক করুন।"
        )
        
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("📢 চ্যানেল 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
        btn2 = types.InlineKeyboardButton("📢 চ্যানেল 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        btn_verify = types.InlineKeyboardButton("ভেরিফাই ✅", callback_data=f"verify:{referrer_id}")
        markup.row(btn1, btn2)
        markup.row(btn_verify)

        bot.send_message(chat_id, welcome_text, reply_markup=markup)

    except Exception as e:
        print(f"Error in start: {e}")


# --- ভেরিফাই বাটনের কাজ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('verify:'))
def handle_verify(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    referrer_id = call.data.split(':')[1]
    first_name = call.from_user.first_name or ""
    last_name = call.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    try:
        # চ্যানেল মেম্বারশিপ চেক করা
        try:
            status1 = bot.get_chat_member(CHANNEL_1, chat_id).status
            status2 = bot.get_chat_member(CHANNEL_2, chat_id).status
            is_joined = status1 in ['member', 'creator', 'administrator'] and status2 in ['member', 'creator', 'administrator']
        except Exception:
            is_joined = False

        if not is_joined:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো আমাদের দুটি চ্যানেলে জয়েন করেননি! দয়া করে দুটি চ্যানেলেই জয়েন করে আবার VERIFY ✅ বাটনে ক্লিক করুন।", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        user_ref = db.reference(f'user/{user_id}')
        if user_ref.get():
            bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন।", reply_markup=get_home_menu())
            return

        # ডাটাবেসে সেভ করার অবজেক্ট
        user_data = {
            "name": full_name,
            "uid": user_id,
            "main_balance": 0,
            "pending_balance": 0,
            "completed_task": 0,
            "referred_by": referrer_id,
            "total_refer": 0
        }

        if referrer_id != 'direct':
            ref_ref = db.reference(f'user/{referrer_id}')
            ref_data = ref_ref.get()

            if ref_data:
                # রেফারার ব্যালেন্স ও রেফার কাউন্ট বাড়ানো
                ref_ref.update({
                    'main_balance': (ref_data.get('main_balance', 0) + 2),
                    'total_refer': (ref_data.get('total_refer', 0) + 1)
                })
                # রেফারারকে মেসেজ পাঠানো
                try:
                    bot.send_message(int(referrer_id), f"আপনার রেফার লিংক এ একজন জয়েন করেছে। তার uid {user_id}")
                except Exception:
                    pass

                user_ref.set(user_data)
                bot.send_message(chat_id, f"অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি আমাদের কাজ করতে পারবেন。\nℹ️ আপনাকে রেফার করেছে {referrer_id}\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।", reply_markup=get_home_menu())
            else:
                user_data['referred_by'] = 'direct'
                user_ref.set(user_data)
                bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি আমাদের কাজ করতে পারবেন。\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।", reply_markup=get_home_menu())
        else:
            user_ref.set(user_data)
            bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি আমাদের কাজ করতে পারবেন。\n\nনিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।", reply_markup=get_home_menu())

    except Exception as e:
        print(f"Error in verification: {e}")


# --- Gmail অ্যাকাউন্ট ক্রিয়েশন ও টাস্ক লোডিং ---
@bot.message_handler(func=lambda m: m.text == '➕ Create Gmail Account')
def handle_gmail_tasks(message):
    chat_id = message.chat.id
    loading_msg = bot.send_message(chat_id, "🔎 checking task ....")

    try:
        # সর্বোচ্চ ১০টি টাস্ক রিড
        tasks_ref = db.reference('task').limit_to_first(10)
        tasks = tasks_ref.get()

        if not tasks:
            bot.edit_message_text("কোনো টাস্ক avilabe নেই", chat_id, loading_msg.message_id)
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = []
        for task_id, task_info in tasks.items():
            title = task_info.get('title', f"Task {task_id}")
            buttons.append(types.InlineKeyboardButton(title, callback_data=f"view_task:{task_id}"))

        # বাটন জোড়া জোড়া করে যুক্ত করা (প্রতি লাইনে ২টি)
        markup.add(*buttons)
        markup.row(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_home"))

        bot.edit_message_text("check completed ✅", chat_id, loading_msg.message_id, reply_markup=markup)

    except Exception as e:
        print(f"Error checking tasks: {e}")
        bot.edit_message_text("টাস্ক লোড করতে সমস্যা হয়েছে।", chat_id, loading_msg.message_id)


# টাস্ক ডিটেইলস এবং সাবমিশন প্রসেস
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_task:'))
def view_task_details(call):
    chat_id = call.message.chat.id
    task_id = call.data.split(':')[1]

    try:
        task_info = db.reference(f'task/{task_id}').get()
        if not task_info:
            bot.answer_callback_query(call.id, "টাস্কটি আর পাওয়া যাচ্ছে না।", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        desc = task_info.get('description', 'কোনো বিবরণ নেই।')
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("Complete Task", callback_data=f"complete_task:{task_id}"))
        markup.row(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_home"))

        bot.send_message(chat_id, f"📋 টাস্ক বিবরণ:\n{desc}", reply_markup=markup)
    except Exception as e:
        print(e)


# সাবমিশন শুরু (নাম চাওয়া এবং টাইমার সেট করা)
@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_task:'))
def start_task_submission(call):
    chat_id = call.message.chat.id
    task_id = call.data.split(':')[1]
    bot.answer_callback_query(call.id)

    # ইউজারের জন্য সার্ভার মেমোরিতে স্টেট বরাদ্দ করা
    user_states[chat_id] = {
        'step': 'get_name',
        'task_id': task_id,
        'name': '',
        'password': ''
    }
    
    # ৫ মিনিটের টাইমআউট (৩০০ সেকেন্ড) সেট করা
    start_timeout_timer(chat_id, 300)
    bot.send_message(chat_id, "Gmail আইডি এর নাম দিন (সময়: ৫ মিনিট)")


# মেসেজ হ্যান্ডলিং (নাম ও পাসওয়ার্ড প্রসেস)
@bot.message_handler(func=lambda m: m.chat.id in user_states)
def process_submission_steps(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    state = user_states[chat_id]
    step = state.get('step')

    if step == 'get_name':
        state['name'] = message.text
        state['step'] = 'get_password'
        
        # পাসওয়ার্ড এর জন্য ৩০ সেকেন্ড টাইমআউট সেট করা
        start_timeout_timer(chat_id, 30)
        bot.send_message(chat_id, "পাসওয়ার্ড দিন (সময়: ৩০ সেকেন্ড)")

    elif step == 'get_password':
        state['password'] = message.text
        
        # টাইমার ক্যানসেল করা
        if 'timer' in state:
            state['timer'].cancel()

        # ডাটাবেসে ডেটা রাইট করা
        try:
            db.reference(f'submit/{user_id}').set({
                'task_id': state['task_id'],
                'gmail_name': state['name'],
                'gmail_password': state['password'],
                'status': 'pending'
            })
            
            # পেন্ডিং ব্যালেন্স ১২ টাকা বৃদ্ধি করা
            user_ref = db.reference(f'user/{user_id}')
            user_data = user_ref.get() or {}
            current_pending = user_data.get('pending_balance', 0)
            user_ref.update({
                'pending_balance': current_pending + 12
            })

            bot.send_message(chat_id, "আপনার টাস্ক সফল ভাবে সাবমিট করা হয়েছে। এডমিন রিভিউ করে ২৪ ঘণ্টার মধ্যে আপনাকে জানানো হবে।")

        except Exception as e:
            print(f"Database write error: {e}")
            bot.send_message(chat_id, "টাস্ক সাবমিট করতে সমস্যা হয়েছে, অনুগ্রহ করে আবার চেষ্টা করুন।")
        
        # --- সার্ভার মেমোরি ফ্রী করা ---
        # এই মেসেজ কমপ্লিট হওয়ার পর ইউজারের মেমোরি স্টেট সার্ভার থেকে মুছে ফেলা হচ্ছে
        clear_user_state(chat_id)


# --- ড্যাশবোর্ড, উইথড্র, রেফার এবং সাপোর্ট ---
@bot.message_handler(func=lambda m: m.text in ['📊 DASHBOARD', '💳 Withdraw', '👥 Refer', '🤝 Support'])
def handle_menu_buttons(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text

    try:
        user_data = db.reference(f'user/{user_id}').get() or {}

        if text == '📊 DASHBOARD':
            dashboard_text = (
                f"👤 নাম: {user_data.get('name', 'N/A')}\n"
                f"🆔 UID: {user_id}\n"
                f"🔗 Referrer: {user_data.get('referred_by', 'direct')}\n\n"
                f"💰 মেইন ব্যালেন্স: {user_data.get('main_balance', 0)} টাকা\n"
                f"⏳ পেন্ডিং ব্যালেন্স: {user_data.get('pending_balance', 0)} টাকা"
            )
            bot.send_message(chat_id, dashboard_text)

        elif text == '💳 Withdraw':
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("বিকাশ", callback_data="withdraw_method:Bkash"),
                types.InlineKeyboardButton("নগদ", callback_data="withdraw_method:Nagad")
            )
            bot.send_message(chat_id, "টাকা তোলার জন্য মাধ্যম সিলেক্ট করুন:", reply_markup=markup)

        elif text == '👥 Refer':
            bot_info = bot.get_me()
            refer_link = f"`https://t.me/{bot_info.username}?start={user_id}`" # ব্যাকটিক ব্যবহার করা হয়েছে কপি-টু-ক্লিক এর জন্য
            refer_text = (
                f"আপনার total রেফার: {user_data.get('total_refer', 0)}\n\n"
                f"আপনার রেফারেল লিংক:\n{refer_link}\n\n"
                f"প্রতি রেফার এ ২ টাকা করে পাবেন। যত রেফার তত টাকা।"
            )
            bot.send_message(chat_id, refer_text, parse_mode="Markdown")

        elif text == '🤝 Support':
            bot.send_message(chat_id, "কোনো সমস্যায় আমাদের সাথে যোগাযোগ করতে পারেন। এডমিন প্রোফাইল: https://t.me/abcdit")

    except Exception as e:
        print(f"Error handling menu button {text}: {e}")


# উইথড্র মেথড সিলেক্ট এবং নম্বর/অ্যামাউন্ট ইনপুট নেওয়া
@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_method:'))
def select_withdraw_method(call):
    chat_id = call.message.chat.id
    method = call.data.split(':')[1]
    bot.answer_callback_query(call.id)

    # উইথড্র করার জন্য মেমোরি স্টেট তৈরি এবং ২ মিনিটের টাইমআউট
    user_states[chat_id] = {
        'step': 'withdraw_number',
        'method': method,
        'number': '',
        'amount': 0
    }
    start_timeout_timer(chat_id, 120)
    bot.send_message(chat_id, f"আপনার {method} নম্বরটি দিন (সময়: ২ মিনিট):")

# উইথড্র প্রসেসিং (নাম্বার ও অ্যামাউন্ট স্টেপ)
@bot.message_handler(func=lambda m: m.chat.id in user_states and 'method' in user_states[m.chat.id])
def process_withdraw_steps(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    state = user_states[chat_id]
    step = state.get('step')

    if step == 'withdraw_number':
        state['number'] = message.text
        state['step'] = 'withdraw_amount'
        start_timeout_timer(chat_id, 60) # পরবর্তী ধাপের জন্য ৬০ সেকেন্ড সময়
        bot.send_message(chat_id, "কত টাকা উইথড্র করতে চান লিখুন (সময়: ১ মিনিট):")

    elif step == 'withdraw_amount':
        try:
            amount = int(message.text)
        except ValueError:
            bot.send_message(chat_id, "দয়া করে সঠিক সংখ্যায় অ্যামাউন্ট দিন:")
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
                # মেইন ব্যালেন্স থেকে টাকা কাটা
                user_ref.update({
                    'main_balance': main_balance - amount
                })

                # উইথড্র রিকোয়েস্ট ডাটাবেসে সাবমিট করা
                db.reference(f'withdraw/{user_id}').push({
                    'method': state['method'],
                    'number': state['number'],
                    'amount': amount,
                    'status': 'pending'
                })

                bot.send_message(chat_id, f"আপনার {amount} টাকা উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে। এডমিন দ্রুত পেমেন্ট কমপ্লিট করবে।")

        except Exception as e:
            print(f"Error processing withdraw: {e}")
            bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")

        # --- সার্ভার মেমোরি ফ্রী করা ---
        clear_user_state(chat_id)


# ইনলাইন Back বাটনের কাজ
@bot.callback_query_handler(func=lambda call: call.data == "back_to_home")
def back_to_home(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    # ইউজারের কোনো অ্যাক্টিভ স্টেট থাকলে তা মেমোরি থেকে রিলিজ করা
    clear_user_state(chat_id)
    bot.send_message(chat_id, "মূল হোম মেনু সিলেক্ট করুন।", reply_markup=get_home_menu())


if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
