import sqlite3
import os
import datetime
from flask import g, current_app
import config

def get_db():
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE') or config.DATABASE_PATH
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON;')
        g.db.execute('PRAGMA journal_mode = WAL;')
        g.db.execute('PRAGMA synchronous = NORMAL;')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(db_path=None):
    target_path = db_path
    if not target_path:
        try:
            target_path = current_app.config.get('DATABASE')
        except RuntimeError:
            pass
    target_path = target_path or config.DATABASE_PATH
    db = sqlite3.connect(target_path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON;')
    
    with open(config.SCHEMA_PATH, 'r', encoding='utf-8') as f:
        db.executescript(f.read())

    db.close()

def log_audit(acao, detalhes="", *args, **kwargs):
    try:
        db = get_db()
        agora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute("""
            INSERT INTO logs_auditoria (acao, detalhes, data_hora)
            VALUES (?, ?, ?)
        """, (acao, detalhes, agora))
        db.commit()
    except Exception as e:
        print(f"[AVISO] Falha ao registrar log de auditoria: {e}")

def init_app(app):
    app.teardown_appcontext(close_db)
