import logging
import sqlite3
import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 设置管理员 Telegram ID
ADMIN_ID = 1373704387  

# 1. 建立极构 Flask HTTP 服务器（给 Render 检查存活）
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Winverse Bot is Running Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

# 2. Telegram Bot 逻辑
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    """)
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, user.username, user.first_name)
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"你好 {user.first_name}！欢迎关注 Winverse，你已成功订阅我们的最新通知！"
    )

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"你的 Telegram ID 是: {update.effective_user.id}")

# 📊 统计订阅人数
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        await update.message.reply_text("⛔ 只有管理员可以查看统计数据！")
        return

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()

    await update.message.reply_text(f"📊 **Winverse Bot 当前订阅统计**\n\n目前共有 **{count}** 位订阅用户。")

# 📋 查看具体订阅者名单（用户名 + 姓名）
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        await update.message.reply_text("⛔ 只有管理员可以查看用户名单！")
        return

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name FROM users")
    users = cursor.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("ℹ️ 目前还没有任何用户订阅。")
        return

    text = f"👥 **Winverse Bot 订阅者名单 (共 {len(users)} 人)**\n\n"
    for idx, (u_id, username, first_name) in enumerate(users, 1):
        name_str = first_name if first_name else "未设定姓名"
        user_str = f"@{username}" if username else "无 Username"
        text += f"{idx}. **{name_str}** ({user_str}) - ID: `{u_id}`\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        await update.message.reply_text("⛔ 只有管理员可以使用广播功能！")
        return

    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("⚠️ 请输入广播内容！\n格式如：/broadcast 今晚8点活动开始！")
        return

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    success_count = 0
    fail_count = 0
    await update.message.reply_text(f"📢 开始向 {len(users)} 位用户发送广播...")

    for user in users:
        user_id = user[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"✅ 广播完成！\n成功发送：{success_count} 人\n失败/封锁：{fail_count} 人"
    )

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()

    # 后台线程启动 Web 端口，满足 Render Free 要求
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    token = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    bot_app = ApplicationBuilder().token(token).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("id", get_id))
    bot_app.add_handler(CommandHandler("stats", stats))
    bot_app.add_handler(CommandHandler("users", users_list))
    bot_app.add_handler(CommandHandler("broadcast", broadcast))

    print("🤖 Winverse Bot Web 模式启动成功！")
    bot_app.run_polling()
