import os
import io
import time
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, InlineQueryHandler,
    ContextTypes, filters
)
from deep_translator import GoogleTranslator
from deep_translator.exceptions import LanguageNotSupportedException

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Config ----------
TOKEN = os.environ.get("BOT_TOKEN", "").strip()

if not TOKEN:
    logger.error("❌ BOT_TOKEN is not set in Railway Variables!")
    time.sleep(60)
    raise SystemExit(1)

if ":" not in TOKEN or len(TOKEN) < 40:
    logger.error("❌ BOT_TOKEN looks invalid")
    time.sleep(60)
    raise SystemExit(1)

logger.info("✅ BOT_TOKEN loaded (length=%d)", len(TOKEN))

# ---------- Language helpers ----------
# Khmer = 'km', English = 'en'
KHMER = "km"
ENGLISH = "en"

def detect_lang(text: str) -> str:
    """Rudimentary detection: Khmer Unicode block = U+1780–U+17FF."""
    for ch in text:
        if "\u1780" <= ch <= "\u17ff":
            return KHMER
    return ENGLISH

def translate(text: str, src: str, dest: str) -> str:
    try:
        return GoogleTranslator(source=src, target=dest).translate(text)
    except LanguageNotSupportedException as e:
        return f"⚠️ Language not supported: {e}"
    except Exception as e:
        logger.exception("Translation failed")
        return f"⚠️ Translation error: {e}"

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇰🇭 → 🇬🇧 Khmer to English", callback_data="km2en")],
        [InlineKeyboardButton("🇬🇧 → 🇰🇭 English to Khmer", callback_data="en2km")],
        [InlineKeyboardButton("🔁 Auto-detect", callback_data="auto")],
        [InlineKeyboardButton("🌐 Other languages (/tr)", callback_data="other")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")],
    ])

# ---------- Commands ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *SB24GZ KH Bot*!\n\n"
        "I translate between *Khmer 🇰🇭* and *English 🇬🇧*.\n\n"
        "Just send me any text — I'll auto-detect the language.\n\n"
        "• `/tr <lang> <text>` — translate to any language\n"
        "• `/km <text>` — force Khmer\n"
        "• `/en <text>` — force English\n"
        "• `@SB24GZ_KH_Bot <text>` in any chat — inline translate",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How to use:*\n\n"
        "• Send text → auto-translate Khmer ⇄ English\n"
        "• `/km <text>` → translate to Khmer\n"
        "• `/en <text>` → translate to English\n"
        "• `/tr <code> <text>` → translate to any language (e.g. `/tr fr hello`)\n"
        "• Type `@SB24GZ_KH_Bot <text>` in any chat for inline translation",
        parse_mode="Markdown",
    )

async def about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text(
            "🤖 *SB24GZ KH Bot*\nKhmer ⇄ English translator.\nPowered by Google Translate.\nDeployed on Railway 🚂",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    else:
        await update.message.reply_text(
            "🤖 *SB24GZ KH Bot*\nKhmer ⇄ English translator.",
            parse_mode="Markdown",
        )

async def km_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args)
    if not text:
        return await update.message.reply_text("Usage: `/km <text>`", parse_mode="Markdown")
    result = translate(text, "auto", KHMER)
    await update.message.reply_text(
        f"🇰🇭 *Khmer:*\n{result}", parse_mode="Markdown"
    )

async def en_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args)
    if not text:
        return await update.message.reply_text("Usage: `/en <text>`", parse_mode="Markdown")
    result = translate(text, "auto", ENGLISH)
    await update.message.reply_text(
        f"🇬🇧 *English:*\n{result}", parse_mode="Markdown"
    )

async def tr_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        return await update.message.reply_text(
            "Usage: `/tr <lang_code> <text>`\nExample: `/tr fr hello world`",
            parse_mode="Markdown",
        )
    lang = ctx.args[0].lower()
    text = " ".join(ctx.args[1:])
    result = translate(text, "auto", lang)
    await update.message.reply_text(
        f"🌐 *{lang.upper()}:*\n{result}", parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "about":
        return await about(update, ctx)
    prompts = {
        "km2en": "🇰🇭→🇬🇧 Send me *Khmer text* to translate to English.",
        "en2km": "🇬🇧→🇰🇭 Send me *English text* to translate to Khmer.",
        "auto": "🔁 Send any text — I'll auto-detect the language.",
        "other": "🌐 Use `/tr <lang_code> <text>` — e.g. `/tr fr hello`",
    }
    await q.edit_message_text(prompts.get(q.data, "OK"), parse_mode="Markdown")

# ---------- Auto translate (main feature) ----------
async def auto_translate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    src = detect_lang(text)
    dest = ENGLISH if src == KHMER else KHMER
    flag_src = "🇰🇭" if src == KHMER else "🇬🇧"
    flag_dest = "🇬🇧" if dest == ENGLISH else "🇰🇭"

    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    result = translate(text, src, dest)

    await update.message.reply_text(
        f"{flag_src} *Original:*\n{text}\n\n"
        f"{flag_dest} *Translation:*\n{result}",
        parse_mode="Markdown",
    )

# ---------- Inline mode ----------
async def inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query.strip():
        return

    src = detect_lang(query)
    dest = ENGLISH if src == KHMER else KHMER
    result = translate(query, src, dest)

    articles = [
        InlineQueryResultArticle(
            id="auto",
            title=f"Translate → {'English' if dest == ENGLISH else 'Khmer'}",
            description=result,
            input_message_content=InputTextMessageContent(
                f"🌐 *{query}*\n➡️ *{result}*",
                parse_mode="Markdown",
            ),
        )
    ]
    await update.inline_query.answer(articles, cache_time=0)

# ---------- Error handler ----------
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=ctx.error)

# ---------- Main ----------
def main():
    logger.info("🚀 Starting SB24GZ KH Bot...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("km", km_cmd))
    app.add_handler(CommandHandler("en", en_cmd))
    app.add_handler(CommandHandler("tr", tr_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_translate))
    app.add_error_handler(error_handler)

    logger.info("✅ Bot is polling for updates...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
