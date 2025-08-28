import os
import logging
import time
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    filters,
    ConversationHandler
)
from collections import defaultdict
from datetime import datetime

# Configuration
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
    GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])
    
    print(f"Bot Token: {BOT_TOKEN[:10]}...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Group Chat ID: {GROUP_CHAT_ID}")
    
except (KeyError, ValueError) as e:
    print(f"❌ Configuration error: {e}")
    raise

# حالت‌های مکالمه برای احراز هویت
NAME, PHONE, SCREENSHOT, CONFIRMATION = range(4)

# دیکشنری برای ذخیره اطلاعات کاربران
user_data = {}
# دیکشنری برای کاربران تأیید شده
verified_users = set()
# دیکشنری برای کاربران مسدود شده
blocked_users = set()
# دیکشنری برای شمارش پیام های کاربران قبل از احراز هویت
user_message_count = defaultdict(int)
# دیکشنری برای ذخیره پیام‌های در انتظار تأیید ادمین
pending_approvals = {}
# تاریخ ثبت نام کاربران
user_registration_date = {}

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تابع برای ذخیره وضعیت ربات (اختیاری)
def save_bot_state():
    """ذخیره وضعیت ربات در فایل"""
    try:
        state = {
            'verified_users': list(verified_users),
            'blocked_users': list(blocked_users),
            'pending_approvals': pending_approvals,
            'user_registration_date': user_registration_date
        }
        # می‌توانید این اطلاعات را در فایل یا دیتابیس ذخیره کنید
        print("💾 Bot state saved")
    except Exception as e:
        logger.error(f"Error saving state: {e}")

# تابع برای بارگذاری وضعیت ربات (اختیاری)
def load_bot_state():
    """بارگذاری وضعیت ربات از فایل"""
    try:
        # می‌توانید وضعیت را از فایل یا دیتابیس بارگذاری کنید
        print("💾 Bot state loaded")
    except Exception as e:
        logger.error(f"Error loading state: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start."""
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    # اگر کاربر ادمین باشد، پنل مدیریت نمایش داده شود
    if user_id == ADMIN_ID:
        await show_admin_panel(update, context)
        return

    # بررسی اگر کاربر مسدود شده
    if user_id in blocked_users:
        await update.message.reply_text(
            "❌ حساب شما مسدود شده است. لطفا با ادمین تماس بگیرید.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    if update.effective_chat.type in ['group', 'supergroup']:
        if user_id in verified_users:
            # کاربر قبلاً احراز هویت شده
            return
        else:
            await update.message.reply_text(
                f"سلام {user_first_name} عزیز! 👋\nبرای فعال‌سازی حساب، لطفا ربات را در چت خصوصی استارت کنید:\n@{(await context.bot.get_me()).username}",
                reply_markup=ReplyKeyboardRemove()
            )
    else:
        # شروع فرآیند احراز هویت در چت خصوصی
        context.user_data.clear()
        await update.message.reply_text(
            "سلام! خوش آمدید. 👋\nبرای تکمیل احراز هویت، لطفا اطلاعات زیر را وارد کنید.\n\n"
            "لطفا نام و نام خانوادگی خود را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME

# بقیه توابع بدون تغییر (همانند کد قبلی)
# [همه توابع قبلی اینجا قرار می‌گیرند]
# ...

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر خطاها"""
    logger.error(f"Error: {context.error}")
    # ذخیره وضعیت هنگام خطا
    save_bot_state()

async def health_check(context: ContextTypes.DEFAULT_TYPE):
    """چک کردن سلامت ربات"""
    try:
        await context.bot.get_me()
        print(f"❤️ Health check passed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        # restart ربات در صورت نیاز

def main():
    """تابع اصلی با سیستم restart اتوماتیک"""
    max_retries = 5
    retry_delay = 30  # ثانیه
    
    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting bot (Attempt {attempt + 1}/{max_retries})...")
            
            application = Application.builder().token(BOT_TOKEN).build()

            # بارگذاری وضعیت قبلی
            load_bot_state()

            # اضافه کردن هندلرها
            application.add_handler(MessageHandler(filters.TEXT & filters.Chat(chat_id=ADMIN_ID), handle_admin_commands))
            application.add_handler(MessageHandler(filters.TEXT & filters.Chat(chat_id=ADMIN_ID), handle_admin_approval))
            
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', start_command)],
                states={
                    NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                    PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_phone)],
                    SCREENSHOT: [MessageHandler(filters.PHOTO, get_screenshot)],
                    CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_data)]
                },
                fallbacks=[CommandHandler('cancel', cancel)],
                allow_reentry=True
            )

            application.add_handler(conv_handler)
            application.add_handler(MessageHandler(filters.TEXT & filters.Chat(chat_id=GROUP_CHAT_ID), handle_group_messages))
            application.add_error_handler(error_handler)

            # اضافه کردن health check دوره‌ای
            job_queue = application.job_queue
            if job_queue:
                job_queue.run_repeating(health_check, interval=300, first=10)  # هر 5 دقیقه

            logger.info("🤖 Bot is starting with professional admin panel...")
            print("✅ Bot started successfully!")
            
            # اجرای ربات
            application.run_polling(
                poll_interval=1.0,
                timeout=10,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"❌ Bot crashed on attempt {attempt + 1}: {e}")
            
            # ذخیره وضعیت قبل از restart
            save_bot_state()
            
            if attempt < max_retries - 1:
                print(f"⏳ Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # افزایش تاخیر برای retry بعدی
            else:
                print("❌ Max retries reached. Bot stopped.")
                # ارسال通知 به ادمین در صورت crash
                try:
                    # می‌توانید اینجا به ادمین پیام بدهید
                    pass
                except:
                    pass
                raise

if __name__ == "__main__":
    main()