import os
from pathlib import Path

# Load environment variables from a .env file if present
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
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///tresoperso.db')
CATEGORIES_JSON = os.environ.get('CATEGORIES_JSON', str(BASE_DIR / 'categories.json'))

__all__ = ['FRONTEND_DIR', 'SECRET_KEY', 'DATABASE_URI', 'CATEGORIES_JSON']
