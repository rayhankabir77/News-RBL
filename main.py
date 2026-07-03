from telebot import types
from firebase_admin import db
from config import bot, user_states, clear_user_state, start_timeout_timer, get_home_menu

# বাকি মডিউলগুলো ইমপোর্ট করে তাদের হ্যান্ডলার রেজিস্টার করা হলো
import start
import create_account
import task
import withdraw

# হোম কিবোর্ড মেনুর অন্যান্য বোতাম হ্যান্ডলিং
@bot.message_handler(func=lambda m: m.text in ['📢 Sponsor Now', '📊 Dashboard', '🤝 Support', '👨‍💻 Developer Profile'])
def handle_menu_buttons(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text

    clear_user_state(chat_id)

    try:
        user_data = db.reference(f'user/{user_id}').get() or {}

        if text == '📊 Dashboard':
            dashboard_text = (
                f"👤 নাম: {user_data.get('name', 'N/A')}\n"
                f"🆔 UID: {user_id}\n"
                f"🔗 Referrer: {user_data.get('referred_by', 'direct')}\n\n"
                f"💰 মেইন ব্যালেন্স: {user_data.get('main_balance', 0)} টাকা\n"
                f"⏳ পেন্ডিং ব্যালেন্স: {user_data.get('pending_balance', 0)} টাকা"
            )
            bot.send_message(chat_id, dashboard_text, reply_markup=get_home_menu())

        elif text == '📢 Sponsor Now':
            bot.send_message(chat_id, "আমাদের সাথে স্পন্সরশিপ করতে যোগাযোগ করুন অফিশিয়াল সাপোর্টে।")

        elif text == '🤝 Support':
            bot.send_message(chat_id, "কোনো সমস্যায় আমাদের সাথে যোগাযোগ করতে পারেন। এডমিন প্রোফাইল: https://t.me/abcdit")

        elif text == '👨‍💻 Developer Profile':
            bot.send_message(chat_id, "বটের ডেভেলপার প্রোফাইল: https://t.me/abcdit")

    except Exception as e:
        print(f"Error handling menu button {text}: {e}")


# সকল ব্যাকগ্রাউন্ড স্টেট এবং ইনপুট প্রসেস
@bot.message_handler(func=lambda m: m.chat.id in user_states)
def process_user_steps(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    state = user_states[chat_id]
    step = state.get('step')
    text = message.text

    # যদি ইউজার কোনো মেইন মেনু বাটনে ক্লিক করে, তবে আগের স্টেট বন্ধ করে নতুন সেকশন ওপেন হবে
    if text in ['➕ Create Account', '📋 Task', '📢 Sponsor Now', '📊 Dashboard', '💳 Withdrawal', '🤝 Support', '👨‍💻 Developer Profile']:
        clear_user_state(chat_id)
        if text in ['➕ Create Account', '📋 Task', '💳 Withdrawal']:
            if text == '➕ Create Account':
                create_account.handle_create_account(message)
            elif text == '📋 Task':
                task.handle_view_tasks(message)
            elif text == '💳 Withdrawal':
                withdraw.handle_withdrawal(message)
        else:
            handle_menu_buttons(message)
        return

    # --- উইথড্র স্টেপস ---
    if step == 'withdraw_number':
        state['number'] = text
        state['step'] = 'withdraw_amount'
        start_timeout_timer(chat_id, 60)
        bot.send_message(chat_id, "কত টাকা উইথড্র করতে চান লিখুন (সময়: ১ মিনিট):")

    elif step == 'withdraw_amount':
        try:
            amount = int(text)
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
                user_ref.update({
                    'main_balance': main_balance - amount
                })

                db.reference(f'submit/{user_id}').push({
                    'method': state['method'],
                    'number': state['number'],
                    'amount': amount,
                    'status': 'pending',
                    'type': 'withdraw'
                })

                bot.send_message(chat_id, f"আপনার {amount} টাকা উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে। এডমিন দ্রুত পেমেন্ট কমপ্লিট করবে।")

        except Exception as e:
            print(f"Error processing withdraw: {e}")
            bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")

        clear_user_state(chat_id)

    # --- জিমেইল অ্যাকাউন্ট সাবমিশন স্টেপস (Create Account) ---
    elif step == 'get_task_id':
        task_id = text.strip()
        try:
            task_data = db.reference(f'task/{task_id}').get()
            if not task_data:
                bot.send_message(chat_id, "ভুল আইডি, দয়া করে সঠিক আইডি দিন:")
                return
            
            task_pass = ""
            if isinstance(task_data, dict):
                task_pass = task_data.get('pass', '')
            else:
                task_pass = str(task_data)

            state['task_id'] = task_id
            state['task_pass'] = task_pass
            state['step'] = 'get_gmail_email'
            
            start_timeout_timer(chat_id, 300)
            bot.send_message(chat_id, "আপনার ইমেইল দিন (সময়: ৫ মিনিট):")

        except Exception as e:
            print(f"Error fetching task data: {e}")
            bot.send_message(chat_id, "একটি ত্রুটি ঘটেছে, আবার চেষ্টা করুন।")
            clear_user_state(chat_id)

    elif step == 'get_gmail_email':
        email_input = text.strip()
        if 'timer' in state:
            state['timer'].cancel()

        try:
            db.reference(f'task_sub/{user_id}').push({
                'gmail': email_input,
                'pass': state.get('task_pass', ''),
                'id': state.get('task_id', ''),
                'status': 'pending'
            })

            bot.send_message(chat_id, "আপনার কাজ সাবমিট করা হয়েছে এডমিন রিভিউ করে আপনাকে জানাবে।")

        except Exception as e:
            print(f"Database write error: {e}")
            bot.send_message(chat_id, "টাস্ক সাবমিট করতে সমস্যা হয়েছে, অনুগ্রহ করে আবার চেষ্টা করুন।")
        
        clear_user_state(chat_id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_home")
def back_to_home(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    clear_user_state(chat_id)
    bot.send_message(chat_id, "মূল হোম মেনু সিলেক্ট করুন।", reply_markup=get_home_menu())


if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
