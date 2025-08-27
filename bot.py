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

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل مدیریت برای ادمین"""
    if update.effective_user.id != ADMIN_ID:
        return

    # محاسبه آمار
    total_verified = len(verified_users)
    total_pending = len(pending_approvals)
    total_blocked = len(blocked_users)
    
    # ایجاد کیبورد پنل ادمین
    admin_keyboard = [
        ['📊 آمار کاربران', '📋 کاربران در انتظار'],
        ['✅ کاربران تأیید شده', '❌ کاربران مسدود شده'],
        ['🔄 بروزرسانی پنل']
    ]
    reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
    
    stats_message = (
        "👨‍💼 پنل مدیریت ربات\n\n"
        f"📊 آمار کلی:\n"
        f"✅ کاربران تأیید شده: {total_verified} نفر\n"
        f"⏳ کاربران در انتظار: {total_pending} نفر\n"
        f"❌ کاربران مسدود شده: {total_blocked} نفر\n\n"
        "لطفا گزینه مورد نظر را انتخاب کنید:"
    )
    
    await update.message.reply_text(stats_message, reply_markup=reply_markup)

async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار کاربران"""
    if update.effective_user.id != ADMIN_ID:
        return

    total_verified = len(verified_users)
    total_pending = len(pending_approvals)
    total_blocked = len(blocked_users)
    
    stats_message = (
        "📊 آمار کاربران:\n\n"
        f"✅ کاربران تأیید شده: {total_verified} نفر\n"
        f"⏳ کاربران در انتظار: {total_pending} نفر\n"
        f"❌ کاربران مسدود شده: {total_blocked} نفر\n\n"
        f"📈 مجموع کاربران: {total_verified + total_pending + total_blocked} نفر"
    )
    
    await update.message.reply_text(stats_message)

async def show_pending_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کاربران در انتظار تأیید"""
    if update.effective_user.id != ADMIN_ID:
        return

    if not pending_approvals:
        await update.message.reply_text("⏳ هیچ کاربری در انتظار تأیید نیست.")
        return

    pending_list = "📋 کاربران در انتظار تأیید:\n\n"
    for user_id, data in pending_approvals.items():
        pending_list += (
            f"👤 User ID: {user_id}\n"
            f"📛 نام: {data['name']}\n"
            f"📱 تلفن: {data['phone']}\n"
            f"🕒 ثبت: {data.get('registration_time', 'نامشخص')}\n"
            f"────────────────────\n"
        )
    
    await update.message.reply_text(pending_list[:4000])  # محدودیت طول پیام

async def show_verified_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کاربران تأیید شده"""
    if update.effective_user.id != ADMIN_ID:
        return

    if not verified_users:
        await update.message.reply_text("✅ هیچ کاربر تأیید شده‌ای وجود ندارد.")
        return

    verified_list = "✅ کاربران تأیید شده:\n\n"
    for user_id in list(verified_users)[:20]:  # نمایش 20 کاربر اول
        reg_date = user_registration_date.get(user_id, 'نامشخص')
        verified_list += f"👤 User ID: {user_id} - 📅 {reg_date}\n"
    
    if len(verified_users) > 20:
        verified_list += f"\n📈 و {len(verified_users) - 20} کاربر دیگر..."
    
    await update.message.reply_text(verified_list)

async def show_blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش کاربران مسدود شده"""
    if update.effective_user.id != ADMIN_ID:
        return

    if not blocked_users:
        await update.message.reply_text("❌ هیچ کاربر مسدود شده‌ای وجود ندارد.")
        return

    blocked_list = "❌ کاربران مسدود شده:\n\n"
    for user_id in list(blocked_users)[:20]:  # نمایش 20 کاربر اول
        blocked_list += f"👤 User ID: {user_id}\n"
    
    if len(blocked_users) > 20:
        blocked_list += f"\n📈 و {len(blocked_users) - 20} کاربر دیگر..."
    
    await update.message.reply_text(blocked_list)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start."""
    user_id = update.effective_user.id
    user_first_name = update.effective_user.first_name

    # دستور /admin برای نمایش پنل مدیریت
    if update.message.text == '/admin' and user_id == ADMIN_ID:
        await admin_panel(update, context)
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
            welcome_text = f"سلام {user_first_name} عزیز! 👋\nشما قبلاً احراز هویت شده‌اید."
            await update.message.reply_text(welcome_text)
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

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام و نام خانوادگی"""
    user_id = update.effective_user.id
    
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
    
    if user_id in blocked_users:
        await update.message.reply_text("❌ حساب شما مسدود شده است.")
        return ConversationHandler.END

    if update.message.contact:
        phone_number = update.message.contact.phone_number
        context.user_data['phone'] = phone_number
    else:
        phone_number = update.message.text
        context.user_data['phone'] = phone_number

    await update.message.reply_text(
        "📸 لطفا مرحله اول اسکرین شات مربوط به سایت مسکن ملی را مانند نمونه ارسال کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return SCREENSHOT

async def get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت اسکرین شات"""
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        await update.message.reply_text("❌ حساب شما مسدود شده است.")
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text("❌ لطفا یک عکس ارسال کنید:")
        return SCREENSHOT

    # ذخیره اطلاعات عکس
    context.user_data['screenshot_file_id'] = update.message.photo[-1].file_id
    
    keyboard = [['✅ تایید اطلاعات', '❌ ویرایش مجدد']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📋 اطلاعات شما:\n\n"
        f"👤 نام: {context.user_data['name']}\n"
        f"📱 شماره تماس: {context.user_data['phone']}\n"
        f"📸 اسکرین شات: ✅ ارسال شد\n\n"
        f"آیا اطلاعات صحیح است؟",
        reply_markup=reply_markup
    )
    return CONFIRMATION

