import os
import logging
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from collections import defaultdict

# Configuration - این مقادیر به عنوان Secret در گیتهاب ست خواهند شد
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID"))

# دیکشنری برای شمارش پیام های کاربران قبل از استارت
# ساختار: user_id: message_count
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
    else:
        # اگر کاربر در چت خصوصی استارت کرده
        await update.message.reply_text(f"سلام {user_first_name}! برای استفاده از من، لطفا در گروه مربوطه من را استارت کن.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای پردازش تمام پیام‌های عادی در گروه."""
    # اگر پیام از گروه مورد نظر ما نبود، آن را نادیده بگیر
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    # اگر کاربر یکی از ادمین ها باشد، محدودیت اعمال نشود
    if user_id == ADMIN_ID:
        return

    # اگر کاربر ربات را استارت نکرده باشد (شمارنده برای او وجود دارد)
    if user_id in user_message_count:
        user_message_count[user_id] += 1
        message_count = user_message_count[user_id]

        if message_count > 3:
            # حذف پیام کاربر
            try:
                await update.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {e}")

            # ارسال پیام هشدار و درخواست استارت ربات
            warning_message = (
                f"👤 کاربر عزیز {user_first_name},\n"
                "متأسفانه شما اجازه ارسال پیام بیشتر را ندارید زیرا هنوز ربات را استارت نکرده‌اید.\n"
                "لطفا برای فعال‌سازی حساب و اجازه چت، ربات را از طریق لینک زیر استارت کنید:\n"
                "https://t.me/YourBotUsername?start=start"
                "\n\n پس از استارت، می‌توانید به چت ادامه دهید."
            )
            # ارسال پیام و پین کردن آن برای تاکید
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=warning_message
            )
            # حذف خودکار پیام هشدار پس از ۱ دقیقه برای جلوگیری از شلوغی گروه
            # await sent_message.delete(delay=60) # اختیاری

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای لاگ کردن خطاها."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """تابع اصلی برای راه‌اندازی ربات."""
    # ساخت اپلیکیشن و پاس دادن توکن
    application = Application.builder().token(BOT_TOKEN).build()

    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # اضافه کردن هندلر خطا
    application.add_error_handler(error_handler)

    # شروع ربات در حالت Polling (برای استفاده در GitHub Actions)
    application.run_polling()

if __name__ == "__main__":
    main()
