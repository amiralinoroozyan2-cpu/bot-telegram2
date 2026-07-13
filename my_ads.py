import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import storage
from handlers.start import check_channel_member, main_menu_keyboard, MAIN_MENU_TEXT

logger = logging.getLogger(__name__)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@yourchannel")

STATUS_MAP = {
    "pending": "⏳ در انتظار",
    "active": "✅ فعال",
    "sold": "💰 فروخته‌شده",
    "deleted": "🗑 حذف‌شده",
}


async def my_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if storage.is_banned(user.id):
        await query.edit_message_text("🚫 شما از ربات مسدود شده‌اید.")
        return

    if not await check_channel_member(user.id, context.bot):
        from handlers.start import send_join_request
        await send_join_request(update, context)
        return

    listings = storage.get_user_listings(user.id)

    if not listings:
        await query.edit_message_text(
            "📋 <b>آگهی‌های من</b>\n\nهنوز هیچ آگهی‌ای ثبت نکرده‌ای.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 ثبت آگهی جدید", callback_data="menu_sell")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
            ])
        )
        return

    text = "📋 <b>آگهی‌های من:</b>\n\n"
    keyboard = []

    for lst in listings[-10:]:  # Show last 10
        code = lst["code"]
        status = STATUS_MAP.get(lst.get("status", ""), lst.get("status", ""))
        price_formatted = f"{lst['price']:,}"
        text += (
            f"🔑 کد: <code>{code}</code>\n"
            f"📌 {lst['title']}\n"
            f"💰 {price_formatted} تومان — {status}\n\n"
        )

        if lst.get("status") in ("active", "pending"):
            keyboard.append([
                InlineKeyboardButton(f"🗑 حذف {code}", callback_data=f"delete_ad_{code}")
            ])

    keyboard.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")])
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    code = query.data.split("_", 2)[2].upper()
    listing = storage.get_listing(code)

    if not listing:
        await query.answer("❌ آگهی یافت نشد.", show_alert=True)
        return

    if listing.get("seller_id") != user.id:
        await query.answer("❌ این آگهی متعلق به شما نیست.", show_alert=True)
        return

    if listing.get("status") not in ("active", "pending"):
        await query.answer("❌ این آگهی قابل حذف نیست.", show_alert=True)
        return

    # Show confirmation
    await query.edit_message_text(
        f"آیا مطمئنی که می‌خوای آگهی <code>{code}</code> را حذف کنی؟",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"confirm_delete_{code}"),
                InlineKeyboardButton("❌ خیر", callback_data="menu_myads")
            ]
        ])
    )


async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    code = query.data.split("_", 2)[2].upper()
    listing = storage.get_listing(code)

    if not listing or listing.get("seller_id") != user.id:
        await query.edit_message_text("❌ خطا در حذف آگهی.")
        return

    storage.update_listing(code, {"status": "deleted"})

    # Delete from channel
    channel_msg_id = listing.get("channel_message_id")
    if channel_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=CHANNEL_ID,
                message_id=channel_msg_id
            )
        except Exception as e:
            logger.warning(f"Could not delete channel message: {e}")

    await query.edit_message_text(
        f"✅ آگهی <code>{code}</code> با موفقیت حذف شد.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 آگهی‌های من", callback_data="menu_myads")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ])
    )


def get_handlers():
    return [
        CallbackQueryHandler(my_ads_menu, pattern="^menu_myads$"),
        CallbackQueryHandler(delete_ad_callback, pattern=r"^delete_ad_"),
        CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_delete_"),
    ]
