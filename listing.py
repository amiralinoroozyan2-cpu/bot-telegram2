import logging
import os
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import storage
from handlers.start import check_channel_member, main_menu_keyboard, MAIN_MENU_TEXT

logger = logging.getLogger(__name__)

CHANNEL_ID = os.environ.get("CHANNEL_ID", "@yourchannel")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# States
(GAME, TITLE, DESCRIPTION, PRICE, SCREENSHOTS, VIDEO,
 EMAIL, PASSWORD, CHANGE_EMAIL, PHONE, CONFIRM) = range(11)

GAMES = ["کلش آف کلنز ⚔️", "فری‌فایر 🔫", "پابجی 🪂", "کالاف دیوتی 💣"]
GAME_CODES = ["clash", "freefire", "pubg", "cod"]


def generate_code(length=6) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        if not storage.get_listing(code):
            return code


def game_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(g, callback_data=f"game_{GAME_CODES[i]}")] for i, g in enumerate(GAMES)]
    keyboard.append([InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")])
    return InlineKeyboardMarkup(keyboard)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")]])


async def start_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    context.user_data.clear()
    context.user_data["listing"] = {}

    await query.edit_message_text(
        "🎮 <b>ثبت آگهی فروش اکانت</b>\n\nمرحله ۱/۱۰: بازی مورد نظر را انتخاب کن:",
        parse_mode="HTML",
        reply_markup=game_keyboard()
    )
    return GAME


async def got_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    code = query.data.replace("game_", "")
    idx = GAME_CODES.index(code) if code in GAME_CODES else 0
    context.user_data["listing"]["game"] = GAMES[idx]

    await query.edit_message_text(
        f"✅ بازی: <b>{GAMES[idx]}</b>\n\n"
        "مرحله ۲/۱۰: <b>عنوان آگهی</b> را بنویس (مثلاً: اکانت تاون‌هال ۱۵ فول):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    return TITLE


async def got_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) < 3 or len(text) > 100:
        await update.message.reply_text("❌ عنوان باید بین ۳ تا ۱۰۰ کاراکتر باشد. دوباره بنویس:")
        return TITLE

    context.user_data["listing"]["title"] = text
    await update.message.reply_text(
        "مرحله ۳/۱۰: <b>توضیحات آگهی</b> را بنویس (ویژگی‌ها، سطح، آیتم‌ها و...):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    return DESCRIPTION


async def got_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["listing"]["description"] = text
    await update.message.reply_text(
        "مرحله ۴/۱۰: <b>قیمت</b> را به تومان وارد کن (فقط عدد، مثلاً: 500000):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    return PRICE


async def got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "").replace("٬", "")
    if not text.isdigit():
        await update.message.reply_text("❌ لطفاً فقط عدد وارد کن:")
        return PRICE

    context.user_data["listing"]["price"] = int(text)
    context.user_data["listing"]["screenshots"] = []

    await update.message.reply_text(
        "مرحله ۵/۱۰: <b>اسکرین‌شات‌های اکانت</b> را ارسال کن (حداقل ۱ عکس).\n"
        "وقتی تموم شد، روی دکمه «اتمام ارسال تصاویر» بزن.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ اتمام ارسال تصاویر", callback_data="done_screenshots")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")]
        ])
    )
    return SCREENSHOTS


async def got_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo
    if not photo:
        await update.message.reply_text("❌ لطفاً تصویر ارسال کن.")
        return SCREENSHOTS

    file_id = photo[-1].file_id
    context.user_data["listing"]["screenshots"].append(file_id)
    count = len(context.user_data["listing"]["screenshots"])
    await update.message.reply_text(
        f"✅ تصویر {count} دریافت شد. می‌تونی بیشتر بفرستی یا «اتمام» بزنی.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ اتمام ارسال تصاویر", callback_data="done_screenshots")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")]
        ])
    )
    return SCREENSHOTS


async def done_screenshots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not context.user_data["listing"].get("screenshots"):
        await query.answer("❌ حداقل یک تصویر ارسال کن!", show_alert=True)
        return SCREENSHOTS

    await query.edit_message_text(
        "مرحله ۶/۱۰: <b>فیلم از اکانت</b> ارسال کن (اختیاری).\n"
        "برای رد کردن این مرحله روی دکمه بزن.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ رد کردن این مرحله", callback_data="skip_video")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")]
        ])
    )
    return VIDEO


async def got_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ لطفاً فیلم ارسال کن یا روی «رد کردن» بزن.")
        return VIDEO

    context.user_data["listing"]["video"] = video.file_id
    return await ask_email(update, context, is_callback=False)


async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["listing"]["video"] = None
    await query.edit_message_text(
        "مرحله ۷/۱۰: <b>ایمیل اکانت</b> را وارد کن:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    return EMAIL


async def ask_email(update, context, is_callback=True):
    text = "مرحله ۷/۱۰: <b>ایمیل اکانت</b> را وارد کن:"
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=cancel_keyboard())
    return EMAIL


async def got_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["listing"]["email"] = text
    await update.message.reply_text(
        "مرحله ۸/۱۰: <b>رمز عبور اکانت</b> را وارد کن:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    return PASSWORD


async def got_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["listing"]["password"] = text
    await update.message.reply_text(
        "مرحله ۹/۱۰: آیا مایل به <b>تغییر ایمیل اکانت</b> پس از فروش هستی؟",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله", callback_data="changeemail_yes"),
             InlineKeyboardButton("❌ خیر", callback_data="changeemail_no")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")]
        ])
    )
    return CHANGE_EMAIL


