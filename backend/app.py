import json
import logging
import os
import threading
import webbrowser

from flask import Flask

from . import config
from .models import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


app = Flask(__name__, static_folder=str(config.FRONTEND_DIR), static_url_path='')
app.secret_key = config.SECRET_KEY
# Secure session cookie settings
# - SESSION_COOKIE_HTTPONLY prevents JavaScript access to the cookie.
# - SESSION_COOKIE_SECURE ensures the cookie is only sent over HTTPS.
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Disable the "secure" attribute on the session cookie directly.
# Previously this behavior depended on the USE_SECURE_COOKIES environment
# variable, which could be inconvenient in a plain HTTP environment.
app.config['SESSION_COOKIE_SECURE'] = False

CATEGORIES_JSON = config.CATEGORIES_JSON


def load_categories_json():
    if os.path.exists(CATEGORIES_JSON):
        try:
            with open(CATEGORIES_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_categories_json(data):
    try:
        with open(CATEGORIES_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def open_browser(port):
    webbrowser.open_new(f'http://localhost:{port}')


def run(port=5000):
    init_db()
    threading.Timer(1, lambda: open_browser(port)).start()
    app.run(host='0.0.0.0', port=port)


from . import auth  # noqa: E402,F401
from . import routes  # noqa: E402,F401
