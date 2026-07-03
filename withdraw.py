from telebot import types
from firebase_admin import db
from config import bot, user_states, start_timeout_timer

@bot.message_handler(func=lambda m: m.text == '💳 Withdrawal')
def handle_withdrawal(message):
    chat_id = message.chat.id
    user_id = str(chat_id)

    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        main_balance = user_data.get('main_balance', 0)

        # ২৪ টাকার মিনিমাম ব্যালেন্স চেক
        if main_balance < 24:
            bot.send_message(chat_id, "আপনার উইথড্র দেয়ার জন্য মিনিমাম 24 টাকা লাগবে")
        else:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("বিকাশ", callback_data="withdraw_method:Bkash"),
                types.InlineKeyboardButton("নগদ", callback_data="withdraw_method:Nagad")
            )
            bot.send_message(chat_id, "আপনার পেমেন্ট মেথড সিলেক্ট করুন:", reply_markup=markup)

    except Exception as e:
        print(f"Error showing withdrawal: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_method:'))
def select_withdraw_method(call):
    chat_id = call.message.chat.id
    method = call.data.split(':')[1]
    bot.answer_callback_query(call.id)

    user_states[chat_id] = {
        'step': 'withdraw_number',
        'method': method,
        'number': '',
        'amount': 0
    }
    start_timeout_timer(chat_id, 120)
    bot.send_message(chat_id, f"আপনার {method} নম্বরটি দিন (সময়: ২ মিনিট):")