async def got_change_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["listing"]["change_email"] = query.data == "changeemail_yes"
    await query.edit_message_text(
        "مرحله ۱۰/۱۰: <b>شماره تماس</b> خود را وارد کن (برای ارتباط ادمین در صورت نیاز):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    return PHONE


async def got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["listing"]["phone"] = text
    return await show_summary(update, context)


async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lst = context.user_data["listing"]
    price_formatted = f"{lst['price']:,}"
    change_email_text = "بله ✅" if lst.get("change_email") else "خیر ❌"
    screenshots_count = len(lst.get("screenshots", []))
    has_video = "✅ دارد" if lst.get("video") else "❌ ندارد"

    text = (
        "📋 <b>خلاصه آگهی شما:</b>\n\n"
        f"🎮 بازی: <b>{lst.get('game', '-')}</b>\n"
        f"📌 عنوان: <b>{lst.get('title', '-')}</b>\n"
        f"📝 توضیحات: {lst.get('description', '-')}\n"
        f"💰 قیمت: <b>{price_formatted} تومان</b>\n"
        f"🖼 تعداد تصاویر: {screenshots_count}\n"
        f"🎬 فیلم: {has_video}\n"
        f"🔄 تغییر ایمیل پس از فروش: {change_email_text}\n\n"
        "آیا تأیید می‌کنی؟"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تأیید و ثبت آگهی", callback_data="confirm_listing")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel_listing")]
        ])
    )
    return CONFIRM


async def confirm_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lst = context.user_data["listing"]

    code = generate_code()
    now = datetime.utcnow().isoformat()

    listing_data = {
        "code": code,
        "seller_id": user.id,
        "game": lst["game"],
        "title": lst["title"],
        "description": lst["description"],
        "price": lst["price"],
        "screenshots": lst.get("screenshots", []),
        "video": lst.get("video"),
        "email": lst["email"],
        "password": lst["password"],
        "change_email": lst.get("change_email", False),
        "phone": lst.get("phone", ""),
        "status": "active",
        "channel_message_id": None,
        "created_at": now,
        "buyer_id": None,
        "pending_buyer_id": None,
        "purchase_confirmed_at": None,
        "seller_delivered": False,
    }
    storage.save_listing(code, listing_data)

    # Post to channel
    channel_msg_id = await post_to_channel(context.bot, listing_data, code)
    if channel_msg_id:
        storage.update_listing(code, {"channel_message_id": channel_msg_id})

    await query.edit_message_text(
        f"✅ <b>آگهی شما با موفقیت ثبت شد!</b>\n\n"
        f"🔑 کد یکتای آگهی: <code>{code}</code>\n\n"
        "این کد را ذخیره کن. خریداران با این کد می‌توانند آگهی شما را پیدا کنند.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]
        ])
    )

    context.user_data.clear()
    return ConversationHandler.END


async def post_to_channel(bot, listing: dict, code: str) -> int | None:
    price_formatted = f"{listing['price']:,}"
    change_email_text = "بله ✅" if listing.get("change_email") else "خیر ❌"

    caption = (
        f"🎮 <b>{listing['game']}</b>\n\n"
        f"📌 <b>{listing['title']}</b>\n\n"
        f"📝 {listing['description']}\n\n"
        f"💰 قیمت: <b>{price_formatted} تومان</b>\n"
        f"🔄 تغییر ایمیل پس از فروش: {change_email_text}\n\n"
        f"🔑 کد آگهی: <code>{code}</code>\n\n"
        "برای خرید ربات را استارت بزن و کد آگهی را وارد کن."
    )

    try:
        screenshots = listing.get("screenshots", [])
        video = listing.get("video")

        if screenshots:
            from telegram import InputMediaPhoto
            media = [InputMediaPhoto(media=fid) for fid in screenshots]
            media[0] = InputMediaPhoto(media=screenshots[0], caption=caption, parse_mode="HTML")
            msgs = await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
            first_msg_id = msgs[0].message_id

            if video:
                await bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=video,
                    caption=f"🎬 فیلم آگهی کد: <code>{code}</code>",
                    parse_mode="HTML"
                )
            return first_msg_id
        else:
            msg = await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="HTML")
            return msg.message_id
    except Exception as e:
        logger.error(f"Error posting to channel: {e}")
        return None


async def cancel_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        entry_points=[CallbackQueryHandler(start_listing, pattern="^menu_sell$")],
        states={
            GAME: [CallbackQueryHandler(got_game, pattern="^game_")],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_description)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_price)],
            SCREENSHOTS: [
                MessageHandler(filters.PHOTO, got_screenshot),
                CallbackQueryHandler(done_screenshots, pattern="^done_screenshots$"),
            ],
            VIDEO: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, got_video),
                CallbackQueryHandler(skip_video, pattern="^skip_video$"),
            ],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_email)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_password)],
            CHANGE_EMAIL: [CallbackQueryHandler(got_change_email, pattern="^changeemail_")],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_phone)],
            CONFIRM: [CallbackQueryHandler(confirm_listing, pattern="^confirm_listing$")],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_listing, pattern="^cancel_listing$"),
        ],
        per_message=False,
    )
