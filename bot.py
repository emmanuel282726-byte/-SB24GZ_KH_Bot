import os
import io
import time
import asyncio
import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# ---------- 语言检测 ----------
def detect_lang(text: str) -> str:
    for ch in text:
        if "\u1780" <= ch <= "\u17ff":
            return "km"
    return "en"

# ---------- 翻译：直接调用 MyMemory 官方 API ----------
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

async def translate_text(text: str, src: str, dest: str) -> str:
    """调用 MyMemory 公开 API，无需密钥。单次最多 500 字节。"""
    if len(text.encode("utf-8")) > 500:
        # 超长截断，避免接口报错
        text = text[:200]

    langpair = f"{src}|{dest}"
    params = {"q": text, "langpair": langpair}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MYMEMORY_URL, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning(f"MyMemory HTTP {resp.status}")
                    return "⚠️ 翻译服务暂时不可用，请稍后重试。"

                data = await resp.json()
                translated = data.get("responseData", {}).get("translatedText", "")

                if not translated or translated == text:
                    # 检查是否有错误信息
                    details = data.get("responseDetails", "")
                    if details:
                        logger.warning(f"MyMemory error: {details}")
                    return "⚠️ 翻译失败，请稍后重试或换一段文字。"

                return translated

    except asyncio.TimeoutError:
        logger.error("MyMemory timeout")
        return "⚠️ 翻译超时，请检查网络后重试。"
    except Exception as e:
        logger.exception("MyMemory request failed")
        return f"⚠️ 翻译出错：{e}"

# ---------- 菜单 ----------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇰🇭 → 🇬🇧 高棉语翻译成英语", callback_data="km2en")],
        [InlineKeyboardButton("🇬🇧 → 🇰🇭 英语翻译成高棉语", callback_data="en2km")],
        [InlineKeyboardButton("🔁 自动检测", callback_data="auto")],
        [InlineKeyboardButton("ℹ️ 关于", callback_data="about")],
    ])

# ---------- 命令处理 ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 欢迎使用 *SB24GZ KH Bot*！\n\n"
        "发送任意文字，我会自动检测语言并翻译：\n"
        "• 高棉语 → 英语\n"
        "• 英语 → 高棉语\n\n"
        "也可以使用下方菜单 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *用法：*\n"
        "• 直接发送文字 → 自动翻译\n"
        "• `/km <文字>` → 翻译成高棉语\n"
        "• `/en <文字>` → 翻译成英语\n"
        "• 点击菜单按钮切换模式",
        parse_mode="Markdown",
    )

async def about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()
        await q.edit_message_text(
            "🤖 *SB24GZ KH Bot*\n高棉语 ⇄ 英语翻译机器人。\n基于 MyMemory 官方 API。\n部署在 Railway 🚂",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    else:
        await update.message.reply_text("🤖 SB24GZ KH Bot — 高棉语 ⇄ 英语翻译")

async def km_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args)
    if not text:
        return await update.message.reply_text("用法：`/km <文字>`", parse_mode="Markdown")
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    result = await translate_text(text, "auto", "km")
    await update.message.reply_text(f"🇰🇭 *高棉语：*\n{result}", parse_mode="Markdown")

async def en_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = " ".join(ctx.args)
    if not text:
        return await update.message.reply_text("用法：`/en <文字>`", parse_mode="Markdown")
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    result = await translate_text(text, "auto", "en")
    await update.message.reply_text(f"🇬🇧 *英语：*\n{result}", parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "about":
        return await about(update, ctx)
    prompts = {
        "km2en": "🇰🇭→🇬🇧 请发送 *高棉语* 文字。",
        "en2km": "🇬🇧→🇰🇭 请发送 *英语* 文字。",
        "auto": "🔁 发送任意文字，我会自动检测语言。",
    }
    await q.edit_message_text(prompts.get(q.data, "OK"), parse_mode="Markdown")

# ---------- 核心：自动翻译 ----------
async def auto_translate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    logger.info(f"📩 收到消息: {text[:30]}")

    src = detect_lang(text)
    dest = "en" if src == "km" else "km"
    flag_src = "🇰🇭" if src == "km" else "🇬🇧"
    flag_dest = "🇬🇧" if dest == "en" else "🇰🇭"

    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    result = await translate_text(text, src, dest)

    await update.message.reply_text(
        f"{flag_src} *原文：*\n{text}\n\n"
        f"{flag_dest} *翻译：*\n{result}",
        parse_mode="Markdown",
    )

# ---------- 轮询健康监控（解决"在线不回复"）----------
async def polling_supervisor(app: Application):
    """每 30 秒检查一次是否还活着，如果 120 秒没有动静就强制重启 polling。"""
    last_heartbeat = time.time()

    async def heartbeat():
        nonlocal last_heartbeat
        last_heartbeat = time.time()

    # 启动时先记录
    heartbeat()

    while True:
        await asyncio.sleep(30)
        if time.time() - last_heartbeat > 120:
            logger.warning("⚠️ Polling 可能已停滞，正在强制重启...")
            try:
                await app.updater.stop()
                await asyncio.sleep(2)
                await app.updater.start_polling(drop_pending_updates=True)
                heartbeat()
                logger.info("✅ Polling 已重启")
            except Exception as e:
                logger.error(f"重启 polling 失败: {e}")

# ---------- 主入口 ----------
async def post_init(app: Application):
    logger.info("✅ Bot 初始化完成，开始轮询...")
    # 启动监控任务
    asyncio.create_task(polling_supervisor(app))

def main():
    if not TOKEN:
        logger.error("❌ BOT_TOKEN 未设置！请在 Railway Variables 中添加。")
        time.sleep(30)
        raise SystemExit(1)

    if ":" not in TOKEN or len(TOKEN) < 40:
        logger.error("❌ BOT_TOKEN 格式看起来不对。")
        time.sleep(30)
        raise SystemExit(1)

    logger.info(f"🚀 启动 SB24GZ KH Bot，Token 长度={len(TOKEN)}")

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("km", km_cmd))
    app.add_handler(CommandHandler("en", en_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_translate))

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
