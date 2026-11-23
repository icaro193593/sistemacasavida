import os
import shutil
import datetime
from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for, send_file
)
import config
from app.db import get_db, log_audit

bp = Blueprint('backup', __name__, url_prefix='/backup')

def _get_database_path():
    try:
        return current_app.config.get('DATABASE') or config.DATABASE_PATH
    except RuntimeError:
        return config.DATABASE_PATH

def obter_tamanho_formatado(num_bytes):
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.2f} MB"

def listar_backups():
    arquivos = []
    if os.path.exists(config.BACKUPS_DIR):
        for f in os.listdir(config.BACKUPS_DIR):
            if f.endswith('.db') or f.endswith('.sqlite'):
                caminho = os.path.join(config.BACKUPS_DIR, f)
                info = os.stat(caminho)
                arquivos.append({
                    'nome': f,
                    'tamanho': obter_tamanho_formatado(info.st_size),
                    'tamanho_bytes': info.st_size,
                    'data_modificacao': datetime.datetime.fromtimestamp(info.st_mtime).strftime('%d/%m/%Y %H:%M:%S'),
                    'timestamp': info.st_mtime
                })
    arquivos.sort(key=lambda x: x['timestamp'], reverse=True)
    return arquivos

def executar_backup(tipo='manual'):
    db_path = _get_database_path()
    if not os.path.exists(db_path):
        return None, "Banco de dados principal não encontrado."

    os.makedirs(config.BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_backup = f"casa_vida_backup_{timestamp}.db"
    caminho_backup = os.path.join(config.BACKUPS_DIR, nome_backup)

    try:
        shutil.copy2(db_path, caminho_backup)
        tamanho = os.path.getsize(caminho_backup)

        try:
            db = get_db()
            db.execute("""
                INSERT INTO backups_registro (nome_arquivo, tamanho_bytes, tipo)
                VALUES (?, ?, ?)
            """, (nome_backup, tamanho, tipo))
            db.commit()
        except Exception:
            pass

        return nome_backup, None
    except Exception as e:
        return None, str(e)

@bp.route('/')
def index():
    db_path = _get_database_path()
    backups = listar_backups()
    tamanho_atual = "0 KB"
    if os.path.exists(db_path):
        tamanho_atual = obter_tamanho_formatado(os.path.getsize(db_path))

    return render_template(
        'backups.html',
        backups=backups,
        tamanho_atual=tamanho_atual,
        caminho_banco=db_path
    )

@bp.route('/criar', methods=('POST',))
def criar():
    nome, erro = executar_backup(tipo='manual')
    if erro:
        flash(f'Erro ao gerar backup: {erro}', 'danger')
    else:
        log_audit('BACKUP', f"Backup criado: {nome}")
        flash(f'Backup "{nome}" gerado com sucesso!', 'success')
    return redirect(url_for('backup.index'))

@bp.route('/download/<nome_arquivo>')
def download(nome_arquivo):
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(config.BACKUPS_DIR, nome_seguro)
    if os.path.exists(caminho):
        log_audit('DOWNLOAD_BACKUP', f"Download do backup {nome_seguro}")
        return send_file(caminho, as_attachment=True, download_name=nome_seguro)
    flash('Arquivo de backup não encontrado.', 'danger')
    return redirect(url_for('backup.index'))

@bp.route('/restaurar/<nome_arquivo>', methods=('POST',))
def restaurar(nome_arquivo):
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(config.BACKUPS_DIR, nome_seguro)

    if not os.path.exists(caminho):
        flash('Arquivo de backup não encontrado.', 'danger')
        return redirect(url_for('backup.index'))

    try:
        db_path = _get_database_path()
        executar_backup(tipo='pre_restauracao')
        shutil.copy2(caminho, db_path)
        log_audit('RESTAURACAO', f"Banco restaurado a partir de {nome_seguro}")
        flash(f'Banco de dados restaurado com sucesso para a versão de "{nome_seguro}"!', 'success')
    except Exception as e:
        flash(f'Erro ao restaurar banco: {e}', 'danger')

    return redirect(url_for('backup.index'))
