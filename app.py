# app.py - Versão Final para Deploy no Render

import os
import requests
import time
import base64
from dotenv import load_dotenv
from flask import (
    Flask, jsonify, request, redirect, url_for, session, render_template, flash
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from authlib.integrations.flask_client import OAuth
from functools import wraps

# --- 1. CONFIGURAÇÕES E INICIALIZAÇÕES ---
load_dotenv()
app = Flask(__name__)

# Configurações do App e Chaves
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"

# Configuração do Banco de Dados para Produção (Render) e Desenvolvimento (Local)
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configurações da API Sophia
SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
SOPHIA_USER = os.getenv('SOPHIA_USER')
SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')
API_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}" if SOPHIA_API_HOSTNAME and SOPHIA_TENANT else None

# Inicialização do OAuth para Login com Google
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
    client_kwargs={'scope': 'openid email profile'}
)

# --- 2. MODELO DO BANCO DE DADOS ---
class Usuario(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)

# Cria as tabelas do banco de dados na inicialização, se elas não existirem.
# Isso é crucial para o primeiro deploy no Render.
with app.app_context():
    db.create_all()

# --- 3. DECORADOR DE AUTENTICAÇÃO ---
def login_obrigatorio(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 4. FUNÇÕES AUXILIARES ---
api_token = None
token_expires_at = 0
def get_sophia_token():
    global api_token, token_expires_at
    if api_token and time.time() < token_expires_at:
        return api_token
    
    auth_url = f"{API_BASE_URL}/api/v1/Autenticacao"
    auth_data = {"usuario": SOPHIA_USER, "senha": SOPHIA_PASSWORD}
    try:
        response = requests.post(auth_url, json=auth_data, timeout=10)
        response.raise_for_status()
        api_token = response.text.strip()
        token_expires_at = time.time() + (29 * 60)
        print("Novo token da API Sophia obtido com sucesso.")
        return api_token
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter token da API Sophia: {e}")
        return None

# --- 5. ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('terminal'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/entrar-google')
def login_google():
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/google-auth')
def google_auth():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info or not user_info.get('email', '').endswith('@colegiocarbonell.com.br'):
        flash('Acesso negado. Utilize uma conta do Colégio Carbonell.', 'danger')
        return redirect(url_for('login'))

    user = db.session.execute(db.select(Usuario).filter_by(email=user_info['email'])).scalar_one_or_none()
    if user is None:
        user = Usuario(email=user_info['email'], nome=user_info['name'])
        db.session.add(user)
        db.session.commit()
    
    session['user'] = {'email': user.email, 'name': user.nome}
    return redirect(url_for('terminal'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# --- 6. ROTAS DA APLICAÇÃO ---
@app.route('/terminal')
@login_obrigatorio
def terminal():
    return render_template('terminal.html')

@app.route('/painel')
def painel():
    return render_template('painel.html')

@app.route('/api/buscar-aluno', methods=['GET'])
@login_obrigatorio
def buscar_aluno():
    token = get_sophia_token()
    if not token:
        return jsonify({"erro": "Não foi possível autenticar com a API Sophia."}), 500
    
    parte_nome = request.args.get('parteNome', '').strip()
    if not parte_nome or len(parte_nome) < 2:
        return jsonify([])

    headers = {'token': token, 'Accept': 'application/json'}
    params = {"Nome": parte_nome}
    search_url = f"{API_BASE_URL}/api/v1/alunos"
    
    try:
        response_alunos = requests.get(search_url, headers=headers, params=params, timeout=10)
        response_alunos.raise_for_status()
        lista_alunos = response_alunos.json()
        
        alunos_formatados = []
        for aluno in lista_alunos:
            aluno_id = aluno.get("codigo")
            if not aluno_id: continue
            
            turmas_do_aluno = aluno.get("turmas", [])
            nome_da_turma = turmas_do_aluno[0].get("descricao") if turmas_do_aluno else "Sem turma"

            alunos_formatados.append({
                "id": aluno_id,
                "nomeCompleto": aluno.get("nome", "Nome não encontrado"),
                "turma": nome_da_turma
            })
        return jsonify(alunos_formatados)
        
    except requests.exceptions.Timeout:
        return jsonify({"erro": "O sistema externo (Sophia) demorou muito para responder."}), 504
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            global api_token
            api_token = None
            return jsonify({"erro": "Falha na autenticação com o sistema Sophia. Tente novamente."}), 500
        else:
            return jsonify({"erro": f"O sistema Sophia retornou um erro inesperado: {e.response.status_code}"}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"erro": "Não foi possível conectar ao sistema Sophia. Verifique a conexão."}), 500

@app.route('/api/aluno/<int:aluno_id>/foto')
@login_obrigatorio
def buscar_foto_aluno(aluno_id):
    token = get_sophia_token()
    if not token:
        return jsonify({"erro": "Sem token de autenticação"}), 500

    headers = {'token': token, 'Accept': 'application/json'}
    foto_url = f"{API_BASE_URL}/api/v1/alunos/{aluno_id}/Fotos/FotosReduzida"
    
    foto_data_uri = "URL_DA_FOTO_PADRAO_AQUI" # Usamos a URL no frontend, então este valor não é crítico
    try:
        response_foto = requests.get(foto_url, headers=headers, timeout=5)
        if response_foto.status_code == 200 and response_foto.text:
            dados_foto = response_foto.json()
            foto_base64 = dados_foto.get('foto')
            if foto_base64:
                foto_data_uri = foto_base64
    except requests.exceptions.RequestException as e:
        print(f"Não foi possível buscar a foto para o aluno {aluno_id}: {e}")
    
    return jsonify({"fotoUrl": foto_data_uri})

# --- 7. COMANDOS DE ADMINISTRAÇÃO ---
@app.cli.command("init-db")
def init_db_command():
    """Cria as tabelas do banco de dados."""
    db.create_all()
    print("Banco de dados de usuários inicializado.")

# --- 8. INICIALIZAÇÃO DO SERVIDOR ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
