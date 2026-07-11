import logging
import os
import threading
import psycopg2
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 设置管理员 Telegram ID
ADMIN_ID = 1373704387  

# 获取数据库连接串
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        # 给链接自动加上 sslmode=require 防断连
        url = DATABASE_URL
        if "sslmode=" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
        return psycopg2.connect(url, connect_timeout=10)
    else:
        import sqlite3
        return sqlite3.connect("users.db")

# 1. 极简 Flask HTTP 服务器
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Winverse Bot is Running Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

# 2. 初始化数据库
def init_db():
    if DATABASE_URL:
        print("🔗 成功检测到 DATABASE_URL，正在连接 Supabase PostgreSQL 数据库...")
    else:
        print("⚠️ 未检测到 DATABASE_URL，回退使用本地 SQLite 数据库！")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if DATABASE_URL:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT
                );
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT
                )
            """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ 数据库初始化/建表成功！")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_URL:
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE 
                SET username = EXCLUDED.username, first_name = EXCLUDED.first_name;
            """, (user.id, user.username, user.first_name))
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user.id, user.username, user.first_name)
            )
            
        conn.commit()
        cursor.close()
        conn.close()
        
        await update.message.reply_text(
            f"你好 {user.first_name}！欢迎关注 Winverse，你已成功订阅我们的最新通知！"
        )
    except Exception as e:
        print(f"❌ /start 写入数据库失败: {e}")
        await update.message.reply_text(f"你好 {user.first_name}！欢迎关注 Winverse！")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"你的 Telegram ID 是: {update.effective_user.id}")

# 📊 统计订阅人数
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        await update.message.reply_text("⛔ 只有管理员可以查看统计数据！")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        await update.message.reply_text(f"📊 **Winverse Bot 当前订阅统计**\n\n目前共有 **{count}** 位订阅用户。")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 读取数据库失败: {e}")

# 📋 查看具体订阅者名单
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        await update.message.reply_text("⛔ 只有管理员可以查看用户名单！")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, first_name FROM users;")
        users = cursor.fetchall()
        cursor.close()
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
    except Exception as e:
        await update.message.reply_text(f"⚠️ 读取名单失败: {e}")

# 📢 广播函数
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = update.effective_user.id
    if ADMIN_ID != 0 and sender_id != ADMIN_ID:
        return

    msg = update.message
    caption_or_text = msg.caption if msg.photo else msg.text

    if not caption_or_text or not caption_or_text.startswith("/broadcast"):
        return

    message_text = caption_or_text.replace("/broadcast", "", 1).lstrip(" :：")

    if not message_text and not msg.photo:
        await msg.reply_text("⚠️ 请输入广播内容！")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users;")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        await msg.reply_text(f"⚠️ 广播获取用户失败: {e}")
        return

    if not users:
        await msg.reply_text("ℹ️ 目前没有任何用户订阅，无法发送广播。")
        return

    success_count = 0
    fail_count = 0
    await msg.reply_text(f"📢 开始向 {len(users)} 位用户发送广播...")

    photo_file_id = msg.photo[-1].file_id if msg.photo else None

    for user in users:
        user_id = user[0]
        try:
            if photo_file_id:
                await context.bot.send_photo(chat_id=user_id, photo=photo_file_id, caption=message_text)
            else:
                await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception:
            fail_count += 1

    await msg.reply_text(
        f"✅ 广播完成！\n成功发送：{success_count} 人\n失败/封锁：{fail_count} 人"
    )

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()

    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    token = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    bot_app = ApplicationBuilder().token(token).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("id", get_id))
    bot_app.add_handler(CommandHandler("stats", stats))
    bot_app.add_handler(CommandHandler("users", users_list))
    
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^/broadcast'), handle_broadcast))
    bot_app.add_handler(MessageHandler(filters.PHOTO, handle_broadcast))

    print("🤖 Winverse Bot 启动成功！")
    bot_app.run_polling()

