import os
import json
import threading
import webbrowser

from flask import Flask

from .models import init_db, SessionLocal
from . import config

app = Flask(__name__, static_folder=str(config.FRONTEND_DIR), static_url_path='')
app.secret_key = config.SECRET_KEY
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

# import modules that register routes
from . import auth  # noqa: F401
from . import routes  # noqa: F401


def open_browser():
    webbrowser.open_new('http://localhost:5000')


def run():
    init_db()
    threading.Timer(1, open_browser).start()
    app.run(host='0.0.0.0')
