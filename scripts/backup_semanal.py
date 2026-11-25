"""Script autônomo para execução do backup automático semanal do Sistema Casa Vida."""

import argparse
import datetime
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import config  # noqa: E402

LOG_MAX_BYTES = 200 * 1024
LOG_KEEP_LINES = 300


def _registrar_log_arquivo(nivel, mensagem):
    """Registra uma linha no log local de backup semanal e aplica rotação simples."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    log_path = os.path.join(config.DATA_DIR, 'backup_semanal.log')
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linha = f"[{timestamp}] [{nivel}] {mensagem}"

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(linha + '\n')

    try:
        if os.path.getsize(log_path) > LOG_MAX_BYTES:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                linhas = f.readlines()
            with open(log_path, 'w', encoding='utf-8') as f:
                f.writelines(linhas[-LOG_KEEP_LINES:])
    except OSError:
        pass

    return linha


def _emitir_log(nivel, mensagem, modo_teste=False, erro=False):
    """Grava no arquivo de log e, no modo --teste, imprime no stdout/stderr."""
    linha = _registrar_log_arquivo(nivel, mensagem)
    if modo_teste:
        stream = sys.stderr if erro else sys.stdout
        if stream is not None:
            print(linha, file=stream, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Executa o backup automático semanal do Sistema Casa Vida.'
    )
    parser.add_argument(
        '--teste',
        action='store_true',
        help='Imprime log detalhado no stdout/stderr além de gravar em arquivo.',
    )
    parser.add_argument(
        '--sem-email',
        action='store_true',
        help='Executa apenas o backup automático local (com retenção de 8 backups) sem enviar e-mail.',
    )
    args = parser.parse_args(argv)

    if args.teste:
        _emitir_log('INFO', f"Iniciando backup automático semanal em {PROJECT_ROOT}", modo_teste=True)

    try:
        from app import create_app

        app = create_app()
        with app.app_context():
            from app.backup import (
                executar_backup,
                enviar_backup_por_email,
                limpar_backups_automaticos,
            )
            from app.db import log_audit
            import config as app_config

            nome_backup, erro = executar_backup(tipo='automatico')
            if erro:
                msg = f"Falha ao criar backup automático semanal: {erro}"
                _emitir_log('ERRO', msg, modo_teste=args.teste, erro=True)
                log_audit('BACKUP', msg)
                return 1

            removidos = limpar_backups_automaticos()
            if args.teste:
                _emitir_log(
                    'INFO',
                    f"Backup local criado: {nome_backup} | Retenção automática aplicada (removidos: {removidos})",
                    modo_teste=True,
                )

            backups_dir = app.config.get('BACKUPS_DIR') or app_config.BACKUPS_DIR
            caminho_backup = os.path.join(backups_dir, nome_backup)

            if args.sem_email:
                log_audit('BACKUP', f"Backup automático semanal criado: {nome_backup}")
                _emitir_log(
                    'OK',
                    f"Backup automático semanal criado (sem envio de e-mail): {nome_backup}",
                    modo_teste=args.teste,
                )
                return 0

            if args.teste:
                _emitir_log(
                    'INFO',
                    f"Enviando backup por e-mail: {caminho_backup}",
                    modo_teste=True,
                )

            ok, info, erro_email = enviar_backup_por_email(
                caminho_backup=caminho_backup,
                nome_backup=nome_backup,
                tipo_origem='automatico',
            )
            info = info or {}

            if ok:
                nome_zip = info.get('nome_zip')
                destinatarios = ', '.join(info.get('destinatarios', []))
                msg_sucesso = (
                    f"Backup automático semanal enviado ({nome_zip}) para {destinatarios}"
                )
                log_audit('BACKUP_EMAIL', msg_sucesso)
                _emitir_log('OK', msg_sucesso, modo_teste=args.teste)
                return 0

            msg_erro_email = (
                f"Backup automático '{nome_backup}' criado, mas falha no envio por e-mail: {erro_email}"
            )
            log_audit('BACKUP_EMAIL', msg_erro_email)
            _emitir_log('ERRO', msg_erro_email, modo_teste=args.teste, erro=True)
            return 1
    except Exception as exc:
        _emitir_log(
            'ERRO',
            f"Erro inesperado ao executar backup semanal: {exc}",
            modo_teste=args.teste,
            erro=True,
        )
        return 1


if __name__ == '__main__':
    sys.exit(main())
