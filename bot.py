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
        'welcome_msg': (
            "🚀 Welcome to EARNGLOW! 🚀\n\n"
            "Start earning unlimited EGW currency effortlessly, right from your mobile phone! 💰 "
            "This is a premier and secure platform designed to help you generate a steady digital income on the go.\n\n"
            "How to Start:\n"
            "Simply join our 2 official channels listed below and tap the 'Verify ✅' button to activate your account and begin your earning journey!"
        ),
        'join_chan_1': "📢 Channel 1",
        'join_chan_2': "📢 Channel 2",
        'verify_btn': "Verify ✅",
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
            "👥 **Total Referrals:** {total_refer} users\n\n"
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
        'sponsor_btn': "Message Us 💬",
        'support': (
            "🤝 EARNGLOW - Support Center 🤝\n\n"
            "Whether it's about withdrawals or task-related issues, we are always here to assist you! Our team is dedicated to resolving your problems as quickly as possible. ⚡️\n\n"
            "🛠️ For any assistance, contact our helpdesk directly:\n"
            "👉 Official Customer Support:"
        ),
        'support_btn': "Help Center 🛠️",
        'refer': (
            "👥 **EARNGLOW - Referral Center** 👥\n\n"
            "🎁 **Referral Bonus:** Earn **1.75 EGW** once your referred friend verifies and earns at least **5 EGW**!\n"
            "👉 **Your Total Referrals:** `{total_refer}` users\n\n"
            "🔗 **Your Unique Referral Link:**\n"
            "`{refer_link}`\n\n"
            "*Share this link to start earning EGW!*"
        ),
        'rules_msg': (
            "📋 Complete Rules & Regulations of EARNGLOW:\n\n"
            "To ensure seamless work and guaranteed payouts, you must strictly follow the rules below:\n"
            "1. New Referral Rule (🎁 Referral Bonus): When someone joins and verifies using your referral link, you will receive a bonus of 1.75 EGW right after they earn at least 5 EGW on their own! Any attempt to use fake referrals will lead to an immediate ban.\n"
            "2. Website Visits: Visit the assigned websites from the task section and stay on the page until the timer finishes. Closing the page early will result in no points.\n"
            "3. Video Tasks: Watch the full duration of the specified videos attentively. Fast-forwarding or skipping the video will invalidate the task.\n"
            "4. Miscellaneous Tasks: Carefully read and complete any other daily custom tasks exactly as instructed.\n"
            "5. Strict Fair Play: The use of VPNs, auto-clickers, or any hacking tools is strictly prohibited. Violating this will result in an immediate account ban and forfeiture of all earnings."
        ),
        'rules_btn': "Rules & Regulations 📋",
        'task_menu': "Please select the type of task you would like to perform from the options below and start earning right away!",
        'task_link': "Link Visit 🌐",
        'task_watch': "Watch AD 📺",
        'task_other': "Other Task 💼",
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
    },
    'bn': {
        'welcome_msg': (
            "🚀 **EARNGLOW-তে আপনাকে স্বাগতম!** 🚀\n\n"
            "এখন আপনার হাতে থাকা মোবাইল ফোনটি ব্যবহার করেই ঘরে বসে খুব সহজে আনলিমিটেড EGW কারেন্সি আর্ন করুন! 💰 "
            "কোনো জটিলতা ছাড়াই প্রতিদিন পার্ট-টাইম কাজ করে আয় করার এটি একটি দুর্দান্ত ও বিশ্বস্ত প্ল্যাটফর্ম।\n\n"
            "কাজ শুরু করার নিয়ম:\n"
            "নিচে দেওয়া আমাদের ২টি অফিসিয়াল চ্যানেলে জয়েন করুন এবং আপনার অ্যাকাউন্টটি সক্রিয় করতে 'Verify ✅' বাটনে ক্লিক করুন!"
        ),
        'join_chan_1': "📢 চ্যানেল 1",
        'join_chan_2': "📢 চ্যানেল 2",
        'verify_btn': "ভেরিফাই ✅",
        'not_joined': (
            "❌ দুঃখিত!\n"
            "আপনি এখনো আমাদের সবকটি চ্যানেলে জয়েন করেননি। অনুগ্রহ করে সবগুলো চ্যানেলে জয়েন করুন এবং এরপর আবার 'Verify ✅' বাটনে ক্লিক করুন। ধন্যবাদ!"
        ),
        'verified_success': (
            "🎉 অভিনন্দন! 🎉\n"
            "আপনার অ্যাকাউন্টটি সফলভাবে ভেরিফাই করা হয়েছে। এখন আপনি কাজ শুরু করতে এবং আনলিমিটেড EGW আর্ন করতে সম্পূর্ণ প্রস্তুত!"
        ),
        'verified_referred': (
            "🎉 অভিনন্দন! 🎉\n"
            "আপনার অ্যাকাউন্টটি সফলভাবে ভেরিফাই করা হয়েছে। এখন আপনি কাজ শুরু করতে এবং আনলিমিটেড EGW আর্ন করতে সম্পূর্ণ প্রস্তুত!\n\n"
            "ℹ️ আপনাকে রেফার করেছেন: {referrer_id}\n\n"
            "👇 নিচের মেনু থেকে আপনার প্রয়োজনীয় অপশনটি সিলেক্ট করুন:"
        ),
        'home_msg': "আপনি হোম মেনুতে চলে এসেছেন।",
        'dashboard': (
            "📊 **আপনার EARNGLOW ড্যাশবোর্ড** 📊\n\n"
            "👤 **নাম:** {name}\n"
            "🆔 **ইউজার আইডি (UID):** `{uid}`\n"
            "👥 **টোটাল রেফার:** {total_refer} জন\n\n"
            "💰 **মেইন ব্যালেন্স:** {main_balance} EGW\n"
            "⏳ **পেন্ডিং ব্যালেন্স:** {pending_balance} EGW\n"
            "✅ **টোটাল কমপ্লিট টাস্ক:** {completed_task} টি"
        ),
        'sponsor': (
            "📢 বিজ্ঞাপন ও স্পন্সরশিপ অফার! 📢\n\n"
            "আপনার ব্যবসা, ব্র্যান্ড, টেলিগ্রাম চ্যানেল কিংবা ওয়েবসাইটের প্রচারণা আমাদের বটের মাধ্যমে সকল সক্রিয় ইউজারের কাছে পৌঁছে দিন! 📈 "
            "আমাদের রয়েছে অত্যন্ত এক্টিভ এবং বিশাল একটি ইউজার বেস, যা আপনার প্রজেক্টের রিচ দ্রুত বাড়াতে সাহায্য করবে। 🚀\n\n"
            "🎯 আমাদের প্রধান সুবিধাসমূহ:\n"
            "👥 শতভাগ রিয়েল এবং একটিভ ইউজার।\n"
            "⚡️ মুহূর্তের মধ্যে সকল ইউজারের কাছে নোটিফিকেশন।\n"
            "📊 সাশ্রয়ী মূল্যে সেরা মার্কেটিং রেজাল্ট。\n\n"
            "🤝 স্পন্সরশিপ বা বিজ্ঞাপনের জন্য সরাসরি যোগাযোগ করুন:"
        ),
        'sponsor_btn': "মেসেজ করুন 💬",
        'support': (
            "🤝 EARNGLOW - সাপোর্ট সেন্টার 🤝\n\n"
            "উইথড্র কিংবা কাজ সংক্রান্ত যেকোনো সমস্যায় আমরা সবসময় আপনার পাশে আছি! "
            "আপনার যেকোনো জটিলতার দ্রুত সমাধানে আমাদের টিম সার্বক্ষণিক প্রস্তুত। ⚡️\n\n"
            "🛠️ যেকোনো প্রয়োজনে সরাসরি আমাদের সাহায্য কেন্দ্রের সাথে যোগাযোগ করুন:\n"
            "👉 অফিসিয়াল কাস্টমার সাপোর্ট:"
        ),
        'support_btn': "হেল্প সেন্টার 🛠️",
        'refer': (
            "👥 **EARNGLOW - রেফারেল সেন্টার** 👥\n\n"
            "🎁 **রেফারেল বোনাস:** আপনার রেফার লিংকে কেউ জয়েন করে ভেরিফাই হওয়ার পর যখন সে নিজে কমপক্ষে **৫ EGW** আয় করবে, তখন আপনি পাবেন **১.৭৫ EGW** বোনাস!\n"
            "👉 **আপনার মোট রেফার সংখ্যা:** `{total_refer}` জন\n\n"
            "🔗 **আপনার ইউনিক রেফারেল লিংক:**\n"
            "`{refer_link}`\n\n"
            "*উপরের লিংকটি কপি করে বন্ধুদের মাঝে শেয়ার করে এখনই EGW ইনকাম শুরু করুন!*"
        ),
        'rules_msg': (
            "📋 EARNGLOW-এর সম্পূর্ণ নিয়মাবলী (Rules & Regulations):\n\n"
            "আমাদের প্ল্যাটফর্মে সঠিকভাবে কাজ করতে এবং পেমেন্ট নিশ্চিত করতে নিচের নিয়মগুলো অবশ্যই মেনে চলতে হবে:\n"
            "১. নতুন রেফারের নিয়ম (🎁 রেফারেল বোনাস): আপনার রেফারেল লিংক ব্যবহার করে কেউ জয়েন এবং ভেরিফাই হওয়ার পর, সে নিজে যখন কমপক্ষে ৫ EGW আয় করবে, "
            "ঠিক তখনই আপনার অ্যাকাউন্টে ১.৭৫ EGW বোনাস যুক্ত হবে! কোনো ফেক রেফার করার চেষ্টা করলে অ্যাকাউন্ট ব্লক করা হবে।\n"
            "২. ওয়েবসাইট টাস্ক: টাস্ক সেকশনে দেওয়া ওয়েবসাইটগুলো ভিজিট করুন এবং নির্দেশিত সময় পর্যন্ত অপেক্ষা করুন। সময় শেষ হওয়ার আগে পেজ বন্ধ করলে পয়েন্ট যোগ হবে না।\n"
            "৩. ভিডিও টাস্ক: প্রতিটি ভিডিও সম্পূর্ণ মনোযোগ দিয়ে শেষ পর্যন্ত দেখুন। কোনো ভিডিও স্কিপ (Skip) বা টেনে টেনে দেখলে টাস্ক বাতিল বলে গণ্য হবে。\n"
            "৪. অন্যান্য কাজ: প্রতিদিনের নতুন নতুন কাস্টম কাজগুলো সঠিক নিয়ম মেনে সম্পূর্ণ করুন।\n"
            "৫. সততা বজায় রাখুন: কোনো প্রকার ভিপিএন (VPN), অটো-ক্লিক্যার বা হ্যাকিং টুলস ব্যবহার করার চেষ্টা করলে আপনার অ্যাকাউন্ট স্থায়ীভাবে ব্যান করা হবে এবং ব্যালেন্স বাতিল হবে।"
        ),
        'rules_btn': "সম্পূর্ণ নিয়মাবলী 📋",
        'task_menu': "আপনি ঠিক কী ধরনের কাজ করতে চান, তা নিচে দেওয়া অপশনগুলো থেকে সিলেক্ট করুন এবং এখনই আপনার আর্নিং শুরু করুন!",
        'task_link': "লিঙ্ক ভিজিট 🌐",
        'task_watch': "অ্যাড দেখুন 📺",
        'task_other': "অন্যান্য কাজ 💼",
        'task_link_msg': "Link visit করে আপনার ইনকাম বাড়িয়ে নিন। নিচে থাকা Visit এর মধ্যে ক্লিক করুন।",
        'task_watch_msg': "বিভিন্ন ধরনের বিজ্ঞাপন দেখে আয় করুন। নিচে থাকা watch button এ ক্লিক করুন।",
        'task_other_msg': "অন্যান্য কাজ করতে নিচে Work এ ক্লিক করুন।",
        'withdraw_min_balance_fail': "❌ উইথড্র করার জন্য আপনার সর্বনিম্ন ৪০ EGW লাগবে। টাস্ক কমপ্লিট এবং রেফার করে ৪০ EGW আয় করে পুনরায় উইথড্র তে ক্লিক করুন।",
        'withdraw_min_refer_fail': "❌ উইথড্র করতে মিনিমাম ৫টা রেফার লাগবে। আমরা চেক করতে চাই আপনি সিরিয়াস কাজ করেছেন কি না।",
        'withdraw_insufficient': "❌ আপনার ব্যালেন্স এ পর্যাপ্ত টাকা নেই। উইথড্র করার জন্য মিনিমাম {min_limit} EGW ব্যালেন্স লাগবে।",
        'withdraw_gateway': "উইথড্র করার পেমেন্ট গেটওয়ে সিলেক্ট করুন:\n*(মনে রাখবেন: 40 EGW = $0.28)*",
        'withdraw_amount_prompt': "কত EGW উইথড্র করতে চান লিখুন (মিনিমাম {min_limit} EGW হতে হবে):",
        'withdraw_number_prompt': "আপনার {method} নম্বর/অ্যাড্রেসটি দিন (সময়: ২ মিনিট):",
        'withdraw_invalid_amount': "দয়া করে সঠিক সংখ্যায় অ্যামাউন্ট দিন:",
        'withdraw_success': "আপনার {amount} EGW উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে। চার্জ {fee:.2f} EGW কেটে নেওয়া হয়েছে। এডমিন দ্রুত পেমেন্ট কমপ্লিট করবে।",
        'timeout': "⏰ সময় শেষ হয়ে গেছে! আপনার রিকোয়েস্টটি বাতিল করা হয়েছে। আবার চেষ্টা করুন।"
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
        markup.row('📜 সম্পূর্ণ নিয়মাবলী', '🛠️ টাস্ক')
        markup.row('📊 ড্যাশবোর্ড', '📢 স্পন্সর')
        markup.row('💳 উইথড্র', '🤝 সাপোর্ট')
        markup.row('👥 রেফার')
    else:
        markup.row('📜 Rules & Regulations', '🛠️ Task')
        markup.row('📊 Dashboard', '📢 Sponsor')
        markup.row('💳 Withdraw', '🤝 Support')
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

        # --- অ্যান্টি-অ্যাবিউস রেফারেল ট্র্যাকিং লজিক (৫ EGW উপার্জনের মাইলফলক) ---
        referred_by = user_data.get('referred_by', 'direct')
        refer_reward_paid = user_data.get('refer_reward_paid', False)

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
                        notify_text = f"🎉 আপনার আমন্ত্রিত ইউজার `{userid}` ৫ EGW আয়ের মাইলফলক স্পর্শ করায় আপনি ১.৭৫ EGW রেফারেল বোনাস পেয়েছেন!"
                    else:
                        notify_text = f"🎉 Your referred user `{userid}` has earned 5 EGW, and you have received a referral bonus of 1.75 EGW!"
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

        # নতুন ইউজারদের ভাষা নির্বাচন স্ক্রিন
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


# --- ৭. উইথড্রয়াল লজিক ও কন্ডিশন সেটআপ ---
def handle_withdrawal_action(message, lang):
    chat_id = message.chat.id
    user_id = str(chat_id)
    
    try:
        user_data = db.reference(f'user/{user_id}').get() or {}
        main_balance = user_data.get('main_balance', 0)
        
        # ১. ব্যালেন্স কমপক্ষে ৪০ EGW হতে হবে
        if main_balance < 40:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_min_balance_fail'])
            return

        # ২. রেফারেল কমপক্ষে ৫টি হতে হবে
        total_refer = user_data.get('total_refer', 0)
        if total_refer < 5:
            bot.send_message(chat_id, TEXTS[lang]['withdraw_min_refer_fail'])
            return

        # ৩. পেমেন্ট গেটওয়ে সিলেক্ট করুন
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Bkash (বিকাশ)", callback_data="withdraw_method:Bkash"),
            types.InlineKeyboardButton("TON Wallet (টন ওয়ালেট)", callback_data="withdraw_method:TON")
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
        user_states[chat_id] = {
            'method': method,
            'min_limit': 40
        }

        if method == 'Bkash':
            user_states[chat_id]['step'] = 'bkash_number'
            start_timeout_timer(chat_id, 120)
            bot.send_message(chat_id, TEXTS[lang]['withdraw_number_prompt'].format(method=method))

        elif method == 'TON':
            user_states[chat_id]['step'] = 'ton_address'
            start_timeout_timer(chat_id, 120)
            bot.send_message(chat_id, TEXTS[lang]['withdraw_number_prompt'].format(method=method))

    except Exception as e:
        print(f"Error selecting withdraw method: {e}")


@bot.callback_query_handler(func=lambda call: call.data == 'skip_memo')
def handle_skip_memo(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    bot.answer_callback_query(call.id)
    
    lang = get_user_lang(user_id)
    
    if chat_id in user_states and user_states[chat_id].get('step') == 'ton_memo':
        user_states[chat_id]['ton_memo'] = "No Memo"
        user_states[chat_id]['step'] = 'ton_amount'
        start_timeout_timer(chat_id, 120)
        
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
            
        if lang == 'bn':
            bot.send_message(chat_id, "কত EGW উইথড্র করতে চান লিখুন (মিনিমাম ৪০ EGW):")
        else:
            bot.send_message(chat_id, "Enter the amount of EGW you wish to withdraw (Minimum 40 EGW):")


# --- ৮. সকল টেক্সট মেসেজ ও বাটন ইন্টারঅ্যাকশন হ্যান্ডলার ---
@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text.strip()
    
    # কোনো অ্যাক্টিভ স্টেট থাকলে তা প্রসেস করা হবে
    if chat_id in user_states and 'step' in user_states[chat_id]:
        process_user_steps(message)
        return

    lang = get_user_lang(user_id)
    
    # বাটন ও কন্ডিশন ম্যাপিং
    menu_actions = {
        '📜 Rules & Regulations': 'rules',
        '📜 সম্পূর্ণ নিয়মাবলী': 'rules',
        
        '🛠️ Task': 'task',
        '🛠️ টাস্ক': 'task',
        
        '📢 Sponsor': 'sponsor',
        '📢 স্পন্সর': 'sponsor',
        
        '📊 Dashboard': 'dashboard',
        '📊 ড্যাশবোর্ড': 'dashboard',
        
        '💳 Withdraw': 'withdraw',
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
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(TEXTS[lang]['sponsor_btn'], url="https://t.me/EarnGlowSupport"))
            bot.send_message(chat_id, TEXTS[lang]['sponsor'], reply_markup=markup, parse_mode="Markdown")

        elif action == 'support':
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(TEXTS[lang]['support_btn'], url="https://t.me/EarnGlowSupport"))
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

    # অন্য কোনো প্রধান বাটন প্রেস করলে স্টেট ক্যান্সেল করবে
    main_menu_commands = [
        '📜 Rules & Regulations', '🛠️ Task', '📊 Dashboard', '📢 Sponsor', '💳 Withdraw', '🤝 Support', '👥 Refer',
        '📜 সম্পূর্ণ নিয়মাবলী', '🛠️ টাস্ক', '📊 ড্যাশবোর্ড', '📢 স্পন্সর', '💳 উইথড্র', '🤝 সাপোর্ট', '👥 রেফার'
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
        if lang == 'bn':
            bot.send_message(chat_id, "কত EGW উইথড্র করতে চান লিখুন (মিনিমাম ৪০ EGW):")
        else:
            bot.send_message(chat_id, "Enter the amount of EGW you wish to withdraw (Minimum 40 EGW):")

    elif step == 'bkash_amount':
        process_amount_and_submit(message, state['number'], "Bkash", None)

    # === TON FLOW ===
    elif step == 'ton_address':
        state['ton_address'] = text
        state['step'] = 'ton_memo'
        start_timeout_timer(chat_id, 120)
        
        # Skip button for TON Memo
        markup = types.InlineKeyboardMarkup()
        skip_btn_text = "Skip ➡️" if lang == 'en' else "স্কিপ করুন ➡️"
        markup.row(types.InlineKeyboardButton(skip_btn_text, callback_data="skip_memo"))
        
        if lang == 'bn':
            bot.send_message(chat_id, "আপনার TON মেমো (Memo) দিন (যদি থাকে, না থাকলে নিচে 'স্কিপ করুন' বাটনে চাপুন):", reply_markup=markup)
        else:
            bot.send_message(chat_id, "Enter your TON Memo (if any, otherwise click the 'Skip' button below):", reply_markup=markup)

    elif step == 'ton_memo':
        state['ton_memo'] = text
        state['step'] = 'ton_amount'
        start_timeout_timer(chat_id, 120)
        if lang == 'bn':
            bot.send_message(chat_id, "কত EGW উইথড্র করতে চান লিখুন (মিনিমাম ৪০ EGW):")
        else:
            bot.send_message(chat_id, "Enter the amount of EGW you wish to withdraw (Minimum 40 EGW):")

    elif step == 'ton_amount':
        process_amount_and_submit(message, state['ton_address'], "TON", state.get('ton_memo', 'No Memo'))


def process_amount_and_submit(message, target, method, memo):
    chat_id = message.chat.id
    user_id = str(chat_id)
    text = message.text.strip()
    lang = get_user_lang(user_id)
    state = user_states.get(chat_id, {})

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

            # চার্জ হিসাব: ৮০ EGW বা তার বেশি হলে ৮ + ৩%, আর কম হলে শুধু ৮ EGW
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

            bot.send_message(chat_id, TEXTS[lang]['withdraw_success'].format(amount=amount, fee=fee))

    except Exception as e:
        print(f"Error processing withdraw: {e}")
        if lang == 'bn':
            bot.send_message(chat_id, "উইথড্র সম্পন্ন করতে সমস্যা হয়েছে, পরে আবার চেষ্টা করুন।")
        else:
            bot.send_message(chat_id, "Something went wrong while processing your withdrawal, please try again later.")

    clear_user_state(chat_id)


if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
