import os
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound, RequestError, TooManyRequests

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "").strip()

def detect_lang(text: str) -> str:
    """Rough detection: if it contains Khmer characters, it's Khmer, otherwise English."""
    for ch in text:
        if "\u1780" <= ch <= "\u17ff":
            return "km"
    return "en"

def safe_translate(text: str, src: str, dest: str, retries: int = 2) -> str:
    """Translate with retries and clear error messages."""
    for attempt in range(retries + 1):
        try:
            result = GoogleTranslator(source=src, target=dest).translate(text)
            if result and result.strip():
                return result
            # If empty result, treat as failure
            raise TranslationNotFound("Empty result")
        except (TranslationNotFound, RequestError, TooManyRequests) as e:
            logger.warning(f"Translate attempt {attempt+1} failed: {e}")
            if attempt < retries:
                time.sleep(2)  # Wait 2 seconds before retrying
            else:
                return "⚠️ Translation service is temporarily unavailable. Please try again later."
        except Exception as e:
            logger.exception("Unexpected translate error")
            return f"⚠️ Translation error: {e}"

async def auto_translate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    src = detect_lang(text)
    dest = "en" if src == "km" else "km"
    flag_src = "🇰🇭" if src == "km" else "🇬🇧"
    flag_dest = "🇬🇧" if dest == "en" else "🇰🇭"

    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    result = safe_translate(text, src, dest)

    await update.message.reply_text(
        f"{flag_src} *Original:*\n{text}\n\n{flag_dest} *Translation:*\n{result}",
        parse_mode="Markdown",
    )

# /km and /en commands also use safe_translate, logic is the same
# ... (other commands same as before) ...

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN missing")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_translate))
    # ... add other handlers ...
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
