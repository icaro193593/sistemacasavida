import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

DATABASE_PATH = os.path.join(DATA_DIR, 'casa_vida.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

SECRET_KEY_FILE = os.path.join(DATA_DIR, '.secret_key')
if os.path.exists(SECRET_KEY_FILE):
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
