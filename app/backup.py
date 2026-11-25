import datetime
import io
import os
import smtplib
import sqlite3
import ssl
import tempfile
import zipfile
from email.message import EmailMessage
from urllib.parse import quote

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for, send_file
)

import config
from app.db import close_db, get_db, init_db, log_audit

bp = Blueprint('backup', __name__, url_prefix='/backup')

_MAX_ZIP_EXTRACT_BYTES = 100 * 1024 * 1024


def _get_database_path():
    try:
        return current_app.config.get('DATABASE') or config.DATABASE_PATH
    except RuntimeError:
        return config.DATABASE_PATH


def _get_backups_dir():
    try:
        return current_app.config.get('BACKUPS_DIR') or config.BACKUPS_DIR
    except RuntimeError:
        return config.BACKUPS_DIR


def _get_config_val(chave, default=None):
    try:
        if chave in current_app.config and current_app.config[chave] is not None:
            return current_app.config[chave]
    except RuntimeError:
        pass
    return getattr(config.Config, chave, default)


def _copiar_banco_sqlite(origem, destino):
    src = None
    dst = None
    try:
        src = sqlite3.connect(origem)
        dst = sqlite3.connect(destino)
        src.backup(dst)
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()


def obter_tamanho_formatado(num_bytes):
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.2f} MB"


def contar_registros_backup(caminho_arquivo):
    """Retorna o total de registros da tabela pacientes no arquivo SQLite ou None se inválido."""
    if not caminho_arquivo or not os.path.isfile(caminho_arquivo):
        return None
    conn = None
    try:
        caminho_uri = quote(os.path.abspath(caminho_arquivo).replace(os.sep, '/'), safe='/:')
        conn = sqlite3.connect(f"file:{caminho_uri}?mode=ro", uri=True)
        tabela = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pacientes'"
        ).fetchone()
        if not tabela:
            return None
        row = conn.execute("SELECT COUNT(*) FROM pacientes").fetchone()
        return int(row[0]) if row is not None else None
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()


def listar_backups():
    arquivos = []
    backups_dir = _get_backups_dir()
    if os.path.exists(backups_dir):
        for f in os.listdir(backups_dir):
            if f.endswith('.db') or f.endswith('.sqlite'):
                caminho = os.path.join(backups_dir, f)
                if not os.path.isfile(caminho):
                    continue
                info = os.stat(caminho)
                arquivos.append({
                    'nome': f,
                    'tamanho': obter_tamanho_formatado(info.st_size),
                    'tamanho_bytes': info.st_size,
                    'data_modificacao': datetime.datetime.fromtimestamp(info.st_mtime).strftime('%d/%m/%Y %H:%M:%S'),
                    'timestamp': info.st_mtime,
                    'registros': contar_registros_backup(caminho),
                })
    arquivos.sort(key=lambda x: x['timestamp'], reverse=True)
    return arquivos


def limpar_backups_automaticos(max_manter=None):
    if max_manter is None:
        max_manter = int(_get_config_val('BACKUP_AUTO_RETENCAO', 8) or 8)
    if max_manter <= 0:
        return []

    backups_dir = _get_backups_dir()
    if not os.path.exists(backups_dir):
        return []

    candidatos = []
    for nome in os.listdir(backups_dir):
        if nome.startswith('casa_vida_backup_auto_') and nome.endswith('.db'):
            caminho = os.path.join(backups_dir, nome)
            if os.path.isfile(caminho):
                candidatos.append((os.stat(caminho).st_mtime, nome, caminho))

    candidatos.sort(key=lambda item: (item[0], item[1]), reverse=True)

    removidos = []
    for _, nome, caminho in candidatos[max_manter:]:
        os.remove(caminho)
        removidos.append(nome)
    return removidos


def executar_backup(tipo='manual'):
    db_path = _get_database_path()
    if not os.path.exists(db_path):
        return None, "Banco de dados principal não encontrado."

    backups_dir = _get_backups_dir()
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    prefixo = 'casa_vida_backup_auto_' if tipo == 'automatico' else 'casa_vida_backup_'

    nome_backup = f"{prefixo}{timestamp}.db"
    caminho_backup = os.path.join(backups_dir, nome_backup)
    contador = 1
    while os.path.exists(caminho_backup):
        nome_backup = f"{prefixo}{timestamp}_{contador}.db"
        caminho_backup = os.path.join(backups_dir, nome_backup)
        contador += 1

    try:
        _copiar_banco_sqlite(db_path, caminho_backup)
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

        if tipo == 'automatico':
            limpar_backups_automaticos()

        return nome_backup, None
    except Exception as e:
        if os.path.exists(caminho_backup):
            try:
                os.remove(caminho_backup)
            except OSError:
                pass
        return None, str(e)


