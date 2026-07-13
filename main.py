import logging
import os
from dotenv import load_dotenv

load_dotenv()

from telegram.ext import Application
from keep_alive import keep_alive
from handlers import start, listing, purchase, my_ads, admin

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN is not set! Exiting.")
        raise SystemExit(1)

    # Start keep-alive Flask server (for UptimeRobot / Render free tier)
    keep_alive()

    app = Application.builder().token(token).build()

    # Register conversation handlers first (higher priority)
    app.add_handler(listing.get_handler())
    app.add_handler(purchase.get_handler())

    # Register simple handlers
    for handler in start.get_handlers():
        app.add_handler(handler)

    for handler in my_ads.get_handlers():
        app.add_handler(handler)

    for handler in admin.get_handlers():
        app.add_handler(handler)

    logger.info("Bot started. Polling...")
    app.run_polling(
        allowed_updates=["message", "callback_query", "chat_member"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
