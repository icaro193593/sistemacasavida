import os
import shutil
import datetime
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, send_file
)
import config
from app.auth import login_required, admin_required
from app.db import get_db, log_audit

bp = Blueprint('backup', __name__, url_prefix='/backup')

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
    if not os.path.exists(config.DATABASE_PATH):
        return None, "Banco de dados principal não encontrado."

    os.makedirs(config.BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_backup = f"casa_vida_backup_{timestamp}.db"
    caminho_backup = os.path.join(config.BACKUPS_DIR, nome_backup)

    try:
        shutil.copy2(config.DATABASE_PATH, caminho_backup)
        tamanho = os.path.getsize(caminho_backup)

        try:
            db = get_db()
            db.execute("""
                INSERT INTO backups_registro (nome_arquivo, tamanho_bytes, tipo, usuario_id)
                VALUES (?, ?, ?, ?)
            """, (nome_backup, tamanho, tipo, g.user['id'] if g.user else None))
            db.commit()
        except Exception:
            pass

        return nome_backup, None
    except Exception as e:
        return None, str(e)

@bp.route('/')
@login_required
def index():
    backups = listar_backups()
    tamanho_atual = "0 KB"
    if os.path.exists(config.DATABASE_PATH):
        tamanho_atual = obter_tamanho_formatado(os.path.getsize(config.DATABASE_PATH))

    return render_template(
        'backups.html',
        backups=backups,
        tamanho_atual=tamanho_atual,
        caminho_banco=config.DATABASE_PATH
    )

@bp.route('/criar', methods=('POST',))
@login_required
def criar():
    nome, erro = executar_backup(tipo='manual')
    if erro:
        flash(f'Erro ao gerar backup: {erro}', 'danger')
    else:
        log_audit('BACKUP', f"Backup criado: {nome}", g.user['id'], g.user['nome_completo'])
        flash(f'Backup "{nome}" gerado com sucesso!', 'success')
    return redirect(url_for('backup.index'))

@bp.route('/download/<nome_arquivo>')
@login_required
def download(nome_arquivo):
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(config.BACKUPS_DIR, nome_seguro)
    if os.path.exists(caminho):
        log_audit('DOWNLOAD_BACKUP', f"Download do backup {nome_seguro}", g.user['id'], g.user['nome_completo'])
        return send_file(caminho, as_attachment=True, download_name=nome_seguro)
    flash('Arquivo de backup não encontrado.', 'danger')
    return redirect(url_for('backup.index'))

@bp.route('/restaurar/<nome_arquivo>', methods=('POST',))
@admin_required
def restaurar(nome_arquivo):
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(config.BACKUPS_DIR, nome_seguro)

    if not os.path.exists(caminho):
        flash('Arquivo de backup não encontrado.', 'danger')
        return redirect(url_for('backup.index'))

    try:
        executar_backup(tipo='pre_restauracao')
        shutil.copy2(caminho, config.DATABASE_PATH)
        log_audit('RESTAURACAO', f"Banco restaurado a partir de {nome_seguro}", g.user['id'], g.user['nome_completo'])
        flash(f'Banco de dados restaurado com sucesso para a versão de "{nome_seguro}"!', 'success')
    except Exception as e:
        flash(f'Erro ao restaurar banco: {e}', 'danger')

    return redirect(url_for('backup.index'))
