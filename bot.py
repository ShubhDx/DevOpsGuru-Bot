# force redeploy
import os
import tempfile
import logging
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from openai import OpenAI

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "DevOpsGuru")
TTS_LANG = os.getenv("TTS_LANG", "hi")

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Transcribe voice using Whisper (OpenAI)
def transcribe_audio(audio_path):
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    return transcript.text


# Generate Hinglish AI reply
def generate_ai_reply(prompt, user_name="Student"):
    system_message = (
        f"You are {BOT_NAME}, a friendly DevOps mentor speaking Hinglish. "
        f"Explain simply, give examples, shortcuts, and DevOps commands."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400
    )

    return response.choices[0].message["content"]


# Convert text to mp3 for Telegram
def text_to_speech(text):
    tts = gTTS(text=text, lang=TTS_LANG)
    tmp_path = Path(tempfile.gettempdir()) / f"voice_{os.getpid()}.mp3"
    tts.save(str(tmp_path))
    return str(tmp_path)


# Handle text messages
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name or "Student"
    text = update.message.text

    reply_text = generate_ai_reply(text, user)

    await update.message.reply_text(reply_text)

    # Send voice reply
    try:
        voice_file = text_to_speech(reply_text)
        await update.message.reply_voice(open(voice_file, "rb"))
        os.remove(voice_file)
    except Exception as e:
        logger.error(f"Voice reply error: {e}")


# Handle voice messages
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name or "Student"
    voice = update.message.voice

    if not voice:
        return await update.message.reply_text("Voice not found.")

    file = await context.bot.get_file(voice.file_id)
    tmp_dir = tempfile.gettempdir()
    ogg_path = Path(tmp_dir) / "input.ogg"

    await file.download_to_drive(str(ogg_path))

    # Whisper transcription
    text = transcribe_audio(str(ogg_path))
    await update.message.reply_text(f"Transcribed: {text}")

    # AI reply
    reply_text = generate_ai_reply(text, user)
    await update.message.reply_text(reply_text)

    # Voice output
    voice_path = text_to_speech(reply_text)
    await update.message.reply_voice(open(voice_path, "rb"))
    os.remove(voice_path)


# MAIN BOT STARTER
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        raise ValueError("Missing TELEGRAM_TOKEN or OPENAI_API_KEY")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("🚀 DevOpsGuruAiBot is running...")
    app.run_polling()
