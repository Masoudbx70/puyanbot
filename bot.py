import os
import logging
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
NAME, PHONE, CONFIRMATION = range(3)

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

    # بررسی اگر کاربر مسدود شده
    if user_id in blocked_users:
        await update.message.reply_text(
            "❌ حساب شما مسدود شده است. لطفا با ادمین تماس بگیرید.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    if update.effective_chat.type in ['group', 'supergroup']:
        # اگر کاربر قبلاً احراز هویت شده
        if user_id in verified_users:
            welcome_text = f"سلام {user_first_name} عزیز! 👋\nشما قبلاً احراز هویت شده‌اید."
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
    
    # بررسی اگر کاربر مسدود شده
    if user_id in blocked_users:
        await update.message.reply_text("❌ حساب شما مسدود شده است.")
        return ConversationHandler.END

    name = update.message.text
    
    if len(name.split()) < 2:
        await update.message.reply_text("لطفا نام و نام خانوادگی را به طور کامل وارد کنید:")
        return NAME
    
    context.user_data['name'] = name
    context.user_data['user_id'] = user_id
    context.user_data['username'] = update.effective_user.username
    context.user_data['first_name'] = update.effective_user.first_name

    # ایجاد دکمه اشتراک گذاری شماره تماس
    phone_button = KeyboardButton("📱 ارسال شماره تماس", request_contact=True)
    keyboard = [[phone_button]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"ممنون {name.split()[0]}! 🙏\n\n"
        "لطفا شماره تماس خود را ارسال کنید:",
        reply_markup=reply_markup
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت شماره تماس"""
    user_id = update.effective_user.id
    
    # بررسی اگر کاربر مسدود شده
    if user_id in blocked_users:
        await update.message.reply_text("❌ حساب شما مسدود شده است.")
        return ConversationHandler.END

    if update.message.contact:
        phone_number = update.message.contact.phone_number
        context.user_data['phone'] = phone_number
    else:
        # اگر کاربر به صورت دستی شماره وارد کرد
        phone_number = update.message.text
        context.user_data['phone'] = phone_number

    # ایجاد کیبورد تایید/لغو
    keyboard = [['✅ تایید اطلاعات', '❌ ویرایش مجدد']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📋 اطلاعات شما:\n\n"
        f"👤 نام: {context.user_data['name']}\n"
        f"📱 شماره تماس: {context.user_data['phone']}\n\n"
        f"آیا اطلاعات صحیح است؟",
        reply_markup=reply_markup
    )
    return CONFIRMATION

async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید نهایی اطلاعات و ارسال برای تأیید ادمین"""
    user_id = context.user_data['user_id']
    user_choice = update.message.text
    
    if user_choice == '✅ تایید اطلاعات':
        # ذخیره اطلاعات در pending_approvals
        pending_approvals[user_id] = context.user_data.copy()
        
        # ارسال پیام انتظار به کاربر
        await update.message.reply_text(
            "⏳ اطلاعات شما برای تأیید به ادمین ارسال شد.\n"
            "لطفا منتظر تأیید ادمین بمانید. پس از تأیید می‌توانید در گروه چت کنید.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # ارسال اطلاعات به ادمین برای تأیید
        try:
            # ایجاد کیبورد برای ادمین
            admin_keyboard = [
                [f'✅ تایید کاربر {user_id}', f'❌ رد کاربر {user_id}']
            ]
            admin_reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
            
            await context.bot.send_message(
                ADMIN_ID,
                f"👤 درخواست احراز هویت جدید:\n\n"
                f"🆔 User ID: {user_id}\n"
                f"👤 نام: {context.user_data['name']}\n"
                f"📱 شماره: {context.user_data['phone']}\n"
                f"👤 First Name: {context.user_data['first_name']}\n"
                f"🔗 Username: @{context.user_data['username'] or 'ندارد'}\n\n"
                f"لطفا کاربر را تأیید یا رد کنید:",
                reply_markup=admin_reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending message to admin: {e}")
            await update.message.reply_text("❌ خطا در ارسال اطلاعات. لطفا بعدا تلاش کنید.")
        
        logger.info(f"User {user_id} waiting for admin approval")
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

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر تأیید/رد کاربر توسط ادمین"""
    if update.effective_user.id != ADMIN_ID:
        return

    message_text = update.message.text
    
    if '✅ تایید کاربر' in message_text:
        # استخراج user_id از پیام
        try:
            user_id = int(message_text.split()[-1])
        except:
            await update.message.reply_text("❌ خطا در پردازش درخواست")
            return

        if user_id in pending_approvals:
            # تأیید کاربر
            verified_users.add(user_id)
            user_data = pending_approvals.pop(user_id)
            
            # ارسال پیام تأیید به کاربر
            try:
                await context.bot.send_message(
                    user_id,
                    "✅ حساب شما توسط ادمین تأیید شد!\n\n"
                    "اکنون می‌توانید در گروه به صورت آزادانه چت کنید. 🎉"
                )
            except Exception as e:
                logger.error(f"Error sending approval message to user: {e}")
            
            # پاسخ به ادمین
            await update.message.reply_text(
                f"✅ کاربر {user_id} تأیید شد و اکنون می‌تواند در گروه چت کند.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            logger.info(f"User {user_id} approved by admin")
        else:
            await update.message.reply_text("❌ کاربر یافت نشد یا قبلاً پردازش شده است.")
    
    elif '❌ رد کاربر' in message_text:
        # استخراج user_id از پیام
        try:
            user_id = int(message_text.split()[-1])
        except:
            await update.message.reply_text("❌ خطا در پردازش درخواست")
            return

        if user_id in pending_approvals:
            # مسدود کردن کاربر
            blocked_users.add(user_id)
            user_data = pending_approvals.pop(user_id)
            
            # ارسال پیام رد به کاربر
            try:
                await context.bot.send_message(
                    user_id,
                    "❌ درخواست احراز هویت شما توسط ادمین رد شد.\n\n"
                    "لطفا با ادمین تماس بگیرید."
                )
            except Exception as e:
                logger.error(f"Error sending rejection message to user: {e}")
            
            # پاسخ به ادمین
            await update.message.reply_text(
                f"❌ کاربر {user_id} رد شد و مسدود گردید.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            logger.info(f"User {user_id} rejected by admin")

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
    
    # اگر کاربر مسدود شده باشد
    if user_id in blocked_users:
        try:
            await update.message.delete()
        except:
            pass
        return

    # اگر کاربر ادمین باشد یا احراز هویت شده باشد
    if user_id == ADMIN_ID or user_id in verified_users:
        return

    # مدیریت کاربران تأیید نشده
    user_message_count[user_id] += 1
    message_count = user_message_count[user_id]

    if message_count > 3:
        try:
            await update.message.delete()
        except Exception as e:
            logger.error(f"Error deleting message: {e}")

        warning_message = (
            f"👤 کاربر عزیز {update.effective_user.first_name},\n"
            "برای ارسال پیام در گروه، باید ابتدا احراز هویت شوید.\n\n"
            f"لطفا ربات را استارت کنید:\n@{(await context.bot.get_me()).username}"
        )
        
        try:
            await context.bot.send_message(
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
                PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), get_phone)],
                CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_data)]
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            allow_reentry=True
        )

        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_approval))
        application.add_error_handler(error_handler)

        logger.info("🤖 Bot is starting with admin approval system...")
        print("✅ Bot started successfully!")
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
