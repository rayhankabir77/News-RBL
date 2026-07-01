import os
import json
import asyncio
import requests
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- এনভায়রনমেন্ট ভ্যারিয়েবল কনফিগারেশন ---
BOT_TOKEN = "8801321117:AAH03Y0HuiSLnVZE2JFAfBJmc8nDkJOmXqU"
FIREBASE_ADMIN = os.environ.get("FIREBASE_ADMIN", "YOUR_FIREBASE_SECRET_KEY")
RTDB_URL = os.environ.get("RTDB_URL", "https://rbl---3-default-rtdb.asia-southeast1.firebasedatabase.app")

# চ্যানেলের তথ্য
CHANNEL_1 = "@earnmoneybd1111"
CHANNEL_2 = "@bbbbbbbbbb11111100"
CHANNEL_1_LINK = "https://t.me/earnmoneybd1111"
CHANNEL_2_LINK = "https://t.me/bbbbbbbbbb11111100"

# সার্ভারের RAM/CPU ফ্রি রাখার জন্য সাময়িক মেমোরি হোল্ডার
# কাজ শেষ হওয়া মাত্রই এখান থেকে ইউজারের ডেটা মুছে ফেলা হবে
user_states = {} 
loop = None
bot_instance = None

# --- ১. ডামি ও অ্যাডমিন ফ্ল্যাস্ক সার্ভার ---
app = Flask(__name__)

@app.route('/check', methods=['GET', 'POST'])
def health_check():
    # এখানে যে রিকোয়েস্টই আসুক না কেন, রেসপন্স সর্বদা 200 OK পাঠাবে
    return "OK", 200

@app.route('/admin', methods=['POST'])
def admin_action():
    data = request.get_json() or {}
    action = data.get("action")
    uid = data.get("uid")
    message = data.get("message")
    
    if action == "send_message" and uid and message and bot_instance and loop:
        # অ্যাসিনক্রোনাসলি টেলিগ্রাম বট দিয়ে নির্দিষ্ট ইউজারকে মেসেজ পাঠানো
        asyncio.run_coroutine_threadable(bot_instance.send_message(chat_id=uid, text=message), loop)
        return jsonify({"status": "success", "message": "Message sent to user"}), 200
    return jsonify({"status": "error", "message": "Invalid parameters"}), 400

def run_flask():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

# --- ২. ফায়ারবেস হেল্পার ফাংশনসমূহ (REST API) ---
def db_get(path):
    try:
        url = f"{RTDB_URL}/{path}.json?auth={FIREBASE_ADMIN}"
        response = requests.get(url)
        return response.json()
    except Exception as e:
        print(f"Database Get Error: {e}")
        return None

def db_put(path, data):
    try:
        url = f"{RTDB_URL}/{path}.json?auth={FIREBASE_ADMIN}"
        requests.put(url, json=data)
        return True
    except Exception as e:
        print(f"Database Put Error: {e}")
        return False

def db_patch(path, data):
    try:
        url = f"{RTDB_URL}/{path}.json?auth={FIREBASE_ADMIN}"
        requests.patch(url, json=data)
        return True
    except Exception as e:
        print(f"Database Patch Error: {e}")
        return False

# ইউজার চ্যানেলগুলোতে জয়েন করেছে কিনা চেক করার ফাংশন
async def is_user_joined(context: ContextTypes.DEFAULT_TYPE, user_id: int, channel: str) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

# --- ৩. টেলিগ্রাম বট লজিক ---

