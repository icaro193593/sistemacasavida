import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _load_dotenv(dotenv_path):
    """Carrega variáveis de um arquivo .env para os.environ sem dependências externas."""
    if not os.path.exists(dotenv_path):
        return
    try:
        with open(dotenv_path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        pass

_load_dotenv(os.path.join(BASE_DIR, '.env'))

DATA_DIR = os.path.join(BASE_DIR, 'data')

def _resolve_path(raw_path, default_path):
    if not raw_path:
        return default_path
    expanded = os.path.expanduser(raw_path.strip())
    if os.path.isabs(expanded):
        return expanded
    return os.path.abspath(os.path.join(BASE_DIR, expanded))

BACKUPS_DIR = _resolve_path(os.environ.get('BACKUPS_DIR', ''), os.path.join(BASE_DIR, 'backups'))
DATABASE_PATH = _resolve_path(os.environ.get('DATABASE_PATH', ''), os.path.join(DATA_DIR, 'casa_vida.db'))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

SECRET_KEY_FILE = os.path.join(DATA_DIR, '.secret_key')
_env_secret_key = os.environ.get('SECRET_KEY', '').strip()
if _env_secret_key:
    SECRET_KEY = _env_secret_key
elif os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, 'r', encoding='utf-8') as f:
        SECRET_KEY = f.read().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    try:
        with open(SECRET_KEY_FILE, 'w', encoding='utf-8') as f:
            f.write(SECRET_KEY)
    except IOError:
        pass

class Config:
    SECRET_KEY = SECRET_KEY
    DATABASE = DATABASE_PATH
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    APP_NAME = 'Sistema Casa Vida'
    INSTITUICAO_NOME = 'Instituto Casa Vida'
    CIDADE_PADRAO = 'Juiz de Fora'
    UF_PADRAO = 'MG'

    # Sincronização com Google Sheets (somente novos registros a partir da data de corte)
    GOOGLE_SHEETS_CSV_URL = os.environ.get('GOOGLE_SHEETS_CSV_URL', '').strip()
    GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID', '').strip()
    GOOGLE_SHEETS_GID = os.environ.get('GOOGLE_SHEETS_GID', '0').strip() or '0'
    GOOGLE_SHEETS_TIMEOUT = int(os.environ.get('GOOGLE_SHEETS_TIMEOUT', '15') or 15)
    GOOGLE_SHEETS_MIN_DATE = os.environ.get('GOOGLE_SHEETS_MIN_DATE', '2026-11-23').strip()
