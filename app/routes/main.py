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
    # Painel público (sem login obrigatório, ou ajuste conforme necessidade)
    return render_template('painel.html')

@bp.route('/painel-infantil')
def painel_infantil():
    return render_template('painel_base.html', collection_name='chamados_ei')

@bp.route('/painel-fundamental')
def painel_fundamental():
    return render_template('painel_base.html', collection_name='chamados_fund')