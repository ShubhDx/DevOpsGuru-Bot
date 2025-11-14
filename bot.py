import os
import logging
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import openai   # <-- correct import

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "DevOpsGuru")
TTS_LANG = os.getenv("TTS_LANG", "hi")

# OpenAI API key (correct)
openai.api_key = OPENAI_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def transcribe_audio(file_path):
    try:
        audio_file = open(file_path, "rb")
        transcript = openai.Audio.transcribe(
            model="whisper-1",
            file=audio_file
        )
        return transcript["text"]
    except Exception as e:
        return f"Audio error: {str(e)}"


async def generate_ai_reply(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are {BOT_NAME}, a Hinglish speaking DevOps mentor."},
                {"role": "user", "content": text}
            ]
        )
        reply = response.choices[0].message["content"]
        return reply
    except Exception as e:
        return f"AI Error: {str(e)}"


def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang=TTS_LANG)
        tmp_dir = tempfile.gettempdir()
        audio_path = os.path.join(tmp_dir, "reply.mp3")
        tts.save(audio_path)
        return audio_path
    except:
        return None


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    ai_reply = await generate_ai_reply(user_message)

    await update.message.reply_text(ai_reply)

    audio_path = text_to_speech(ai_reply)
    if audio_path:
        await update.message.reply_audio(audio_path)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = await update.message.voice.get_file()
    file_path = Path(tempfile.gettempdir()) / "voice.ogg"
    await voice.download_to_drive(str(file_path))

    text = await transcribe_audio(str(file_path))
    ai_reply = await generate_ai_reply(text)

    await update.message.reply_text(ai_reply)

    audio_path = text_to_speech(ai_reply)
    if audio_path:
        await update.message.reply_audio(audio_path)


if __name__ == "__main__":
    logger.info("🚀 DevOpsGuru Telegram Bot Started...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()
