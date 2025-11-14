import os
import logging
from dotenv import load_dotenv
from gtts import gTTS
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    MessageHandler, filters
)
import tempfile
import requests

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "DevOpsGuru")
TTS_LANG = os.getenv("TTS_LANG", "hi")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "deepseek")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================
# DEEPSEEK COMPLETION FUNCTION
# ============================
def deepseek_reply(prompt):
    url = "https://api.deepseek.com/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a friendly Hinglish DevOps Mentor."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ DeepSeek API error: {e}"

# ============================
# HANDLE TEXT MESSAGE
# ============================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    reply_text = deepseek_reply(user_msg)

    # Send text reply
    await update.message.reply_text(reply_text)

    # Also send Voice reply
    tts = gTTS(reply_text, lang=TTS_LANG)
    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as tmp:
        tts.save(tmp.name)
        await update.message.reply_voice(voice=open(tmp.name, "rb"))

# ============================
# HANDLE VOICE MESSAGE
# ============================
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Download voice file
    voice_file = await update.message.voice.get_file()
    file_path = "voice.ogg"
    await voice_file.download_to_drive(file_path)

    # Convert to text using DeepSeek Whisper endpoint
    # (DeepSeek currently does not include Whisper, so using external free STT)
    transcript = "Sorry bhai, voice-to-text deepseek ne abhi launch nahi kiya. Text bhej do 🙂"

    # Get AI reply
    reply_text = deepseek_reply(transcript)

    # Send reply
    await update.message.reply_text(reply_text)
    tts = gTTS(reply_text, lang=TTS_LANG)
    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as tmp:
        tts.save(tmp.name)
        await update.message.reply_voice(voice=open(tmp.name, "rb"))


# ============================
# MAIN APP START
# ============================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))

if __name__ == "__main__":
    logger.info("🚀 DevOpsGuru (DeepSeek Edition) Started...")
    app.run_polling()
