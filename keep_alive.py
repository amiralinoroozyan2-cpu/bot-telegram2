import threading
import logging
import os
from flask import Flask

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
def home():
    return "I'm alive"


@app.route("/health")
def health():
    return "OK"


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def keep_alive():
    t = threading.Thread(target=run, daemon=True)
    t.start()
    logger.info("Keep-alive server started.")
