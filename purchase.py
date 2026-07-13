import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import storage
from handlers.start import check_channel_member, main_menu_keyboard, MAIN_MENU_TEXT

logger = logging.getLogger(__name__)

CARD_NUMBER = os.environ.get("CARD_NUMBER", "6037XXXXXXXXXXXX")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

ENTER_CODE, UPLOAD_RECEIPT = range(2)


async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if storage.is_banned(user.id):
        await query.edit_message_text("🚫 شما از ربات مسدود شده‌اید.")
        return ConversationHandler.END

    if not await check_channel_member(user.id, context.bot):
        from handlers.start import send_join_request
        await send_join_request(update, context)
        return ConversationHandler.END

    await query.edit_message_text(
        "🛒 <b>خرید اکانت</b>\n\n"
        "کد یکتای آگهی را که از کانال کپی کردی وارد کن:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_purchase")]
        ])
    )
    return ENTER_CODE


async def got_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    listing = storage.get_listing(code)

    if not listing:
        await update.message.reply_text(
            "❌ آگهی با این کد یافت نشد. دوباره امتحان کن:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ لغو", callback_data="cancel_purchase")]
            ])
        )
        return ENTER_CODE

    if listing.get("status") != "active":
        status_map = {
            "sold": "فروخته شده",
            "deleted": "حذف شده",
            "pending": "در انتظار تأیید"
        }
        status_text = status_map.get(listing.get("status", ""), listing.get("status", ""))
        await update.message.reply_text(
            f"❌ این آگهی «{status_text}» است و قابل خرید نیست.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return ConversationHandler.END

    if listing.get("seller_id") == update.effective_user.id:
        await update.message.reply_text(
            "❌ نمی‌تونی آگهی خودت رو بخری!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return ConversationHandler.END

    context.user_data["purchase_code"] = code
    price_formatted = f"{listing['price']:,}"

    text = (
        f"📋 <b>اطلاعات آگهی</b>\n\n"
        f"🎮 بازی: <b>{listing['game']}</b>\n"
        f"📌 عنوان: <b>{listing['title']}</b>\n"
        f"📝 {listing['description']}\n"
        f"💰 قیمت: <b>{price_formatted} تومان</b>\n\n"
        f"💳 <b>شماره کارت برای واریز:</b>\n<code>{CARD_NUMBER}</code>\n\n"
        "⚠️ <b>هشدار مهم:</b> در صورت ارسال رسید جعلی، اکانت به شما تحویل داده نخواهد شد "
        "و شما از ربات مسدود می‌شوید.\n\n"
        "بعد از پرداخت، تصویر رسید را ارسال کن:"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_purchase")]
        ])
    )
    return UPLOAD_RECEIPT


async def got_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo
    if not photo:
        await update.message.reply_text(
            "❌ لطفاً تصویر رسید پرداخت را ارسال کن:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ لغو", callback_data="cancel_purchase")]
            ])
        )
        return UPLOAD_RECEIPT

    code = context.user_data.get("purchase_code", "")
    listing = storage.get_listing(code)

    if not listing or listing.get("status") != "active":
        await update.message.reply_text(
            "❌ این آگهی دیگر در دسترس نیست.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )
        context.user_data.clear()
        return ConversationHandler.END

    buyer = update.effective_user
    receipt_file_id = photo[-1].file_id

    # Save pending buyer
    storage.update_listing(code, {"pending_buyer_id": buyer.id})

    price_formatted = f"{listing['price']:,}"
    seller_info = storage.get_user(listing["seller_id"])
    seller_name = ""
    if seller_info:
        seller_name = f"@{seller_info['username']}" if seller_info.get("username") else seller_info.get("first_name", str(listing["seller_id"]))

    admin_text = (
        f"💰 <b>درخواست خرید جدید</b>\n\n"
        f"🔑 کد آگهی: <code>{code}</code>\n"
        f"🎮 بازی: <b>{listing['game']}</b>\n"
        f"📌 آگهی: <b>{listing['title']}</b>\n"
        f"💵 قیمت: <b>{price_formatted} تومان</b>\n\n"
        f"👤 فروشنده: {seller_name} (<code>{listing['seller_id']}</code>)\n"
        f"🛒 خریدار: @{buyer.username or ''} (<code>{buyer.id}</code>)\n"
        f"نام خریدار: {buyer.first_name}\n\n"
        "لطفاً رسید زیر را بررسی کن:"
    )

    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید خرید", callback_data=f"admin_confirm_{code}"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin_reject_{code}")
        ],
        [InlineKeyboardButton("🚫 رد + مسدود کردن خریدار", callback_data=f"admin_rejectban_{code}")]
    ])

    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text, parse_mode="HTML")
            await context.bot.send_photo(
                admin_id,
                photo=receipt_file_id,
                caption=f"رسید خرید کد: <code>{code}</code>",
                parse_mode="HTML",
                reply_markup=admin_keyboard
            )
            sent_count += 1
        except Exception as e:
            logger.warning(f"Could not send to admin {admin_id}: {e}")

    if sent_count > 0:
        await update.message.reply_text(
            "✅ <b>رسید شما دریافت شد و برای ادمین ارسال گردید.</b>\n\n"
            "بعد از بررسی و تأیید، اطلاع‌رسانی خواهید شد.\n"
            "⏳ معمولاً ظرف چند ساعت بررسی می‌شود.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )
    else:
        await update.message.reply_text(
            "⚠️ در ارسال به ادمین مشکلی پیش آمد. لطفاً مستقیم با ادمین تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            MAIN_MENU_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END


def get_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_purchase, pattern="^menu_buy$")],
        states={
            ENTER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_code)],
            UPLOAD_RECEIPT: [MessageHandler(filters.PHOTO, got_receipt)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_purchase, pattern="^cancel_purchase$"),
        ],
        per_message=False,
    )
