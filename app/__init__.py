import os
import datetime
from flask import Flask, send_from_directory
import config
from app import db, auth, pacientes, backup

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config.Config)

    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(pacientes.bp)
    app.register_blueprint(backup.bp)

    with app.app_context():
        db.init_db()

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.static_folder, 'img'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )

    @app.context_processor
    def inject_global_data():
        return {
            'ano_atual': datetime.date.today().year,
            'app_nome': config.Config.APP_NAME,
            'instituicao_nome': config.Config.INSTITUICAO_NOME
        }

    @app.template_filter('formata_cpf')
    def formata_cpf_filter(valor):
        if not valor:
            return '-'
        digits = ''.join(filter(str.isdigit, str(valor)))
        if len(digits) == 11:
            return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        return valor

    @app.template_filter('formata_data')
    def formata_data_filter(valor):
        if not valor:
            return '-'
        try:
            if hasattr(valor, 'strftime'):
                return valor.strftime('%d/%m/%Y')
            s = str(valor)
            if ' ' in s:
                data_part, hora_part = s.split(' ', 1)
                ano, mes, dia = data_part.split('-')
                return f"{dia}/{mes}/{ano} {hora_part[:5]}"
            elif '-' in s:
                partes = s.split('-')
                if len(partes) == 3:
                    return f"{partes[2]}/{partes[1]}/{partes[0]}"
            return valor
        except Exception:
            return valor

    @app.template_filter('formata_telefone')
    def formata_telefone_filter(valor):
        if not valor:
            return '-'
        digits = ''.join(filter(str.isdigit, str(valor)))
        if len(digits) == 11:
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        elif len(digits) == 10:
            return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
        return valor

    return app
