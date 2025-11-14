import os
import tempfile
import logging
import subprocess
from dotenv import load_dotenv
from pathlib import Path
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from gtts import gTTS

# Load env
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
BOT_NAME = os.getenv('BOT_NAME', 'DevOpsGuru')
TTS_LANG = os.getenv('TTS_LANG', 'hi')

openai.api_key = OPENAI_API_KEY

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Convert ogg voice → mp3 using ffmpeg
def convert_to_mp3(input_path: str, output_path: str):
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', '16000', '-ac', '1', output_path
    ]
    subprocess.run(cmd, check=True)


# Transcribe audio using Whisper
def transcribe_audio(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    return transcript.text if hasattr(transcript, "text") else ""


# Generate AI chat response in Hinglish
def get_chat_response(prompt_text: str, user_name: str = "Student") -> str:
    system_prompt = (
        f"You are {BOT_NAME}, a friendly DevOps mentor speaking Hinglish "
        f"(mix of Hindi & English). Explain concepts simply, give short examples, "
        f"command snippets, and quizzes when asked."
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_name} asked: {prompt_text}"}
        ],
        max_tokens=400
    )

    reply = response.choices[0].message["content"]
    return reply


# Convert text → speech (gTTS → ogg)
def text_to_speech_and_prepare_ogg(text: str) -> str:
    with tempfile.TemporaryDirectory() as td:
        mp3_path = Path(td) / 'speech.mp3'
        ogg_path = Path(td) / 'speech.ogg'

        # gTTS conversion
        tts = gTTS(text=text, lang=TTS_LANG)
        tts.save(str(mp3_path))

        # Convert mp3 → ogg for Telegram
        cmd = [
            'ffmpeg', '-y', '-i', str(mp3_path),
            '-c:a', 'libopus', '-b:a', '64k', str(ogg_path)
        ]
        subprocess.run(cmd, check=True)

        # Move to temp
        final_path = Path(tempfile.gettempdir()) / f"resp_{os.getpid()}.ogg"
        if final_path.exists():
            final_path.unlink()
        final_path.write_bytes(ogg_path.read_bytes())

        return str(final_path)


# Handle text input from user
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name or "Student"
    text = update.message.text

    reply = get_chat_response(text, user_name)
    await update.message.reply_text(reply)

    try:
        voice_path = text_to_speech_and_prepare_ogg(reply)
        with open(voice_path, 'rb') as f:
            await update.message.reply_voice(f)
        os.remove(voice_path)
    except Exception as e:
        logger.error("TTS failed", e)


# Handle voice messages
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name or 'Student'
    voice = update.message.voice

    if not voice:
        await update.message.reply_text("Voice message not found.")
        return

    file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as td:
        ogg_path = Path(td) / "input.ogg"
        mp3_path = Path(td) / "input.mp3"

        await file.download_to_drive(str(ogg_path))

        try:
            convert_to_mp3(str(ogg_path), str(mp3_path))
        except Exception as e:
            logger.exception("ffmpeg conversion failed")
            await update.message.reply_text("Audio processing error.")
            return

        # Whisper transcription
        text = transcribe_audio(str(mp3_path))
        await update.message.reply_text(f"Transcribed: {text}")

        # AI mentor reply
        reply = get_chat_response(text, user_name)
        await update.message.reply_text(reply)

        # Voice reply
        try:
            voice_path = text_to_speech_and_prepare_ogg(reply)
            with open(voice_path, 'rb') as f:
                await update.message.reply_voice(f)
            os.remove(voice_path)
        except Exception:
            await update.message.reply_text("Voice reply failed.")


# Start the bot
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        print("Missing TELEGRAM_TOKEN or OPENAI_API_KEY in .env")
        exit()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("DevOpsGuru bot is running...")
    app.run_polling()
