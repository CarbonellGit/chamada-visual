from flask import Blueprint, url_for, session, redirect, render_template, flash, current_app
from app import oauth

bp = Blueprint('auth', __name__)

@bp.route('/login')
def login():
    return render_template('login.html')

@bp.route('/entrar-google')
def login_google():
    redirect_uri = url_for('auth.google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@bp.route('/google-auth')
def google_auth():
    """
    Callback de autenticação do Google OAuth.

    Processa o token recebido, verifica o domínio do e-mail (se configurado)
    e cria a sessão do usuário.

    Returns:
        Redirect: Redireciona para o terminal em sucesso ou login em falha.
    """
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    allowed_domain = current_app.config.get('ALLOWED_DOMAIN')

    if not user_info:
        flash('Falha ao obter dados do usuário.', 'danger')
        return redirect(url_for('auth.login'))

    # Validação de Domínio
    email = user_info.get('email', '')
    if allowed_domain and not email.endswith(allowed_domain):
        flash('Acesso negado. Domínio não autorizado.', 'danger')
        return render_template('acesso_negado.html')

    session['user'] = {'email': email, 'name': user_info['name']}
    return redirect(url_for('main.terminal'))

@bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('auth.login'))