async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید نهایی اطلاعات و ارسال برای تأیید ادمین"""
    user_id = context.user_data['user_id']
    user_choice = update.message.text
    
    if user_choice == '✅ تایید اطلاعات':
        # ذخیره زمان ثبت نام
        reg_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context.user_data['registration_time'] = reg_time
        user_registration_date[user_id] = reg_time
        
        # ذخیره اطلاعات در pending_approvals
        pending_approvals[user_id] = context.user_data.copy()
        
        await update.message.reply_text(
            "⏳ اطلاعات شما برای تأیید به ادمین ارسال شد.\n"
            "لطفا منتظر تأیید ادمین بمانید.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # ارسال اطلاعات به ادمین با عکس
        try:
            admin_keyboard = [
                [f'✅ تایید کاربر {user_id}', f'❌ رد کاربر {user_id}']
            ]
            admin_reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
            
            # ارسال عکس به ادمین
            await context.bot.send_photo(
                ADMIN_ID,
                photo=context.user_data['screenshot_file_id'],
                caption=(
                    f"👤 درخواست احراز هویت جدید:\n\n"
                    f"🆔 User ID: {user_id}\n"
                    f"📛 نام: {context.user_data['name']}\n"
                    f"📱 شماره: {context.user_data['phone']}\n"
                    f"👤 First Name: {context.user_data['first_name']}\n"
                    f"🔗 Username: @{context.user_data['username'] or 'ندارد'}\n"
                    f"🕒 زمان ثبت: {reg_time}\n\n"
                    f"لطفا کاربر را تأیید یا رد کنید:"
                ),
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
        try:
            user_id = int(message_text.split()[-1])
        except:
            await update.message.reply_text("❌ خطا در پردازش درخواست")
            return

        if user_id in pending_approvals:
            verified_users.add(user_id)
            user_data = pending_approvals.pop(user_id)
            
            try:
                await context.bot.send_message(
                    user_id,
                    "✅ حساب شما توسط ادمین تأیید شد!\n\n"
                    "اکنون می‌توانید در گروه به صورت آزادانه چت کنید. 🎉"
                )
            except Exception as e:
                logger.error(f"Error sending approval message to user: {e}")
            
            await update.message.reply_text(
                f"✅ کاربر {user_id} تأیید شد.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            logger.info(f"User {user_id} approved by admin")
        else:
            await update.message.reply_text("❌ کاربر یافت نشد.")
    
    elif '❌ رد کاربر' in message_text:
        try:
            user_id = int(message_text.split()[-1])
        except:
            await update.message.reply_text("❌ خطا در پردازش درخواست")
            return

        if user_id in pending_approvals:
            blocked_users.add(user_id)
            user_data = pending_approvals.pop(user_id)
            
            try:
                await context.bot.send_message(
                    user_id,
                    "❌ درخواست احراز هویت شما توسط ادمین رد شد.\n\n"
                    "لطفا با ادمین تماس بگیرید."
                )
            except Exception as e:
                logger.error(f"Error sending rejection message to user: {e}")
            
            await update.message.reply_text(
                f"❌ کاربر {user_id} رد شد و مسدود گردید.",
                reply_markup=ReplyKeyboardRemove()
            )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو فرآیند احراز هویت"""
    await update.message.reply_text(
        "فرآیند احراز هویت لغو شد. با دستور /start می‌توانید مجدداً شروع کنید.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیام‌های گروه"""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        try:
            await update.message.delete()
        except:
            pass
        return

    if user_id == ADMIN_ID or user_id in verified_users:
        return

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

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستورات پنل ادمین"""
    if update.effective_user.id != ADMIN_ID:
        return

    command = update.message.text
    
    if command == '📊 آمار کاربران':
        await show_user_stats(update, context)
    elif command == '📋 کاربران در انتظار':
        await show_pending_users(update, context)
    elif command == '✅ کاربران تأیید شده':
        await show_verified_users(update, context)
    elif command == '❌ کاربران مسدود شده':
        await show_blocked_users(update, context)
    elif command == '🔄 بروزرسانی پنل':
        await admin_panel(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر خطاها"""
    logger.error(f"Error: {context.error}")

def main():
    """تابع اصلی"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # ConversationHandler برای احراز هویت
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
        application.add_handler(CommandHandler('admin', admin_panel))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_approval))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_commands))
        application.add_error_handler(error_handler)

        logger.info("🤖 Bot is starting with admin panel and screenshot system...")
        print("✅ Bot started successfully!")
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
