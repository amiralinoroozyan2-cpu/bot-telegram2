import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import storage

logger = logging.getLogger(__name__)

CHANNEL_ID = os.environ.get("CHANNEL_ID", "@yourchannel")

MAIN_MENU_TEXT = (
    "🎮 <b>به ربات خرید و فروش اکانت بازی خوش اومدی!</b>\n\n"
    "از منوی زیر یکی رو انتخاب کن:"
)

WARNING_TEXT = (
    "⚠️ <b>هشدار مهم</b>\n\n"
    "در صورت کلاهبرداری، فروش اکانت دزدی، یا وارد کردن اطلاعات نادرست،\n"
    "🚫 کاربر برای <b>همیشه</b> از ربات مسدود می‌شود\n"
    "📢 اطلاعات او به ادمین گزارش می‌گردد\n\n"
    "با ادامه استفاده این قوانین را می‌پذیری."
)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 ثبت آگهی فروش اکانت", callback_data="menu_sell")],
        [InlineKeyboardButton("🛒 خرید اکانت", callback_data="menu_buy")],
        [InlineKeyboardButton("📋 مدیریت آگهی‌های من", callback_data="menu_myads")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def check_channel_member(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception as e:
        logger.warning(f"Could not check membership for {user_id}: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    storage.upsert_user(user.id, user.username, user.first_name)

    if storage.is_banned(user.id):
        await update.message.reply_text("🚫 شما از ربات مسدود شده‌اید.")
        return

    # Check channel membership
    is_member = await check_channel_member(user.id, context.bot)
    if not is_member:
        await send_join_request(update, context)
        return

    # Show warning once
    if not storage.is_warned(user.id):
        storage.mark_warned(user.id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ متوجه شدم، ادامه", callback_data="accept_warning")]
        ])
        await update.message.reply_text(WARNING_TEXT, parse_mode="HTML", reply_markup=keyboard)
        return

    await update.message.reply_text(
        MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


async def send_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_link = CHANNEL_ID if CHANNEL_ID.startswith("http") else f"https://t.me/{CHANNEL_ID.lstrip('@')}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=channel_link)],
        [InlineKeyboardButton("🔄 بررسی مجدد عضویت", callback_data="check_membership")]
    ])
    text = (
        "❌ <b>برای استفاده از ربات باید ابتدا در کانال ما عضو بشی.</b>\n\n"
        "بعد از عضویت روی «بررسی مجدد عضویت» بزن."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if storage.is_banned(user.id):
        await query.edit_message_text("🚫 شما از ربات مسدود شده‌اید.")
        return

    is_member = await check_channel_member(user.id, context.bot)
    if not is_member:
        await send_join_request(update, context)
        return

    storage.upsert_user(user.id, user.username, user.first_name)

    if not storage.is_warned(user.id):
        storage.mark_warned(user.id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ متوجه شدم، ادامه", callback_data="accept_warning")]
        ])
        await query.edit_message_text(WARNING_TEXT, parse_mode="HTML", reply_markup=keyboard)
        return

    await query.edit_message_text(MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard())


async def accept_warning_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard())


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if storage.is_banned(user.id):
        await query.edit_message_text("🚫 شما از ربات مسدود شده‌اید.")
        return

    is_member = await check_channel_member(user.id, context.bot)
    if not is_member:
        await send_join_request(update, context)
        return

    await query.edit_message_text(MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard())


def get_handlers():
    return [
        CommandHandler("start", start),
        CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"),
        CallbackQueryHandler(accept_warning_callback, pattern="^accept_warning$"),
        CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
    ]