def compactar_backup_zip(caminho_db):
    nome_base = os.path.basename(caminho_db)
    raiz, ext = os.path.splitext(nome_base)
    if ext.lower() in ('.db', '.sqlite'):
        nome_zip = f"{raiz}.zip"
    else:
        nome_zip = f"{nome_base}.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(caminho_db, arcname=nome_base)
    return nome_zip, buffer.getvalue()


def obter_destinatarios_backup(raw_destinos=None):
    if raw_destinos is None:
        raw_destinos = _get_config_val('BACKUP_EMAIL_DESTINO', '') or ''
    if isinstance(raw_destinos, (list, tuple)):
        return [str(parte).strip() for parte in raw_destinos if str(parte).strip()]
    texto = str(raw_destinos).replace(';', ',')
    return [parte.strip() for parte in texto.split(',') if parte.strip()]


def _autenticar_smtp(server, smtp_user, smtp_password):
    """Autentica no servidor SMTP, convertendo desconexão abrupta no login em erro de autenticação."""
    try:
        server.login(smtp_user, smtp_password)
    except smtplib.SMTPServerDisconnected as exc:
        raise smtplib.SMTPAuthenticationError(
            535,
            b'Servidor SMTP encerrou a conexao durante a autenticacao.',
        ) from exc


def enviar_backup_por_email(caminho_backup=None, nome_backup=None, tipo_origem='manual'):
    smtp_host = str(_get_config_val('SMTP_HOST', 'smtp.gmail.com') or 'smtp.gmail.com').strip()
    smtp_port = int(_get_config_val('SMTP_PORT', 465) or 465)
    smtp_use_ssl_raw = _get_config_val('SMTP_USE_SSL', True)
    if isinstance(smtp_use_ssl_raw, str):
        smtp_use_ssl = smtp_use_ssl_raw.strip().lower() in ('1', 'true', 'sim', 'yes', 'on')
    else:
        smtp_use_ssl = bool(smtp_use_ssl_raw)
    smtp_user = str(_get_config_val('SMTP_USER', '') or '').strip()
    smtp_password = str(_get_config_val('SMTP_PASSWORD', '') or '').strip()
    smtp_timeout = int(_get_config_val('SMTP_TIMEOUT', 30) or 30)
    destinatarios = obter_destinatarios_backup(_get_config_val('BACKUP_EMAIL_DESTINO', ''))

    if not destinatarios:
        return False, {}, "Nenhum destinatário configurado em BACKUP_EMAIL_DESTINO."
    if not smtp_user or not smtp_password:
        return False, {}, "Credenciais SMTP (SMTP_USER e SMTP_PASSWORD) não configuradas."
    if not smtp_host:
        return False, {}, "Servidor SMTP (SMTP_HOST) não configurado."

    if caminho_backup is None:
        nome_gerado, erro = executar_backup(tipo=tipo_origem)
        if erro:
            return False, {}, erro
        caminho_backup = os.path.join(_get_backups_dir(), nome_gerado)
        if nome_backup is None:
            nome_backup = nome_gerado
    else:
        if not os.path.exists(caminho_backup):
            return False, {}, "Arquivo de backup não encontrado para envio."
        if nome_backup is None:
            nome_backup = os.path.basename(caminho_backup)

    info_dict = {
        'nome_backup': nome_backup,
        'nome_zip': '',
        'tamanho_db': 0,
        'tamanho_zip': 0,
        'destinatarios': destinatarios,
    }

    try:
        nome_zip, dados_zip_bytes = compactar_backup_zip(caminho_backup)
        tamanho_db = os.path.getsize(caminho_backup)
        tamanho_zip = len(dados_zip_bytes)
        info_dict.update({
            'nome_zip': nome_zip,
            'tamanho_db': tamanho_db,
            'tamanho_zip': tamanho_zip,
        })

        rotulo_tipo = "Automático Semanal" if tipo_origem == 'automatico' else "Manual"
        data_hora_br = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

        msg = EmailMessage()
        msg['From'] = f"Sistema Casa Vida <{smtp_user}>"
        msg['To'] = ', '.join(destinatarios)
        msg['Subject'] = f"[Sistema Casa Vida] Backup {rotulo_tipo} — {data_hora_br}"
        msg.set_content(
            f"Backup do Sistema Casa Vida realizado com sucesso.\n\n"
            f"Tipo: {rotulo_tipo}\n"
            f"Data/Hora: {data_hora_br}\n"
            f"Arquivo do banco (.db): {nome_backup} ({obter_tamanho_formatado(tamanho_db)})\n"
            f"Arquivo compactado (.zip): {nome_zip} ({obter_tamanho_formatado(tamanho_zip)})\n\n"
            f"Nota: Este arquivo .zip pode ser restaurado diretamente na tela de Backups do sistema.\n"
        )
        msg.add_attachment(
            dados_zip_bytes,
            maintype='application',
            subtype='zip',
            filename=nome_zip,
        )

        context = ssl.create_default_context()
        if smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout, context=context) as server:
                _autenticar_smtp(server, smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                _autenticar_smtp(server, smtp_user, smtp_password)
                server.send_message(msg)

        return True, info_dict, None
    except smtplib.SMTPAuthenticationError as e:
        detalhe_auth = (
            "O servidor SMTP encerrou a conexão durante a autenticação "
            "(comportamento típico quando o Gmail recusa a senha comum). "
            if isinstance(e.__cause__, smtplib.SMTPServerDisconnected)
            else "Falha na autenticação SMTP (usuário ou senha recusados). "
        )
        return (
            False,
            info_dict,
            f"{detalhe_auth}"
            "No Gmail, é obrigatório ativar a Verificação em 2 etapas e usar uma "
            "Senha de App de 16 letras em SMTP_PASSWORD no arquivo .env."
        )
    except (smtplib.SMTPException, TimeoutError, OSError) as e:
        return False, info_dict, str(e) or type(e).__name__
    except Exception as e:
        return False, info_dict, f"Erro inesperado: {e}"


def validar_arquivo_sqlite(caminho_arquivo):
    if not caminho_arquivo or not os.path.isfile(caminho_arquivo):
        raise ValueError("Arquivo de backup não encontrado.")

    if os.path.getsize(caminho_arquivo) < 100:
        raise ValueError("Arquivo inválido: tamanho insuficiente para ser um banco SQLite.")

    with open(caminho_arquivo, 'rb') as f:
        cabecalho = f.read(16)
    if cabecalho != b'SQLite format 3\x00':
        raise ValueError("Arquivo inválido: não possui cabeçalho SQLite válido.")

    conn = None
    try:
        conn = sqlite3.connect(caminho_arquivo)
        check = conn.execute("PRAGMA quick_check").fetchone()
        if not check or str(check[0]).lower() != 'ok':
            raise ValueError("O arquivo SQLite está corrompido (falha na verificação de integridade).")

        tabela = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pacientes'"
        ).fetchone()
        if not tabela:
            raise ValueError("O banco informado não pertence ao Sistema Casa Vida (tabela 'pacientes' ausente).")
    except sqlite3.DatabaseError as e:
        raise ValueError(f"Arquivo SQLite inválido ou corrompido: {e}")
    finally:
        if conn is not None:
            conn.close()


