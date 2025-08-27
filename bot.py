import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    filters,
    ConversationHandler
)
from collections import defaultdict

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
NAME, AGE, CONFIRMATION = range(3)

# دیکشنری برای ذخیره اطلاعات کاربران
user_data = {}
# دیکشنری برای کاربران تأیید شده
verified_users = set()
# دیکشنری برای شمارش پیام های کاربران قبل از احراز هویت
user_message_count = defaultdict(int)

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start."""
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    if update.effective_chat.type in ['group', 'supergroup']:
        # اگر کاربر قبلاً احراز هویت شده
        if user_id in verified_users:
            welcome_text = f"سلام {user_first_name} عزیز! 👋\nشما قبلاً احراز هویت شده‌اید و می‌توانید آزادانه چت کنید."
            await update.message.reply_text(welcome_text)
        else:
            # شروع فرآیند احراز هویت در گروه
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

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام و نام خانوادگی"""
    user_id = update.effective_user.id
    name = update.message.text
    
    if len(name.split()) < 2:
        await update.message.reply_text("لطفا نام و نام خانوادگی را به طور کامل وارد کنید:")
        return NAME
    
    context.user_data['name'] = name
    context.user_data['user_id'] = user_id
    context.user_data['username'] = update.effective_user.username
    
    await update.message.reply_text(
        f"ممنون {name.split()[0]}! 🙏\n\nلطفا سن خود را وارد کنید:"
    )
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت سن"""
    try:
        age = int(update.message.text)
        if age < 5 or age > 120:
            await update.message.reply_text("لطفا سن معتبر وارد کنید (بین 5 تا 120):")
            return AGE
    except ValueError:
        await update.message.reply_text("لطفا سن را به صورت عدد وارد کنید:")
        return AGE
    
    context.user_data['age'] = age
    
    # ایجاد کیبورد تایید/لغو
    keyboard = [['✅ تایید اطلاعات', '❌ ویرایش مجدد']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📋 اطلاعات شما:\n\n"
        f"👤 نام: {context.user_data['name']}\n"
        f"🎂 سن: {age} سال\n\n"
        f"آیا اطلاعات صحیح است؟",
        reply_markup=reply_markup
    )
    return CONFIRMATION

async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید نهایی اطلاعات"""
    user_id = context.user_data['user_id']
    user_choice = update.message.text
    
    if user_choice == '✅ تایید اطلاعات':
        # افزودن کاربر به لیست تأیید شده
        verified_users.add(user_id)
        user_message_count[user_id] = 0  # ریست شمارنده
        
        # ارسال پیام تأیید به کاربر
        await update.message.reply_text(
            "✅ احراز هویت شما با موفقیت تکمیل شد!\n\n"
            "اکنون می‌توانید در گروه به صورت آزادانه چت کنید.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # اطلاع به ادمین
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"👤 کاربر جدید احراز هویت شد:\n\n"
                f"ID: {user_id}\n"
                f"نام: {context.user_data['name']}\n"
                f"سن: {context.user_data['age']}\n"
                f"Username: @{context.user_data['username'] or 'ندارد'}"
            )
        except Exception as e:
            logger.error(f"Error sending message to admin: {e}")
        
        logger.info(f"User {user_id} verified successfully")
        return ConversationHandler.END
        
    elif user_choice == '❌ ویرایش مجدد':
        await update.message.reply_text(
            "لطفا نام و نام خانوادگی خود را مجدداً وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME
    else:
        await update.message.reply_text("لطفا از گزینه‌های بالا انتخاب کنید:")
        return CONFIRMATION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو فرآیند احراز هویت"""
    await update.message.reply_text(
        "فرآیند احراز هویت لغو شد. هر زمان که خواستید می‌توانید با دستور /start مجدداً شروع کنید.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیام‌های گروه"""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    user_id = update.effective_user.id
    
    # اگر کاربر ادمین باشد یا احراز هویت شده باشد
    if user_id == ADMIN_ID or user_id in verified_users:
        return

    # مدیریت کاربران تأیید نشده
    user_message_count[user_id] += 1
    message_count = user_message_count[user_id]

    logger.info(f"Unverified user {user_id} message count: {message_count}")

    if message_count > 3:
        try:
            await update.message.delete()
            logger.info(f"Deleted message from unverified user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting message: {e}")

        warning_message = (
            f"👤 کاربر عزیز {update.effective_user.first_name},\n"
            "برای ارسال پیام در گروه، باید ابتدا احراز هویت شوید.\n\n"
            f"لطفا ربات را استارت کنید:\n@{(await context.bot.get_me()).username}"
        )
        
        try:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=warning_message
            )
        except Exception as e:
            logger.error(f"Error sending warning: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر خطاها"""
    logger.error(f"Error: {context.error}")

def main():
    """تابع اصلی"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # ایجاد ConversationHandler برای احراز هویت
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start_command)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
                CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_data)]
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            allow_reentry=True
        )

        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))
        application.add_error_handler(error_handler)

        logger.info("🤖 Bot is starting with authentication system...")
        print("✅ Bot started successfully!")
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
