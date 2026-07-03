from telebot import types
from firebase_admin import db
from config import bot, CHANNEL_1, CHANNEL_2, SPONSOR_1, SPONSOR_2, get_home_menu

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

        # পরিবর্তন: ইউজার আগে থেকে রেজিস্টার্ড থাকলে সরাসরি হোম পেজ (কোনো জয়েন বা ভেরিফাই মেসেজ দেখাবে না)
        if user_snapshot:
            bot.send_message(chat_id, "EARN MONEY BD হোম মেনু:", reply_markup=get_home_menu())
            return

        welcome_text = (
            f"আসসালামু আলাইকুম {full_name}, EARN MONEY BD bot এ আপনাকে স্বাগতম 😊।\n\n"
            f"এখানে আপনি Gmail ID বিক্রি করে টাকা আয় করতে পারবেন। প্রতিটা Gmail এর মূল্য ১২ টাকা।\n\n"
            f"কাজ করতে আমাদের ২টি চ্যানেল এবং ২টি স্পন্সর চ্যানেলে জয়েন করুন এবং পরে ভেরিফাই বাটনে ক্লিক করুন।"
        )
        
        # ৪টি চ্যানেল সম্বলিত ইনলাইন বাটন
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("📢 চ্যানেল 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
        btn2 = types.InlineKeyboardButton("📢 চ্যানেল 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        btn3 = types.InlineKeyboardButton("📢 স্পন্সর 1 (1M+)", url=f"https://t.me/{SPONSOR_1.replace('@', '')}")
        btn4 = types.InlineKeyboardButton("📢 স্পন্সর 2 (1M+)", url=f"https://t.me/{SPONSOR_2.replace('@', '')}")
        btn_verify = types.InlineKeyboardButton("ভেরিফাই ✅", callback_data=f"verify:{referrer_id}")
        
        markup.row(btn1, btn2)
        markup.row(btn3, btn4)
        markup.row(btn_verify)

        bot.send_message(chat_id, welcome_text, reply_markup=markup)

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
            # ৪টি চ্যানেলের মেম্বারশিপ চেক করা হচ্ছে
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
            bot.answer_callback_query(call.id, "❌ আপনি এখনো ৪টি চ্যানেলে জয়েন করেননি! দয়া করে ৪টি চ্যানেলেই জয়েন করে আবার ভেরিফাই ✅ বাটনে ক্লিক করুন।", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        user_ref = db.reference(f'user/{user_id}')
        if user_ref.get():
            bot.send_message(chat_id, "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন।", reply_markup=get_home_menu())
            return

        # সিকিউরিটি রুল: ভেরিফাই সফল হওয়ার পরেই কেবল ডাটাবেজে ইউজার যোগ হবে এবং রেফারারকে বোনাস দেওয়া হবে
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
