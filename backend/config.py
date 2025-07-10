import os
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_PATH = ROOT_DIR / '.env'

def load_dotenv(path=ENV_PATH):
    if path.exists():
        with path.open('r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                os.environ.setdefault(key, val)

load_dotenv()

FRONTEND_DIR = ROOT_DIR / 'frontend'

_SECRET_KEY = os.environ.get('SECRET_KEY')
if not _SECRET_KEY:
    _SECRET_KEY = os.urandom(32).hex()
    logging.warning('SECRET_KEY environment variable not set; using a generated key')

CATEGORIES_JSON = os.environ.get('CATEGORIES_JSON', str(BASE_DIR / 'categories.json'))
SECRET_KEY = _SECRET_KEY

# *** ADAPTATION CHEMIN BASE ***
if getattr(sys, 'frozen', False):
    # Exécuté via PyInstaller
    app_dir = Path(sys.executable).parent
else:
    app_dir = ROOT_DIR

DEFAULT_DB = app_dir / 'tresoperso.db'
DATABASE_URI = os.environ.get('DATABASE_URI', f'sqlite:///{DEFAULT_DB}')

print("CHEMIN BASE DE DONNÉES UTILISÉ :", DEFAULT_DB)
print("DATABASE_URI utilisée :", DATABASE_URI)

__all__ = ['FRONTEND_DIR', 'SECRET_KEY', 'DATABASE_URI', 'CATEGORIES_JSON']
