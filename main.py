import os
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ১. ডামি ফ্ল্যাস্ক সার্ভার (রেন্ডারকে ২৪/৭ জাগিয়ে রাখার জন্য) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "EarnMoneyBD Bot is Running 24/7!"

def run_flask():
    # রেন্ডার অটোমেটিক PORT এনভায়রনমেন্ট ভ্যারিয়েবল দেয়, না থাকলে ৩০০০ ব্যবহার করবে
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

# --- ২. টেলিগ্রাম বটের কনফিগারেশন ---
# এখানে আপনার আসল বটের টোকেন দিন
BOT_TOKEN = "8801321117:AAH03Y0HuiSLnVZE2JFAfBJmc8nDkJOmXqU" 

# আপনার চ্যানেলের ইউজারনেম বা আইডি (অবশ্যই @ সহ দিতে হবে)
CHANNEL_1 = "@bmjdbdkidhr"
CHANNEL_2 = "@bmjdbdkidhr"

# চ্যানেল লিংক
CHANNEL_1_LINK = "https://t.me/bmjdbdkidhr"
CHANNEL_2_LINK = "https://t.me/bmjdbdkidhr"

# ইউজার চ্যানেলগুলোতে জয়েন করেছে কিনা তা চেক করার ফাংশন
async def is_user_joined(context: ContextTypes.DEFAULT_TYPE, user_id: int, channel: str) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
        # member.status যদি member, administrator, বা creator হয় তবে সে জয়েন আছে
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception as e:
        print(f"Error checking channel {channel}: {e}")
        return False

# /start কমান্ড হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else ""
    last_name = user.last_name if user.last_name else ""
    full_name = f"{first_name} {last_name}".strip()

    welcome_text = (
        f"আসসালামু আলাইকুম {full_name},\n"
        f"আশাকরি ভালো আছেন। EARN MONEY BD bot এ আপনাকে স্বাগতম 😊।\n\n"
        f"এখানে আপনি Gmail ID বিক্রি করে টাকা আয় করতে পারবেন। প্রতিটা Gmail এর মূল্য ১২ টাকা।\n\n"
        f"কাজ করতে আমাদের দুইটা চ্যানেল এ জয়েন করুন এবং পরে ভেরিফাই বাটন এ ক্লিক করুন।"
    )

    # ইনলাইন বাটন তৈরি (এক লাইনে দুই চ্যানেল, নিচে ভেরিফাই)
    keyboard = [
        [
            InlineKeyboardButton("CHANNEL - 1 📢", url=CHANNEL_1_LINK),
            InlineKeyboardButton("CHANNEL - 2 📢", url=CHANNEL_2_LINK)
        ],
        [InlineKeyboardButton("VERIFY ✅", callback_data="verify_channels")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text=welcome_text, reply_markup=reply_markup)

# ভেরিফাই বাটন ক্লিক হ্যান্ডলার
async def verify_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # বাটন ক্লিক রেসপন্স ফাস্ট করার জন্য
    
    user_id = query.from_user.id
    
    # দুটি চ্যানেলই চেক করা হচ্ছে
    joined_1 = await is_user_joined(context, user_id, CHANNEL_1)
    joined_2 = await is_user_joined(context, user_id, CHANNEL_2)

    if joined_1 and joined_2:
        # সফলভাবে ভেরিফাই হলে ইনলাইন বাটনগুলো রিমুভ করে নতুন মেসেজ দেওয়া
        success_text = (
            "অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি আমাদের কাজ করতে পারবেন। "
            "নিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।"
        )
        
        # নিচের মেইন মেনু বাটন (Reply Keyboard)
        main_menu_buttons = [
            ["+ Create Gmail Account", "Balance 💰"],
            ["Withdraw 💳", "Rules 📜"]
        ]
        reply_markup = ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True)
        
        await query.edit_message_text(text="ভেরিফিকেশন সফল হয়েছে! 👍")
        await query.message.reply_text(text=success_text, reply_markup=reply_markup)
    else:
        # জয়েন না করলে অ্যালার্ট দেওয়া
        await query.message.reply_text(
            text="❌ আপনি এখনো আমাদের দুটি চ্যানেলে জয়েন করেননি! দয়া করে দুটি চ্যানেলেই জয়েন করে আবার VERIFY ✅ বাটনে ক্লিক করুন।"
        )

# মেইন ফাংশন
def main():
    # প্রথমে ব্যাকগ্রাউন্ড থ্রেডে ফ্ল্যাস্ক সার্ভার চালু করা
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # টেলিগ্রাম বট অ্যাপ্লিকেশন তৈরি
    application = Application.builder().token(BOT_TOKEN).build()

    # হ্যান্ডলার যুক্ত করা
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(verify_click, pattern="^verify_channels$"))

    # বট পোলিং মোডে রান করা (হাই ট্রাফিকের জন্য পারফেক্ট)
    application.run_polling()

if __name__ == '__main__':
    main()
  
