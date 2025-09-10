# app.py - Versão simplificada para Google Cloud App Engine

import os
import requests
import time
import base64
from dotenv import load_dotenv
from flask import (
    Flask, jsonify, request, redirect, url_for, session, render_template, flash
)
from authlib.integrations.flask_client import OAuth
from functools import wraps
import concurrent.futures
import unicodedata

# --- 1. CONFIGURAÇÕES E INICIALIZAÇÕES ---
load_dotenv() # Carrega variáveis do .env para testes locais
app = Flask(__name__)

# Configurações do App e Chaves (lidas do ambiente)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"

# Configurações da API Sophia
SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
SOPHIA_USER = os.getenv('SOPHIA_USER')
SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')
API_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}" if SOPHIA_API_HOSTNAME and SOPHIA_TENANT else None

# Inicialização do OAuth
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
    client_kwargs={'scope': 'openid email profile'}
)

# --- 2. DECORADOR DE AUTENTICAÇÃO ---
def login_obrigatorio(f):
    """
    Decorador que verifica se um usuário está logado na sessão.

    Se o usuário não estiver na sessão, ele é redirecionado para a página de login.
    Este decorador deve ser aplicado a qualquer rota que exija autenticação.

    Args:
        f (function): A função de view a ser decorada.

    Returns:
        function: A função decorada que inclui a verificação de login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 3. FUNÇÕES AUXILIARES ---
api_token = None
token_expires_at = 0
def get_sophia_token():
    """
    Obtém um token de autenticação da API Sophia, gerenciando sua validade.

    A função primeiro verifica se as variáveis de ambiente da API Sophia estão
    configuradas. Em seguida, verifica se um token válido e não expirado já
    existe. Se não, solicita um novo token à API, armazena-o globalmente
    e define seu tempo de expiração para 29 minutos.

    Returns:
        str or None: O token de autenticação da API se a obtenção for bem-sucedida,
                     caso contrário, None.
    """
    global api_token, token_expires_at
    if not API_BASE_URL:
        print("AVISO: Variáveis da API Sophia não configuradas.")
        return None
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

def fetch_photo(aluno_id, headers):
    """
    Busca a foto de um aluno específico na API Sophia.

    Realiza uma requisição GET para o endpoint de fotos da API para obter a
    foto de um aluno em formato base64.

    Args:
        aluno_id (int): O ID do aluno cuja foto será buscada.
        headers (dict): Os cabeçalhos da requisição, incluindo o token de
                        autenticação da API.

    Returns:
        tuple: Uma tupla contendo o ID do aluno e a string da foto em base64.
               Se a foto não for encontrada ou ocorrer um erro, retorna o ID do
               aluno e None.
    """
    try:
        photo_url = f"{API_BASE_URL}/api/v1/alunos/{aluno_id}/Fotos/FotosReduzida"
        response_foto = requests.get(photo_url, headers=headers, timeout=5)
        if response_foto.status_code == 200 and response_foto.text:
            dados_foto = response_foto.json()
            foto_base64 = dados_foto.get('foto')
            if foto_base64:
                return aluno_id, foto_base64
    except requests.exceptions.RequestException:
        pass
    return aluno_id, None

def normalize_text(text):
    """
    Normaliza um texto para uma comparação 'case-insensitive' e sem acentos.

    Converte o texto para minúsculas e remove os caracteres de acentuação.

    Args:
        text (str): O texto a ser normalizado.

    Returns:
        str: O texto normalizado.
    """
    if not text:
        return ""
    text = str(text).lower()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

# --- 4. ROTA DA API DE BUSCA ---
@app.route('/api/buscar-aluno', methods=['GET'])
@login_obrigatorio
def buscar_aluno():
    """
    Endpoint da API para buscar alunos na base de dados do Sophia.

    Recebe um termo de busca (parte do nome) e um filtro de grupo via query
    string. Autentica-se na API Sophia, busca alunos, filtra os resultados
    com base nos critérios fornecidos e, em paralelo, busca as fotos dos
    alunos encontrados.

    Query Params:
        parteNome (str): O termo de busca para o nome do aluno.
        grupo (str): O grupo para filtrar os resultados (ex: 'EI', 'AI', 'AF').
                     O padrão é 'todos'.

    Returns:
        Response: Um objeto JSON contendo uma lista de alunos formatados
                  (id, nome, turma, foto) ou uma mensagem de erro.
    """
    token = get_sophia_token()
    if not token:
        return jsonify({"erro": "Não foi possível autenticar com a API Sophia."}), 500

    parte_nome = request.args.get('parteNome', '').strip()
    grupo_filtro = request.args.get('grupo', 'todos').upper()

    if not parte_nome or len(parte_nome) < 2:
        return jsonify([])

    primeiro_nome = parte_nome.split(' ')[0]
    headers = {'token': token, 'Accept': 'application/json'}
    params = {"Nome": primeiro_nome}
    search_url = f"{API_BASE_URL}/api/v1/alunos"

    try:
        response_alunos = requests.get(search_url, headers=headers, params=params)
        response_alunos.raise_for_status()
        lista_alunos_api = response_alunos.json()

        alunos_filtrados = []
        termos_busca_normalizados = normalize_text(parte_nome).split()

        for aluno in lista_alunos_api:
            turma_aluno = aluno.get("turmas", [{}])[0].get("descricao", "")
            if turma_aluno.upper().startswith('EM'):
                continue
            if grupo_filtro != 'TODOS' and not turma_aluno.upper().startswith(grupo_filtro):
                continue

            nome_completo_normalizado = normalize_text(aluno.get("nome"))
            if all(termo in nome_completo_normalizado for termo in termos_busca_normalizados):
                alunos_filtrados.append(aluno)

        alunos_map = {
            aluno.get("codigo"): {
                "id": aluno.get("codigo"),
                "nomeCompleto": aluno.get("nome", "Nome não encontrado"),
                "turma": aluno.get("turmas", [{}])[0].get("descricao", "Sem turma")
            } for aluno in alunos_filtrados if aluno.get("codigo")
        }

        fotos = {}
        if alunos_map:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_id = {executor.submit(fetch_photo, aluno_id, headers): aluno_id for aluno_id in alunos_map.keys()}
                for future in concurrent.futures.as_completed(future_to_id):
                    aluno_id, foto_data = future.result()
                    if foto_data:
                        fotos[aluno_id] = foto_data

        alunos_formatados = []
        for aluno_id, aluno_data in alunos_map.items():
            aluno_data['fotoUrl'] = fotos.get(aluno_id)
            alunos_formatados.append(aluno_data)

        return jsonify(alunos_formatados)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar alunos na API Sophia: {e}")
        return jsonify({"erro": "Ocorreu um erro ao buscar os dados no sistema Sophia."}), 500

# --- 5. ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO ---
@app.route('/')
def index():
    """
    Rota principal da aplicação.

    Redireciona o usuário para o terminal de chamada se ele já estiver logado.
    Caso contrário, redireciona para a página de login.

    Returns:
        Response: Um redirecionamento para a rota 'terminal' ou 'login'.
    """
    if 'user' in session:
        return redirect(url_for('terminal'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    """
    Renderiza a página de login.

    Returns:
        str: O conteúdo HTML da página de login.
    """
    return render_template('login.html')

@app.route('/entrar-google')
def login_google():
    """
    Inicia o fluxo de autenticação com o Google.

    Redireciona o usuário para a página de consentimento do Google para
    autorizar a aplicação.

    Returns:
        Response: Um redirecionamento para o serviço de autenticação do Google.
    """
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/google-auth')
def google_auth():
    """
    Callback para o fluxo de autenticação do Google.

    Processa a resposta do Google após o login. Se o e-mail do usuário
    pertencer ao domínio permitido, suas informações são salvas na sessão
    e ele é redirecionado para o terminal. Caso contrário, uma mensagem
    de erro é exibida.

    Returns:
        Response: Um redirecionamento para a rota 'terminal' em caso de sucesso
                  ou de volta para 'login' em caso de falha.
    """
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    if not user_info or not user_info.get('email', '').endswith('@colegiocarbonell.com.br'):
        flash('Acesso negado. Utilize uma conta do Colégio Carbonell.', 'danger')
        return redirect(url_for('login'))

    # Simplesmente salva na sessão, sem banco de dados
    session['user'] = {'email': user_info['email'], 'name': user_info['name']}
    return redirect(url_for('terminal'))

@app.route('/logout')
def logout():
    """
    Realiza o logout do usuário.

    Remove as informações do usuário da sessão e o redireciona para a
    página de login.

    Returns:
        Response: Um redirecionamento para a rota 'login'.
    """
    session.pop('user', None)
    return redirect(url_for('login'))

# --- 6. ROTAS DA APLICAÇÃO ---
@app.route('/terminal')
@login_obrigatorio
def terminal():
    """
    Renderiza a página do terminal de chamada.

    Esta página é protegida e requer que o usuário esteja logado.

    Returns:
        str: O conteúdo HTML da página do terminal.
    """
    return render_template('terminal.html')

@app.route('/painel')
def painel():
    """
    Renderiza a página do painel de exibição.

    Esta página é pública e mostra os alunos que foram chamados em
    tempo real.

    Returns:
        str: O conteúdo HTML da página do painel.
    """
    return render_template('painel.html')

# A seção if __name__ == '__main__' foi removida pois o Gunicorn irá gerenciar o servidor.