def extrair_banco_de_upload(file_storage, temp_dir):
    if file_storage is None or not getattr(file_storage, 'filename', ''):
        raise ValueError("Nenhum arquivo de backup foi enviado.")

    nome_original = os.path.basename(file_storage.filename.strip())
    if not nome_original:
        raise ValueError("Nenhum arquivo de backup foi enviado.")

    _, ext = os.path.splitext(nome_original)
    ext = ext.lower()
    if ext not in ('.db', '.sqlite', '.zip'):
        raise ValueError("Formato não suportado. Envie um arquivo .db, .sqlite ou .zip.")

    caminho_extraido = os.path.join(temp_dir, 'upload_restore.db')

    if ext in ('.db', '.sqlite'):
        file_storage.save(caminho_extraido)
        validar_arquivo_sqlite(caminho_extraido)
        return caminho_extraido, nome_original

    caminho_zip = os.path.join(temp_dir, 'upload_restore.zip')
    file_storage.save(caminho_zip)

    membro_db = None
    try:
        with zipfile.ZipFile(caminho_zip, 'r') as zf:
            for membro in zf.infolist():
                if membro.is_dir():
                    continue
                nome_norm = membro.filename.replace('\\', '/')
                if nome_norm.startswith('__MACOSX/') or '/__MACOSX/' in nome_norm:
                    continue
                if (
                    nome_norm.startswith('/')
                    or (len(nome_norm) >= 2 and nome_norm[1] == ':')
                    or '..' in nome_norm.split('/')
                ):
                    raise ValueError("Arquivo .zip contém caminho inválido ou inseguro.")

                _, m_ext = os.path.splitext(nome_norm)
                if m_ext.lower() in ('.db', '.sqlite'):
                    if membro.file_size > _MAX_ZIP_EXTRACT_BYTES:
                        raise ValueError("O arquivo dentro do .zip excede o limite máximo de 100 MB.")
                    membro_db = membro
                    break

            if membro_db is None:
                raise ValueError("Nenhum arquivo .db ou .sqlite encontrado dentro do .zip.")

            total_lido = 0
            with zf.open(membro_db, 'r') as src, open(caminho_extraido, 'wb') as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    total_lido += len(chunk)
                    if total_lido > _MAX_ZIP_EXTRACT_BYTES:
                        raise ValueError("O arquivo extraído do .zip excede o limite máximo de 100 MB.")
                    dst.write(chunk)
    except zipfile.BadZipFile:
        raise ValueError("O arquivo .zip enviado está corrompido ou não é um ZIP válido.")

    validar_arquivo_sqlite(caminho_extraido)
    nome_interno = os.path.basename(membro_db.filename.replace('\\', '/'))
    return caminho_extraido, f"{nome_original} ({nome_interno})"


