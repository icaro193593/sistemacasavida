import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import get_db, log_audit

bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        if g.user['perfil'] != 'admin':
            flash('Acesso restrito a administradores do sistema.', 'danger')
            return redirect(url_for('pacientes.index'))
        return view(**kwargs)
    return wrapped_view

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        user = db.execute(
            'SELECT id, username, nome_completo, perfil, ativo FROM usuarios WHERE id = ?',
            (user_id,)
        ).fetchone()
        if user and user['ativo']:
            g.user = user
        else:
            session.clear()
            g.user = None

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('pacientes.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        senha = request.form.get('senha', '')
        erro = None

        if not username or not senha:
            erro = 'Informe o usuário e a senha.'
        else:
            db = get_db()
            user = db.execute(
                'SELECT * FROM usuarios WHERE username = ? COLLATE NOCASE',
                (username,)
            ).fetchone()

            if user is None:
                erro = 'Usuário ou senha incorretos.'
            elif not user['ativo']:
                erro = 'Este usuário foi desativado. Contate o administrador.'
            elif not check_password_hash(user['senha_hash'], senha):
                erro = 'Usuário ou senha incorretos.'
            else:
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['nome'] = user['nome_completo']
                session['perfil'] = user['perfil']

                db.execute(
                    'UPDATE usuarios SET ultimo_login = CURRENT_TIMESTAMP WHERE id = ?',
                    (user['id'],)
                )
                db.commit()

                log_audit('LOGIN', f"Usuário {user['username']} autenticado", user['id'], user['nome_completo'])

                flash(f"Bem-vindo(a), {user['nome_completo']}!", 'success')
                next_url = request.args.get('next')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect(url_for('pacientes.index'))

        if erro:
            flash(erro, 'danger')

    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    if g.user:
        log_audit('LOGOUT', f"Usuário {g.user['username']} encerrou sessão", g.user['id'], g.user['nome_completo'])
    session.clear()
    flash('Você saiu do sistema com segurança.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/perfil', methods=('GET', 'POST'))
@login_required
def perfil():
    db = get_db()
    if request.method == 'POST':
        nome = request.form.get('nome_completo', '').strip()
        senha_atual = request.form.get('senha_atual', '')
        nova_senha = request.form.get('nova_senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')

        user_db = db.execute('SELECT * FROM usuarios WHERE id = ?', (g.user['id'],)).fetchone()

        if not nome:
            flash('O nome não pode ficar em branco.', 'danger')
        elif nova_senha:
            if not check_password_hash(user_db['senha_hash'], senha_atual):
                flash('A senha atual informada está incorreta.', 'danger')
            elif len(nova_senha) < 6:
                flash('A nova senha deve ter no mínimo 6 caracteres.', 'danger')
            elif nova_senha != confirmar_senha:
                flash('A confirmação da nova senha não confere.', 'danger')
            else:
                db.execute(
                    'UPDATE usuarios SET nome_completo = ?, senha_hash = ? WHERE id = ?',
                    (nome, generate_password_hash(nova_senha), g.user['id'])
                )
                db.commit()
                log_audit('ALTERACAO_SENHA', f"Usuário {g.user['username']} alterou sua senha", g.user['id'], nome)
                flash('Senha e dados atualizados com sucesso!', 'success')
                return redirect(url_for('pacientes.index'))
        else:
            db.execute('UPDATE usuarios SET nome_completo = ? WHERE id = ?', (nome, g.user['id']))
            db.commit()
            flash('Dados atualizados com sucesso!', 'success')
            return redirect(url_for('pacientes.index'))

    return render_template('auth/perfil.html')

@bp.route('/usuarios')
@admin_required
def usuarios():
    db = get_db()
    usuarios_list = db.execute(
        'SELECT id, username, nome_completo, perfil, ativo, criado_em, ultimo_login FROM usuarios ORDER BY nome_completo ASC'
    ).fetchall()
    return render_template('auth/usuarios.html', usuarios=usuarios_list)

@bp.route('/usuarios/novo', methods=('POST',))
@admin_required
def criar_usuario():
    username = request.form.get('username', '').strip().lower()
    nome = request.form.get('nome_completo', '').strip()
    senha = request.form.get('senha', '')
    perfil = request.form.get('perfil', 'atendente')

    if not username or not nome or not senha:
        flash('Preencha todos os campos obrigatórios para o usuário.', 'danger')
        return redirect(url_for('auth.usuarios'))

    if len(senha) < 6:
        flash('A senha deve possuir pelo menos 6 caracteres.', 'danger')
        return redirect(url_for('auth.usuarios'))

    db = get_db()
    try:
        db.execute("""
            INSERT INTO usuarios (username, nome_completo, senha_hash, perfil, ativo)
            VALUES (?, ?, ?, ?, 1)
        """, (username, nome, generate_password_hash(senha), perfil))
        db.commit()
        log_audit('CRIAR_USUARIO', f"Usuário {username} criado ({perfil})", g.user['id'], g.user['nome_completo'])
        flash(f'Usuário "{username}" cadastrado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao cadastrar usuário: Nome de usuário já em uso ou inválido.', 'danger')

    return redirect(url_for('auth.usuarios'))

@bp.route('/usuarios/<int:id>/status', methods=('POST',))
@admin_required
def alternar_status_usuario(id):
    if id == g.user['id']:
        flash('Você não pode desativar seu próprio usuário.', 'danger')
        return redirect(url_for('auth.usuarios'))

    db = get_db()
    usuario = db.execute('SELECT id, username, ativo FROM usuarios WHERE id = ?', (id,)).fetchone()
    if usuario:
        novo_status = 0 if usuario['ativo'] else 1
        db.execute('UPDATE usuarios SET ativo = ? WHERE id = ?', (novo_status, id))
        db.commit()
        status_txt = "ativado" if novo_status else "desativado"
        log_audit('ALTERAR_STATUS_USUARIO', f"Usuário {usuario['username']} {status_txt}", g.user['id'], g.user['nome_completo'])
        flash(f"Usuário {usuario['username']} foi {status_txt}.", 'info')

    return redirect(url_for('auth.usuarios'))
