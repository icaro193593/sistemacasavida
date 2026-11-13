import sqlite3
import os
from flask import g, current_app
from werkzeug.security import generate_password_hash
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
        
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM usuarios")
    row = cur.fetchone()
    
    if row['total'] == 0:
        senha_hash = generate_password_hash("admin123")
        cur.execute("""
            INSERT INTO usuarios (username, senha_hash, nome_completo, perfil, ativo)
            VALUES (?, ?, ?, ?, ?)
        """, ('admin', senha_hash, 'Administrador Casa Vida', 'admin', 1))
        db.commit()
    db.close()

def log_audit(acao, detalhes="", usuario_id=None, usuario_nome=None):
    try:
        db = get_db()
        db.execute("""
            INSERT INTO logs_auditoria (usuario_id, usuario_nome, acao, detalhes)
            VALUES (?, ?, ?, ?)
        """, (usuario_id, usuario_nome, acao, detalhes))
        db.commit()
    except Exception as e:
        print(f"[AVISO] Falha ao registrar log de auditoria: {e}")

def init_app(app):
    app.teardown_appcontext(close_db)
