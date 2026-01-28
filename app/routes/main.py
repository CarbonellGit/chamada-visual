from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps

bp = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('main.terminal'))
    return redirect(url_for('auth.login'))

@bp.route('/terminal')
@login_required
def terminal():
    return render_template('terminal.html')

@bp.route('/painel')
def painel():
    """
    Painel legado/padrão.
    (Pode ser mantido para testes ou compatibilidade)
    """
    return render_template('painel.html')

@bp.route('/painel-infantil')
def painel_infantil():
    """
    Renderiza o painel conectado à coleção 'chamados_ei'.
    """
    return render_template('painel_base.html', collection_name='chamados_ei')

@bp.route('/painel-fundamental')
def painel_fundamental():
    """
    Renderiza o painel conectado à coleção 'chamados_fund'.
    Nota: Agora exclui turmas de 1º ano (1A, 1B, 1C).
    """
    return render_template('painel_base.html', collection_name='chamados_fund')

@bp.route('/painel-1anos')
def painel_1anos():
    """
    NOVA ROTA: Renderiza o painel exclusivo para 1ºs Anos.
    Conectado à coleção 'chamados_1ano'.
    """
    return render_template('painel_base.html', collection_name='chamados_1ano')