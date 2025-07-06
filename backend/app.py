import os
import json
import threading
import webbrowser
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

from flask import Flask

from . import config
from .models import init_db

app = Flask(__name__, static_folder=str(config.FRONTEND_DIR), static_url_path='')
app.secret_key = config.SECRET_KEY
# Secure session cookie settings
# - SESSION_COOKIE_HTTPONLY prevents JavaScript access to the cookie.
# - SESSION_COOKIE_SECURE ensures the cookie is only sent over HTTPS.
app.config['SESSION_COOKIE_HTTPONLY'] = True
use_secure_cookies = os.environ.get('USE_SECURE_COOKIES', '1')
app.config['SESSION_COOKIE_SECURE'] = str(use_secure_cookies).lower() not in (
    '0', 'false', 'no'
)

CATEGORIES_JSON = config.CATEGORIES_JSON

from . import auth  # noqa: F401


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



def open_browser():
    webbrowser.open_new('http://localhost:5000')


def run():
    init_db()
    threading.Timer(1, open_browser).start()
    app.run(host='0.0.0.0')


from . import routes  # noqa: F401