# /start কমান্ড হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    
    # স্টার্ট প্যারামিটার চেক করা (bot?start=uid)
    args = context.args
    referrer_id = args[0] if args else None
    
    # ডাটাবেসে নিজের প্রোফাইল চেক করা
    existing_user = db_get(f"users/{user_id}")
    
    # সার্ভারের মেমরিতে অস্থায়ী স্টেট তৈরি (RAM অপ্টিমাইজড)
    user_states[user_id] = {
        "referrer": "directly",
        "ref_status": "none"
    }
    
    if existing_user:
        user_states[user_id]["ref_status"] = "already_registered"
    elif referrer_id:
        # নিজের আইডি নিজে রেফার করতে পারবে না
        if str(referrer_id) == str(user_id):
            user_states[user_id]["referrer"] = "directly"
        else:
            # রেফারার ডাটাবেসে আছে কিনা চেক
            referrer_user = db_get(f"users/{referrer_id}")
            if referrer_user:
                user_states[user_id]["referrer"] = str(referrer_id)
                user_states[user_id]["ref_status"] = "success"
            else:
                user_states[user_id]["referrer"] = str(referrer_id)
                user_states[user_id]["ref_status"] = "not_found"
    else:
        user_states[user_id]["referrer"] = "directly"

    welcome_text = (
        f"আসসালামু আলাইকুম {full_name},\n"
        f"আশাকরি ভালো আছেন। EARN MONEY BD bot এ আপনাকে স্বাগতম 😊।\n\n"
        f"এখানে আপনি Gmail ID বিক্রি করে টাকা আয় করতে পারবেন। প্রতিটা Gmail এর মূল্য ১২ টাকা।\n\n"
        f"কাজ করতে আমাদের দুইটা চ্যানেল এ জয়েন করুন এবং পরে ভেরিফাই বাটন এ ক্লিক করুন।"
    )

    keyboard = [
        [InlineKeyboardButton("CHANNEL - 1 📢", url=CHANNEL_1_LINK),
         InlineKeyboardButton("CHANNEL - 2 📢", url=CHANNEL_2_LINK)],
        [InlineKeyboardButton("VERIFY ✅", callback_data="verify_channels")]
    ]
    await update.message.reply_text(text=welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ভেরিফাই বাটন ক্লিক হ্যান্ডলার
async def verify_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = query.from_user
    username = user.username or "No Username"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    
    if user_id not in user_states:
        await query.message.reply_text("❌ অনুগ্রহ করে আবার /start দিন।")
        return

    joined_1 = await is_user_joined(context, user_id, CHANNEL_1)
    joined_2 = await is_user_joined(context, user_id, CHANNEL_2)

    if joined_1 and joined_2:
        state = user_states[user_id]
        ref_status = state["ref_status"]
        referrer = state["referrer"]
        
        # সফল ভেরিফিকেশন মেসেজ নির্ধারণ
        if ref_status == "already_registered":
            ref_msg = "You already registered"
        elif referrer == "directly":
            ref_msg = "You join directly"
            # নতুন ইউজার হিসেবে ডাটাবেসে সেভ
            new_user_data = {
                "name": full_name, "username": username, "uid": user_id,
                "balance": 0, "pending": 0, "total_refer": 0, "complit_task": 0, "referred_by": "directly"
            }
            db_put(f"users/{user_id}", new_user_data)
        elif ref_status == "success":
            ref_msg = f"You referred by {referrer} success"
            # নতুন ইউজার ডাটাবেস এন্ট্রি
            new_user_data = {
                "name": full_name, "username": username, "uid": user_id,
                "balance": 0, "pending": 0, "total_refer": 0, "complit_task": 0, "referred_by": referrer
            }
            db_put(f"users/{user_id}", new_user_data)
            
            # রেফারারের অ্যাকাউন্টে total_refer +1 এবং মেইন ব্যালেন্স +2 করা হচ্ছে
            ref_data = db_get(f"users/{referrer}")
            if ref_data:
                updated_ref = {
                    "total_refer": int(ref_data.get("total_refer", 0)) + 1,
                    "balance": int(ref_data.get("balance", 0)) + 2
                }
                db_patch(f"users/{referrer}", updated_ref)
                
                # রেফারারকে মেসেজ পাঠানো
                try:
                    await context.bot.send_message(
                        chat_id=int(referrer),
                        text=f"🔔 আপনার রেফার লিংকে একজন জয়েন করেছে। UID: {user_id}"
                    )
                except Exception:
                    pass
        else: # not_found
            ref_msg = f"You referred by {referrer} not found"
            new_user_data = {
                "name": full_name, "username": username, "uid": user_id,
                "balance": 0, "pending": 0, "total_refer": 0, "complit_task": 0, "referred_by": referrer
            }
            db_put(f"users/{user_id}", new_user_data)

        # সার্ভার মেমরি ক্লিনআপ (RAM/CPU ফ্রি করা)
        del user_states[user_id]

        success_text = (
            f"অভিনন্দন 🎉, আপনি সফল ভাবে ভেরিফাই হয়েছেন এখন আপনি আমাদের কাজ করতে পারবেন।\n"
            f"ℹ️ {ref_msg}\n\n"
            f"নিচে থেকে প্রয়োজনীয় অপশন সিলেক্ট করুন।"
        )
        
        # আপনার চাহিদা অনুযায়ী নতুন বাটন লেআউট ফরম্যাট
        main_menu_buttons = [
            ["➕ Create Gmail Account"],
            ["📊 DASHBOARD", "💳 Withdraw"],
            ["👥 Refer", "🤝 Support"]
        ]
        reply_markup = ReplyKeyboardMarkup(main_menu_buttons, resize_keyboard=True)
        await query.edit_message_text(text="ভেরিফিকেশন সফল হয়েছে! 👍")
        await query.message.reply_text(text=success_text, reply_markup=reply_markup)
    else:
        await query.message.reply_text(text="❌ আপনি এখনো আমাদের দুটি চ্যানেলে জয়েন করেননি! দয়া করে দুটি চ্যানেলেই জয়েন করে আবার VERIFY ✅ বাটনে ক্লিক করুন।")

# মেইন মেনু হ্যান্ডলার
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    user_info = db_get(f"users/{user_id}")
    if not user_info:
        await update.message.reply_text("❌ দয়া করে প্রথমে /start দিয়ে চ্যানেল ভেরিফাই করুন।")
        return

    # ১. ➕ Create Gmail Account
    if text == "➕ Create Gmail Account":
        loading_msg = await update.message.reply_text("🔎 checking task ....")
        tasks = db_get("task") or {}
        
        if not tasks:
            await loading_msg.edit_text("❌ এই মুহূর্তে কোনো টাস্ক উপলব্ধ নেই।")
            return
            
        await loading_msg.edit_text("check completed ✅")
        
        keyboard = []
        row = []
        # প্রতি লাইনে ২টি করে বাটন (সর্বোচ্চ ১০টি টাস্ক)
        for t_id, t_data in list(tasks.items())[:10]:
            title = t_data.get("title", "Task")
            row.append(InlineKeyboardButton(title, callback_data=f"task_{t_id}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="go_home")])
        await update.message.reply_text("নিচের যেকোনো একটি টাস্ক সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ২. 📊 DASHBOARD
    elif text == "📊 DASHBOARD":
        dash_text = (
            "📊 **আপনার অ্যাকাউন্ট ড্যাশবোর্ড:**\n\n"
            f"👤 নাম: {user_info.get('name')}\n"
            f"🆔 UID: {user_info.get('uid')}\n"
            f"🔗 র্যাফারার: {user_info.get('referred_by')}\n"
            f"💵 মেইন ব্যালেন্স: {user_info.get('balance', 0)} টাকা\n"
            f"⏳ পেন্ডিং ব্যালেন্স: {user_info.get('pending', 0)} টাকা"
        )
        await update.message.reply_text(text=dash_text, parse_mode="Markdown")

    # ৩. 💳 Withdraw
    elif text == "💳 Withdraw":
        keyboard = [
            [InlineKeyboardButton("বিকাশ", callback_data="w_bikas"),
             InlineKeyboardButton("নগদ", callback_data="w_nagad")]
        ]
        await update.message.reply_text("পেমেন্ট মেথড সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ৪. 👥 Refer
    elif text == "👥 Refer":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        refer_text = (
            f"👥 **আপনার মোট রেফার:** {user_info.get('total_refer', 0)} জন\n\n"
            f"🔗 **আপনার রেফারাল লিংক (কপি করতে লিংকে চাপুন):**\n`{ref_link}`\n\n"
            f"💰 প্রতি রেফার এ ২ টাকা করে পাবেন। যত রেফার তত টাকা।"
        )
        await update.message.reply_text(text=refer_text, parse_mode="Markdown")

    # ৫. 🤝 Support
    elif text == "🤝 Support":
        await update.message.reply_text("কোনো সমস্যায় আমাদের সাথে যোগাযোগ করতে পারেন।\n\n👤 অ্যাডমিন প্রোফাইল: https://t.me/abcdit")

    # ডাটা এন্ট্রি হ্যান্ডলিং (নাম ও পাসওয়ার্ড ইনপুট নেওয়ার লজিক)
    elif user_id in user_states:
        state = user_states[user_id]
        if state.get("step") == "wait_gmail":
            state["gmail_name"] = text
            state["step"] = "wait_pass"
            await update.message.reply_text("🔑 পাসওয়ার্ড দিন (আপনার কাছে সময় আছে ৩০ সেকেন্ড):")
            
            # ৩০ সেকেন্ডের পাসওয়ার্ড ইনপুট টাইমার শুরু
            async def pass_timeout():
                await asyncio.sleep(30)
                if user_id in user_states and user_states[user_id].get("step") == "wait_pass":
                    del user_states[user_id]
                    await update.message.reply_text("⏱️ সময় শেষ! ৩০ সেকেন্ডের মধ্যে পাসওয়ার্ড না দেওয়ায় টাস্ক বাতিল হয়েছে।")
            asyncio.create_task(pass_timeout())

        elif state.get("step") == "wait_pass":
            gmail_name = state["gmail_name"]
            password = text
            t_id = state["task_id"]
            
            # ডাটাবেসে সাবমিট ডেটা পাঠানো dburl/submit/{UID}
            submit_data = {
                "task_id": t_id,
                "gmail": gmail_name,
                "password": password,
                "status": "pending"
            }
            db_put(f"submit/{user_id}", submit_data)
            
            # পেন্ডিং ব্যালেন্স ১২ টাকা বৃদ্ধি করা
            current_pending = int(user_info.get("pending", 0))
            db_patch(f"users/{user_id}", {"pending": current_pending + 12})
            
            # সার্ভার মেমরি ও CPU ফ্রি করার জন্য সাথে সাথে ডিলিট
            del user_states[user_id]
            
            await update.message.reply_text("✅ আপনার টাস্ক সফল ভাবে সাবমিট করা হয়েছে। এডমিন রিভিউ করে ২৪ ঘণ্টার মধ্যে আপনাকে জানানো হবে।")
            
        elif state.get("step") == "wait_w_num":
            state["w_num"] = text
            state["step"] = "wait_w_amount"
            await update.message.reply_text("💵 আপনার Withdraw Amount (টাকা) লিখুন:")
            
        elif state.get("step") == "wait_w_amount":
            try:
                amount = int(text)
            except ValueError:
                await update.message.reply_text("❌ দয়া করে সঠিক সংখ্যায় অ্যামাউন্ট লিখুন।")
                return
                
            main_bal = int(user_info.get("balance", 0))
            if amount <= 0:
                await update.message.reply_text("❌ অ্যামাউন্ট অবশ্যই ০ থেকে বেশি হতে হবে।")
                return
                
            if main_bal >= amount:
                # ব্যালেন্স কেটে নেওয়া
                db_patch(f"users/{user_id}", {"balance": main_bal - amount})
                
                # উইথড্র ডাটাবেসে সাবমিট করা dburl/withdraw/{UID}
                w_data = {
                    "method": state["w_method"],
                    "number": state["w_num"],
                    "amount": amount,
                    "status": "pending"
                }
                db_put(f"withdraw/{user_id}", w_data)
                
                await update.message.reply_text(f"✅ আপনার {amount} টাকা উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে।")
            else:
                await update.message.reply_text("❌ আপনার মেইন ব্যালেন্সে পর্যাপ্ত টাকা নেই (পেন্ডিং ব্যালেন্স বাদে)।")
                
            # কাজ শেষে স্টেট মেমোরি থেকে মুছে ফেলা হলো (CPU/RAM ফ্রি)
            del user_states[user_id]

# ইনলাইন বাটন ক্লিকে রেসপন্স হ্যান্ডলার
async def inline_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("task_"):
        t_id = data.split("_")[1]
        task_details = db_get(f"task/{t_id}")
        if task_details:
            msg = f"📋 **টাস্ক বিবরণ:**\n\n{task_details.get('description', 'No details available')}"
            keyboard = [[InlineKeyboardButton("Complete Task", callback_data=f"comp_{t_id}")]]
            await query.message.reply_text(text=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            
    elif data.startswith("comp_"):
        t_id = data.split("_")[1]
        user_states[user_id] = {"step": "wait_gmail", "task_id": t_id}
        await query.message.reply_text("📧 Gmail আইডি এর নাম দিন (আপনার কাছে সময় আছে ৫ মিনিট):")
        
        # ৫ মিনিটের জিমেইল নাম ইনপুট টাইমার শুরু
        async def gmail_timeout():
            await asyncio.sleep(300)
            if user_id in user_states and user_states[user_id].get("step") == "wait_gmail":
                del user_states[user_id]
                await query.message.reply_text("⏱️ সময় শেষ! ৫ মিনিটের মধ্যে জিমেইল নাম না দেওয়ায় টাস্ক বাতিল হয়েছে।")
        asyncio.create_task(gmail_timeout())

    elif data in ["w_bikas", "w_nagad"]:
        method = "বিকাশ" if data == "w_bikas" else "নগদ"
        user_states[user_id] = {"step": "wait_num", "w_method": method}
        user_states[user_id]["step"] = "wait_w_num"
        await query.message.reply_text(f"📱 আপনার {method} নম্বরটি দিন:")

    elif data == "go_home":
        await query.message.delete()

# মেইন এক্সেকিউশন ফাংশন
def main():
    global loop, bot_instance
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # ব্যাকগ্রাউন্ড থ্রেডে ফ্ল্যাস্ক সার্ভার চালু করা
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # টেলিগ্রাম অ্যাপ্লিকেশন তৈরি
    application = Application.builder().token(BOT_TOKEN).build()
    bot_instance = application.bot

    # হ্যান্ডলার যুক্ত করা
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(verify_click, pattern="^verify_channels$"))
    application.add_handler(CallbackQueryHandler(inline_click, pattern="^(task_|comp_|w_|go_home)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    # অ্যাপ্লিকেশন রান করানো
    application.run_polling()

if __name__ == '__main__':
    main()
