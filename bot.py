import logging
import sqlite3
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import TelegramError, Forbidden

# 设置你的 Telegram Admin ID (你的个人 Telegram 数字 ID)
# 如果不知道，可以填 0，或者先留空，等下可以用 /id 获取
ADMIN_ID = 1373704387 

# 初始化数据库
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

# /start 命令：记录用户
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

# /id 命令：方便查看你自己的 ID
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"你的 Telegram ID 是: {user_id}")

# /broadcast 命令：广播消息（格式：/broadcast 要发送的内容）
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    
    # 安全检查：如果设置了 ADMIN_ID，只有管理员能发
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        await update.message.reply_text("⛔ 只有管理员可以使用广播功能！")
        return

    # 获取广播内容
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
        except Forbidden:
            # 用户退订或封锁了 Bot，自动忽略
            fail_count += 1
        except TelegramError:
            fail_count += 1

    await update.message.reply_text(
        f"✅ 广播完成！\n成功发送：{success_count} 人\n失败/封锁：{fail_count} 人"
    )

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    init_db()

    # 读取 Token，优先读取环境变量，没有则使用默认值
    token = os.getenv("BOT_TOKEN", "8548350902:AAEQ5-jepn7NwlOfzve092999Wn1lTL19Sc")
    
    if token == "YOUR_BOT_TOKEN_HERE":
        print("❌ 错误：请先设置你的 Bot Token！")
        exit()

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("broadcast", broadcast))

    print("🤖 Winverse Bot 启动成功，监听中...")
    app.run_polling()