def restaurar_banco_de_arquivo(caminho_origem):
    validar_arquivo_sqlite(caminho_origem)
    db_path = _get_database_path()
    if os.path.exists(db_path):
        _, erro_pre = executar_backup(tipo='pre_restauracao')
        if erro_pre:
            raise RuntimeError(f"Falha ao gerar backup pré-restauração: {erro_pre}")
    close_db()
    _copiar_banco_sqlite(caminho_origem, db_path)
    init_db()


@bp.route('/')
def index():
    db_path = _get_database_path()
    backups = listar_backups()
    tamanho_atual = "0 KB"
    if os.path.exists(db_path):
        tamanho_atual = obter_tamanho_formatado(os.path.getsize(db_path))

    destinatarios = obter_destinatarios_backup()
    smtp_configurado = bool(
        _get_config_val('SMTP_USER')
        and _get_config_val('SMTP_PASSWORD')
        and destinatarios
    )
    retencao_auto = int(_get_config_val('BACKUP_AUTO_RETENCAO', 8) or 8)

    return render_template(
        'backups.html',
        backups=backups,
        tamanho_atual=tamanho_atual,
        caminho_banco=db_path,
        email_destino=', '.join(destinatarios),
        smtp_configurado=smtp_configurado,
        retencao_auto=retencao_auto,
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


@bp.route('/enviar-email', methods=('POST',))
def enviar_email():
    sucesso, info, erro = enviar_backup_por_email(tipo_origem='email_manual')
    if sucesso:
        destinos = ', '.join(info.get('destinatarios', []))
        log_audit(
            'BACKUP_EMAIL',
            f"Backup {info.get('nome_zip')} enviado por e-mail para {destinos}"
        )
        flash(f'Backup "{info.get("nome_zip")}" enviado por e-mail com sucesso!', 'success')
    else:
        msg_erro = str(erro or '').strip()
        prefixo = 'Erro ao enviar backup por e-mail:'
        if msg_erro.startswith(prefixo):
            msg_erro = msg_erro[len(prefixo):].strip()
        log_audit('BACKUP_EMAIL', f"Falha ao enviar backup por e-mail: {msg_erro}")
        flash(f'Erro ao enviar backup por e-mail: {msg_erro}', 'danger')
    return redirect(url_for('backup.index'))


@bp.route('/download/<nome_arquivo>')
def download(nome_arquivo):
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(_get_backups_dir(), nome_seguro)
    if os.path.exists(caminho):
        log_audit('DOWNLOAD_BACKUP', f"Download do backup {nome_seguro}")
        return send_file(caminho, as_attachment=True, download_name=nome_seguro)
    flash('Arquivo de backup não encontrado.', 'danger')
    return redirect(url_for('backup.index'))


@bp.route('/restaurar/<nome_arquivo>', methods=('POST',))
def restaurar(nome_arquivo):
    nome_seguro = os.path.basename(nome_arquivo)
    caminho = os.path.join(_get_backups_dir(), nome_seguro)

    if not os.path.exists(caminho):
        flash('Arquivo de backup não encontrado.', 'danger')
        return redirect(url_for('backup.index'))

    try:
        restaurar_banco_de_arquivo(caminho)
        log_audit('RESTAURACAO', f"Banco restaurado a partir de {nome_seguro}")
        flash(f'Banco de dados restaurado com sucesso para a versão de "{nome_seguro}"!', 'success')
    except Exception as e:
        flash(f'Erro ao restaurar banco: {e}', 'danger')

    return redirect(url_for('backup.index'))


@bp.route('/restaurar-arquivo', methods=('POST',))
def restaurar_arquivo():
    arquivo = request.files.get('arquivo_backup')
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho_extraido, origem_label = extrair_banco_de_upload(arquivo, temp_dir)
            restaurar_banco_de_arquivo(caminho_extraido)
        log_audit('RESTAURACAO', f"Banco restaurado via upload: {origem_label}")
        flash(f'Banco de dados restaurado com sucesso a partir de "{origem_label}"!', 'success')
    except Exception as e:
        flash(f'Erro ao restaurar banco: {e}', 'danger')

    return redirect(url_for('backup.index'))
