import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from collections import defaultdict

# Configuration - با خطایابی بهتر
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
    GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])
    
    # چاپ مقادیر برای دیباگ (در لاگ گیتهاب دیده می‌شود)
    print(f"Bot Token: {BOT_TOKEN[:10]}...")  # فقط ۱۰ کاراکتر اول برای امنیت
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Group Chat ID: {GROUP_CHAT_ID}")
    
except KeyError as e:
    error_msg = f"❌ Environment variable {e} is not set! Please check your GitHub Secrets."
    print(error_msg)
    raise Exception(error_msg)
except ValueError as e:
    error_msg = f"❌ Environment variable value cannot be converted to integer: {e}"
    print(error_msg)
    raise Exception(error_msg)

# دیکشنری برای شمارش پیام های کاربران قبل از استارت
user_message_count = defaultdict(int)

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start. وقتی کاربر ربات را استارت می‌کند فراخوانی می‌شود."""
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    # اگر کاربر در گروه استارت کرده، شمارنده او را ریست می‌کنیم
    if update.effective_chat.type in ['group', 'supergroup']:
        user_message_count[user_id] = 0
        welcome_text = f"سلام {user_first_name} عزیز! 🤚\nاز اینکه ربات رو استارت کردی ممنونم. حالا می‌تونی آزادانه در گروه چت کنی."
        await update.message.reply_text(welcome_text)
        logger.info(f"User {user_id} ({user_first_name}) started the bot in group. Counter reset.")
    else:
        # اگر کاربر در چت خصوصی استارت کرده
        await update.message.reply_text(f"سلام {user_first_name}! برای استفاده از من، لطفا در گروه مربوطه من را استارت کن.")
        logger.info(f"User {user_id} started the bot in private chat.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای پردازش تمام پیام‌های عادی در گروه."""
    # اگر پیام از گروه مورد نظر ما نبود، آن را نادیده بگیر
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name
    username = update.effective_user.username

    # اگر کاربر یکی از ادمین ها باشد، محدودیت اعمال نشود
    if user_id == ADMIN_ID:
        logger.debug(f"Admin {user_id} sent message, no restriction applied.")
        return

    # اگر کاربر ربات را استارت نکرده باشد (شمارنده برای او وجود دارد)
    if user_id in user_message_count:
        user_message_count[user_id] += 1
        message_count = user_message_count[user_id]

        logger.info(f"User {user_id} ({user_first_name}) message count: {message_count}")

        if message_count > 3:
            # حذف پیام کاربر
            try:
                await update.message.delete()
                logger.info(f"Deleted message from user {user_id} (exceeded limit)")
            except Exception as e:
                logger.error(f"Error deleting message from user {user_id}: {e}")

            # ارسال پیام هشدار و درخواست استارت ربات
            warning_message = (
                f"👤 کاربر عزیز {user_first_name},\n"
                "متأسفانه شما اجازه ارسال پیام بیشتر را ندارید زیرا هنوز ربات را استارت نکرده‌اید.\n"
                "لطفا برای فعال‌سازی حساب و اجازه چت، ربات را از طریق لینک زیر استارت کنید:\n"
                "https://t.me/puyan_test_bot?start=start"  # لینک ربات خود را جایگزین کنید
                "\n\n پس از استارت، می‌توانید به چت ادامه دهید."
            )
            
            try:
                # ارسال پیام هشدار
                sent_message = await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=warning_message
                )
                logger.info(f"Sent warning message to user {user_first_name}")
                
                # حذف خودکار پیام هشدار پس از ۳۰ ثانیه برای جلوگیری از شلوغی گروه
                # await sent_message.delete(delay=30)
                
            except Exception as e:
                logger.error(f"Error sending warning message: {e}")

    else:
        # اگر کاربر برای اولین بار پیام می‌فرستد، شمارنده را ایجاد کن
        user_message_count[user_id] = 1
        logger.info(f"New user {user_id} ({user_first_name}) started chatting. Counter created.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای لاگ کردن خطاها."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """تابع اصلی برای راه‌اندازی ربات."""
    try:
        # ساخت اپلیکیشن و پاس دادن توکن
        application = Application.builder().token(BOT_TOKEN).build()

        # اضافه کردن هندلرها
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # اضافه کردن هندلر خطا
        application.add_error_handler(error_handler)

        logger.info("🤖 Bot is starting...")
        print("✅ Bot started successfully!")
        
        # شروع ربات در حالت Polling
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Bot failed to start: {e}")
        raise

if __name__ == "__main__":
    main()
