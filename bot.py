import os
import hmac
import hashlib
import urllib.parse
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- CORS CONFIGURATION ---
# Restricting frontend access specifically to your mini app domain
ALLOWED_ORIGIN = "https://earnglow.raybil.me"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

REQUIRED_CHANNELS = ["@earnglowofficial", "@raybilofficial"]

# --- TELEGRAM BOT LOGIC ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    welcome_text = (
        f"Welcome {full_name} 🎉\n\n"
        "Thank you for coming here. Through us, you can utilize your leisure time to earn passive income.\n\n"
        "To see our works and start working, join us now."
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Open Glow", 
        web_app=types.WebAppInfo(url=ALLOWED_ORIGIN)
    ))
    builder.row(
        InlineKeyboardButton(text="Telegram Channel", url="https://t.me/earnglowofficial"),
        InlineKeyboardButton(text="YouTube Channel", url="https://youtube.com")
    )

    await message.answer(welcome_text, reply_markup=builder.as_markup())


# --- WEB SERVER & API ROUTES ---

@app.api_route("/health", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def health_check(request: Request):
    """Public health endpoint. Accepts absolutely anything from anywhere and returns 200 OK."""
    return JSONResponse(status_code=200, content={"status": "OK"})


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(received_hash, expected_hash):
            return json.loads(parsed_data.get("user", "{}"))
        return None
    except Exception:
        return None

async def check_channel_membership(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

@app.post("/verify")
async def verify_user(request: Request):
    # Strict server-side origin/referrer check in case CORS is bypassed by scripting tools
    origin = request.headers.get("origin")
    referer = request.headers.get("referer") or ""
    
    if origin != ALLOWED_ORIGIN and not referer.startswith(ALLOWED_ORIGIN):
        raise HTTPException(status_code=404, detail="Not Found")

    body = await request.json()
    init_data = body.get("initData")

    if not init_data:
        raise HTTPException(status_code=404, detail="Missing initData")

    user_data = verify_telegram_init_data(init_data, BOT_TOKEN)
    if not user_data or "id" not in user_data:
        raise HTTPException(status_code=404, detail="Hash verification failed")

    user_id = user_data["id"]
    is_member = await check_channel_membership(user_id)
    if not is_member:
        raise HTTPException(status_code=404, detail="User has not joined required channels")

    return JSONResponse(status_code=200, content={"status": "success", "message": "Verified"})


@app.on_event("startup")
async def on_startup():
    import asyncio
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
