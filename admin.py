import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import storage

logger = logging.getLogger(__name__)

ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

BROADCAST_TEXT = 0


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    all_users = storage.get_all_users()
    total = len(all_users)
    banned = [u for u in all_users if u.get("banned")]

    text = f"👥 <b>آمار کاربران</b>\n\n"
    text += f"• کل کاربران: <b>{total}</b>\n"
    text += f"• مسدودشده‌ها: <b>{len(banned)}</b>\n\n"

    if banned:
        text += "🚫 <b>کاربران مسدود:</b>\n"
        for u in banned[:20]:
            uname = f"@{u['username']}" if u.get("username") else u.get("first_name", "")
            text += f"  • {uname} (<code>{u['id']}</code>)\n"
        if len(banned) > 20:
            text += f"  ... و {len(banned) - 20} نفر دیگر"

    await update.message.reply_text(text, parse_mode="HTML")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ استفاده: /ban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ آیدی عددی وارد کن.")
        return

    storage.ban_user(target_id)
    try:
        await context.bot.send_message(target_id, "🚫 شما از ربات مسدود شده‌اید.")
    except Exception:
        pass

    await update.message.reply_text(f"✅ کاربر {target_id} مسدود شد.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ استفاده: /unban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ آیدی عددی وارد کن.")
        return

    storage.unban_user(target_id)
    try:
        await context.bot.send_message(target_id, "✅ مسدودیت شما برداشته شد. می‌توانید دوباره از ربات استفاده کنید.")
    except Exception:
        pass

    await update.message.reply_text(f"✅ کاربر {target_id} آزاد شد.")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "📢 متن پیام همگانی را ارسال کن.\n(برای لغو: /cancel)",
    )
    return BROADCAST_TEXT


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text
    all_users = storage.get_all_users()
    sent = 0
    failed = 0

    status_msg = await update.message.reply_text("⏳ در حال ارسال...")

    for user in all_users:
        if user.get("banned"):
            continue
        try:
            await context.bot.send_message(user["id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ پیام همگانی ارسال شد.\n• موفق: {sent}\n• ناموفق: {failed}"
    )
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ارسال پیام همگانی لغو شد.")
    return ConversationHandler.END


# ── Confirm/Reject purchase (called from purchase handler) ──────────────────

async def admin_confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # admin_confirm_{code} or admin_reject_{code}
    parts = data.split("_", 2)
    action = parts[1]
    code = parts[2].upper()

    listing = storage.get_listing(code)
    if not listing:
        await query.edit_message_text("❌ آگهی یافت نشد.")
        return

    if listing.get("status") == "sold":
        await query.edit_message_text("⚠️ این آگهی قبلاً تأیید شده.")
        return

    buyer_id = listing.get("pending_buyer_id")
    seller_id = listing.get("seller_id")

    if action == "confirm":
        await _handle_confirm(query, context, listing, code, buyer_id, seller_id)
    elif action == "reject":
        await _handle_reject(query, context, listing, code, buyer_id)
    elif action == "rejectban":
        await _handle_reject(query, context, listing, code, buyer_id, ban=True)


async def _handle_confirm(query, context, listing, code, buyer_id, seller_id):
    # Update listing
    from datetime import datetime
    storage.update_listing(code, {
        "status": "sold",
        "buyer_id": buyer_id,
        "purchase_confirmed_at": datetime.utcnow().isoformat(),
    })

    # Delete channel post
    channel_msg_id = listing.get("channel_message_id")
    if channel_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=os.environ.get("CHANNEL_ID", "@yourchannel"),
                message_id=channel_msg_id
            )
        except Exception as e:
            logger.warning(f"Could not delete channel message: {e}")

    # Notify buyer
    try:
        await context.bot.send_message(
            buyer_id,
            f"✅ <b>پرداخت شما تأیید شد!</b>\n\n"
            f"🎮 آگهی: <b>{listing['title']}</b>\n"
            f"اطلاعات تماس فروشنده برای ارتباط مستقیم به ادمین اعلام خواهد شد.\n"
            f"اطلاعات اکانت پس از تحویل توسط فروشنده ارسال می‌شود.\n\n"
            f"کد آگهی: <code>{code}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify buyer {buyer_id}: {e}")

    # Notify seller
    try:
        seller_info = storage.get_user(buyer_id)
        buyer_contact = ""
        if seller_info and seller_info.get("username"):
            buyer_contact = f"@{seller_info['username']}"
        else:
            buyer_contact = f"ID: {buyer_id}"

        await context.bot.send_message(
            seller_id,
            f"🎉 <b>آگهی شما خریداری شد!</b>\n\n"
            f"🎮 آگهی: <b>{listing['title']}</b>\n"
            f"خریدار: {buyer_contact}\n\n"
            f"⏰ ادمین با شما تماس می‌گیرد. لطفاً <b>ظرف ۷۲ ساعت</b> اطلاعات اکانت را تحویل دهید.\n"
            f"در غیر این صورت به‌طور خودکار مسدود خواهید شد.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ اطلاعات را تحویل دادم", callback_data=f"seller_delivered_{code}")]
            ])
        )
    except Exception as e:
        logger.warning(f"Could not notify seller {seller_id}: {e}")

    # Schedule 72h ban job
    context.job_queue.run_once(
        _auto_ban_seller,
        when=72 * 3600,
        data={"seller_id": seller_id, "code": code},
        name=f"auto_ban_{code}"
    )

    # Send full account info to admin
    admin_info = (
        f"✅ <b>تأیید خرید کد {code}</b>\n\n"
        f"📧 ایمیل: <code>{listing.get('email', '-')}</code>\n"
        f"🔑 رمز عبور: <code>{listing.get('password', '-')}</code>\n"
        f"📱 شماره فروشنده: <code>{listing.get('phone', '-')}</code>\n"
        f"👤 فروشنده ID: <code>{seller_id}</code>\n"
        f"👤 خریدار ID: <code>{buyer_id}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_info, parse_mode="HTML")
        except Exception:
            pass

    await query.edit_message_text(
        query.message.text + "\n\n✅ <b>تأیید شد.</b>",
        parse_mode="HTML"
    )


async def _handle_reject(query, context, listing, code, buyer_id, ban=False):
    storage.update_listing(code, {"pending_buyer_id": None, "status": "active"})

    if ban and buyer_id:
        storage.ban_user(buyer_id)

    try:
        msg = (
            f"❌ <b>پرداخت شما رد شد.</b>\n"
            f"رسید ارسال‌شده تأیید نشد."
        )
        if ban:
            msg += "\n🚫 شما از ربات مسدود شده‌اید."
        await context.bot.send_message(buyer_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not notify buyer {buyer_id}: {e}")

    await query.edit_message_text(
        query.message.text + "\n\n❌ <b>رد شد.</b>" + (" (خریدار مسدود شد)" if ban else ""),
        parse_mode="HTML"
    )


async def _auto_ban_seller(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    seller_id = data["seller_id"]
    code = data["code"]

    listing = storage.get_listing(code)
    if not listing:
        return

    if listing.get("seller_delivered"):
        return  # Already delivered

    # Ban seller
    storage.ban_user(seller_id)

    # Delete channel post if still there
    channel_msg_id = listing.get("channel_message_id")
    if channel_msg_id:
        try:
            await context.bot.delete_message(
                chat_id=os.environ.get("CHANNEL_ID", "@yourchannel"),
                message_id=channel_msg_id
            )
        except Exception:
            pass

    storage.update_listing(code, {"status": "deleted"})

    try:
        await context.bot.send_message(
            seller_id,
            "🚫 شما به دلیل عدم تحویل اطلاعات در موعد مقرر (۷۲ ساعت) از ربات مسدود شدید."
        )
    except Exception:
        pass

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"⚠️ فروشنده {seller_id} به دلیل عدم تحویل آگهی <code>{code}</code> به‌طور خودکار مسدود شد.",
                parse_mode="HTML"
            )
        except Exception:
            pass


async def seller_delivered_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    code = query.data.split("_", 2)[2].upper()
    listing = storage.get_listing(code)

    if not listing:
        await query.answer("❌ آگهی یافت نشد.", show_alert=True)
        return

    if listing.get("seller_id") != update.effective_user.id:
        await query.answer("❌ این آگهی متعلق به شما نیست.", show_alert=True)
        return

    storage.update_listing(code, {"seller_delivered": True})

    buyer_id = listing.get("buyer_id")
    if buyer_id:
        try:
            await context.bot.send_message(
                buyer_id,
                f"✅ <b>اطلاعات اکانت توسط فروشنده تحویل داده شد.</b>\n\n"
                f"📧 ایمیل: <code>{listing.get('email', '-')}</code>\n"
                f"🔑 رمز عبور: <code>{listing.get('password', '-')}</code>\n\n"
                f"در صورت هرگونه مشکل با ادمین تماس بگیرید.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send account info to buyer {buyer_id}: {e}")

    # Cancel auto-ban job
    jobs = context.job_queue.get_jobs_by_name(f"auto_ban_{code}")
    for job in jobs:
        job.schedule_removal()

    await query.edit_message_text(
        "✅ <b>تحویل اطلاعات ثبت شد.</b>\nممنون از همکاری شما.",
        parse_mode="HTML"
    )


def get_handlers():
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel_broadcast)],
    )
    return [
        CommandHandler("users", users_command),
        CommandHandler("ban", ban_command),
        CommandHandler("unban", unban_command),
        broadcast_conv,
        CallbackQueryHandler(admin_confirm_purchase, pattern=r"^admin_(confirm|reject|rejectban)_"),
        CallbackQueryHandler(seller_delivered_callback, pattern=r"^seller_delivered_"),
    ]
