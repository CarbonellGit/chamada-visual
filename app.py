# -*- coding: utf-8 -*-
"""
Aplicação web Flask para o sistema de Chamada Visual do Colégio Carbonell.

Descrição geral:
- Este módulo implementa um servidor Flask que permite pesquisar alunos na API
    do sistema de gestão (SophiA), autenticar usuários via Google OAuth (restrito
    ao domínio da escola) e publicar chamadas de alunos em coleções do Firestore
    para serem exibidas em painéis em tempo real.

Funcionalidades principais:
- Autenticação com contas Google do domínio permitido (ALLOWED_DOMAIN).
- Obtenção e cache de token para a API SophiA com persistência em arquivo.
- Busca de alunos por nome, com filtros por grupo/segmento e exclusão de
    determinadas turmas (ex.: Ensino Médio).
- Busca paralela de fotos dos alunos para reduzir latência na resposta.
- Publicação de eventos de "chamada" no Firestore em coleções específicas
    dependendo da turma (ex.: 'chamados_ei', 'chamados_fund', 'chamados').

Notas de versão (resumo técnico):
- Ajuste do filtro de grupo para verificar inclusão ("in") em vez de
    startswith, para cobrir siglas embutidas em nomes de turma (ex: 'INT-AI').
- Reativação de filtro que exclui turmas do Ensino Médio (EM) dos resultados.

Observações de design/segurança:
- O código usa um arquivo local (instância) para cache do token da API SophiA
    e um lock de thread para evitar condições de corrida quando múltiplas
    requisições tentam renovar o token simultaneamente.
- A integração com o Firestore é opcional: o app continua rodando sem ela,
    mas endpoints que dependem do banco retornam erro 500 quando o cliente não
    foi inicializado.

Este arquivo adiciona comentários e docstrings detalhados para facilitar
manutenção, revisão e auditoria do comportamento em produção.
"""

# --- 1. IMPORTAÇÕES DE BIBLIOTECAS ---
import os
import time
import json
import threading
import unicodedata
import concurrent.futures
import re
import tempfile  # <-- CORREÇÃO 1: Adicionado para cache de token
from datetime import datetime
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from functools import wraps
from flask import (
    Flask, jsonify, request, redirect, url_for, session, render_template, flash
)
from authlib.integrations.flask_client import OAuth

# --- 2. CONFIGURAÇÕES E INICIALIZAÇÕES ---

load_dotenv()
app = Flask(__name__, instance_relative_config=True)

# --- Bloco de Inicialização do Firebase Admin SDK ---

# !! CORREÇÃO CRÍTICA 2 !!
# Remove a variável de credenciais local (GOOGLE_APPLICATION_CREDENTIALS)
# que o 'gcloud deploy' pode ter capturado do ambiente Windows (visto nos logs),
# pois ela entra em conflito com as credenciais padrão do App Engine.
if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    print("Variável de ambiente 'GOOGLE_APPLICATION_CREDENTIALS' local removida para usar credenciais do GAE.")

try:
    # CORREÇÃO 3: Força o uso do ID do projeto correto no GAE
    firebase_admin.initialize_app(options={
        'projectId': 'singular-winter-471620-u0',
    })
    db = firestore.client()
    print("Firebase Admin SDK inicializado com sucesso usando credenciais do ambiente.")
except Exception as e:
    db = None
    print(f"ERRO: Não foi possível inicializar o Firebase Admin SDK: {e}")

# --- Configurações do App e Chaves (lidas do ambiente) ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"
ALLOWED_DOMAIN = os.getenv('ALLOWED_EMAIL_DOMAIN')

# --- Configurações da API Sophia (sistema de gestão escolar) ---
SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
SOPHIA_USER = os.getenv('SOPHIA_USER')
SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')
API_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}" if SOPHIA_API_HOSTNAME and SOPHIA_TENANT else None

# --- Inicialização do OAuth para Login com Google ---
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
    client_kwargs={'scope': 'openid email profile'}
)

# --- 3. DECORADOR DE AUTENTICAÇÃO ---
def login_obrigatorio(f):
    """
    Decorador para proteger rotas que exigem autenticação.

    Comportamento:
    - Verifica se existe a chave 'user' na sessão Flask.
    - Se não existir, exibe uma mensagem (flash) e redireciona para a
      página de login.

    Uso:
        @app.route('/rota-protegida')
        @login_obrigatorio
        def rota():
            ...

    Observações:
    - Não altera o comportamento da função decorada, apenas a intercepta para
      verificação de sessão. Mantém os metadados originais da função
      (functools.wraps).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # A sessão Flask armazena informações do usuário após login bem-sucedido.
        # Se a chave não existir, o usuário não está autenticado.
        if 'user' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        # Se autenticado, prossegue com a execução da rota original.
        return f(*args, **kwargs)
    return decorated_function

# --- 4. FUNÇÕES AUXILIARES ---

# CORREÇÃO 4: Usa o diretório temporário do sistema (funciona no Windows e Linux)
TOKEN_CACHE_FILE = os.path.join(tempfile.gettempdir(), 'sophia_token.json')
token_lock = threading.Lock()
# token_lock: garante exclusão mútua ao acessar/atualizar o arquivo de cache
# do token (TOKEN_CACHE_FILE). Evita condições de corrida quando múltiplas
# requisições simultâneas detectam token expirado e tentam renová-lo ao
# mesmo tempo. A escolha de um lock de thread é suficiente para o modelo de
# execução do Flask em desenvolvimento; em ambientes distribuídos seria
# necessário um mecanismo de lock distribuído (ex: Redis, Cloud Storage).

def get_sophia_token():
    """
    Obtém um token de autenticação para a API Sophia, utilizando um cache em
    arquivo localizado na pasta de instância do Flask.

    Estratégia:
    1. Usa um lock (token_lock) para evitar que múltiplas threads tentem criar
       ou renovar o token simultaneamente.
    2. Tenta ler o arquivo de cache (`TOKEN_CACHE_FILE`) e verifica validade
       temporal do token com base em 'expires_at'. Se válido, retorna o token.
    3. Caso não haja token válido, solicita um novo token à API de
       autenticação da SophiA e grava o resultado no arquivo com tempo de
       expiração (29 minutos a partir do momento atual).

    Retorno:
    - Retorna o token (str) em caso de sucesso.
    - Retorna None em casos de erro (diretório inacessível, falha de rede,
      variáveis de ambiente não configuradas, etc.).

    Observações/Edge cases:
    - O arquivo de cache pode ser inválido ou corrompido; nesse caso o código
      ignora o conteúdo e solicita um novo token.
    - O tempo de expiração não é fornecido pela API (suposição): o código usa
      29 minutos para garantir margem antes do expiramento real.
    - Se `API_BASE_URL` não estiver configurado, a função retorna None.
    """
    # Protegemos toda a operação de leitura/validação/escrita do cache com
    # um lock para evitar que duas threads corrompam o arquivo JSON.
    with token_lock:
        # CORREÇÃO 5: Garante que o diretório temporário exista.
        try:
            os.makedirs(tempfile.gettempdir(), exist_ok=True)
        except OSError as e:
            # Em ambiente com permissões restritas, criar o diretório pode falhar.
            print(f"Erro crítico ao criar o diretório temporário: {e}")
            return None

        # Tenta carregar token em cache e validar tempo de vida. Estrutura
        # esperada do arquivo: { 'token': '<token_str>', 'expires_at': 1234567890.0 }
        # Se o arquivo estiver ausente, inválido ou com token expirado,
        # prosseguimos para solicitar um novo token à API.
        try:
            with open(TOKEN_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                token = cache_data.get('token')
                expires_at = cache_data.get('expires_at')
                if token and time.time() < expires_at:
                    # Token ainda válido, retorna imediatamente.
                    return token
        except (FileNotFoundError, json.JSONDecodeError):
            # Cache ausente ou corrompido => prosseguir para renovação.
            pass

        # Informativo: o cache está ausente ou inválido, vamos solicitar novo
        # token. Em produção, esse log pode ser ajustado para nível de WARNING.
        print("Cache do token Sophia inválido ou inexistente. Solicitando um novo token.")
        if not API_BASE_URL:
            # Configuração incompleta impede autenticação contra a API.
            print("AVISO: Variáveis da API Sophia não configuradas no arquivo .env.")
            return None

        # Monta a requisição de autenticação para a API SophiA.
        auth_url = f"{API_BASE_URL}/api/v1/Autenticacao"
        auth_data = {"usuario": SOPHIA_USER, "senha": SOPHIA_PASSWORD}
        # Realiza a chamada POST para obter o token de autenticação. Timeout
        # curto protege o serviço caso a API esteja indisponível.
        try:
            response = requests.post(auth_url, json=auth_data, timeout=10)
            response.raise_for_status()
            # A API retorna o token no corpo como texto simples (observação do
            # comportamento atual). Removemos espaços em branco.
            new_token = response.text.strip()
            # Define uma expiração conservadora (29 minutos) para forçar renovação
            # antes do prazo real e evitar falhas durante uso intensivo.
            new_expires_at = time.time() + (29 * 60)
            with open(TOKEN_CACHE_FILE, 'w') as f:
                json.dump({'token': new_token, 'expires_at': new_expires_at}, f)
            print("Novo token da API Sophia obtido e salvo em cache com sucesso.")
            return new_token
        except requests.exceptions.RequestException as e:
            # Erros de rede ou respostas inválidas são tratados aqui; retornamos
            # None para que o chamador possa lidar com a ausência de token.
            print(f"Erro ao obter novo token da API Sophia: {e}")
            return None

def fetch_photo(aluno_id, headers):
    """
    Busca a foto reduzida de um aluno a partir da API SophiA.

    Parâmetros:
    - aluno_id: identificador do aluno (normalmente o código retornado pela API).
    - headers: dicionário de headers HTTP (deve conter o token de autenticação).

    Retorno:
    - Tupla (aluno_id, foto_base64) quando a foto é obtida com sucesso.
    - Tupla (aluno_id, None) quando não há foto ou ocorreu erro na requisição.

    Observações:
    - Projetada para ser executada em paralelo via ThreadPoolExecutor. Não levanta
      exceções para que o executor possa coletar resultados parcimoniosamente.
    - Timeout curto (5s) para não atrasar significativamente a montagem da
      resposta principal quando o serviço de fotos estiver lento.
    """
    # Esta função foi projetada para ser resiliente: falhas na obtenção da
    # foto não devem interromper a listagem de alunos. Por isso capturamos
    # exceções e retornamos (aluno_id, None) em caso de erro.
    try:
        photo_url = f"{API_BASE_URL}/api/v1/alunos/{aluno_id}/Fotos/FotosReduzida"
        response_foto = requests.get(photo_url, headers=headers, timeout=5)
        if response_foto.status_code == 200 and response_foto.text:
            dados_foto = response_foto.json()
            foto_base64 = dados_foto.get('foto')
            if foto_base64:
                return aluno_id, foto_base64
    except requests.exceptions.RequestException:
        # Qualquer erro de rede ou timeout é ignorado e tratado como ausência de
        # foto para não interromper a resposta para o usuário.
        pass
    return aluno_id, None

def normalize_text(text):
        """
        Normaliza uma string para facilitar comparações de busca.

        Passos realizados:
        - Converte o valor para string e passa para minúsculas.
        - Remove marcas de acentuação usando normalização NFD e filtrando caracteres
            da categoria 'Mn' (marks nonspacing).

        Retorno:
        - String normalizada pronta para comparações.
        - Retorna string vazia quando a entrada é None/Falsey.
        """
        if not text: return ""
        text = str(text).lower()
        return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

# --- 5. ROTAS DA API ---
@app.route('/api/buscar-aluno', methods=['GET'])
@login_obrigatorio
def buscar_aluno():
    """
    Endpoint para buscar alunos na API Sophia com uma estratégia de busca ampla.
    """
    # Fluxo principal: obtém token (do cache ou renovando), então consulta a
    # API de alunos. Se não houver token válido o endpoint devolve erro 500.
    token = get_sophia_token()
    if not token:
        return jsonify({"erro": "Não foi possível autenticar com a API Sophia."}), 500
    
    # Ano atual utilizado para filtrar turmas cujo ano (ex: 2026) indica
    # que o aluno já teria se formado (caso o número seja menor que o vigente).
    ano_vigente = datetime.now().year

    # Parâmetros de consulta recebidos via query string:
    # - parteNome: fragmento do nome a ser pesquisado (mínimo 2 caracteres exigidos)
    # - grupo: filtro opcional por segmento/turma (ex: 'EI', 'AI', 'AF', 'TODOS')
    parte_nome = request.args.get('parteNome', '').strip()
    grupo_filtro = request.args.get('grupo', 'todos').upper()

    # Validação rápida: evita consultas desnecessárias para termos curtos/ausentes.
    if not parte_nome or len(parte_nome) < 2:
        return jsonify([])

    headers = {'token': token, 'Accept': 'application/json'}

    params = { "Nome": parte_nome }
    search_url = f"{API_BASE_URL}/api/v1/alunos"

    try:
        response_alunos = requests.get(search_url, headers=headers, params=params, timeout=15)
        response_alunos.raise_for_status()
        lista_alunos_api = response_alunos.json()

        # Preparação das estruturas para filtragem local dos resultados da API.
        alunos_filtrados = []
        termos_busca_normalizados = normalize_text(parte_nome).split()
        # Evita duplicidade de alunos no resultado final (mesmo código).
        codigos_alunos_adicionados = set()

        for aluno in lista_alunos_api:
            # Valida presença do código do aluno; pula entradas inválidas/duplicadas.
            codigo_aluno = aluno.get("codigo")
            if not codigo_aluno or codigo_aluno in codigos_alunos_adicionados:
                continue

            # Extrai descrição da turma (padrão: usa a primeira turma se houver várias).
            turma_aluno = aluno.get("turmas", [{}])[0].get("descricao", "")
            if not turma_aluno:
                # Se não houver informação de turma, não temos como categorizar o aluno.
                continue

            # Tenta extrair um ano contido no nome da turma (ex: '2025'). Se encontrado,
            # filtra alunos cuja data indica formatura anterior ao ano vigente.
            try:
                match = re.search(r'(\d{4})', turma_aluno)
                if not match:
                    # Sem ano na descrição => não conseguimos validar a vigência.
                    continue
                ano_formatura = int(match.group(1))
                if ano_formatura < ano_vigente:
                    # Ignora alunos que aparentam ter se formado em anos anteriores.
                    continue
            except (ValueError, TypeError):
                # Em casos inesperados, descartamos o registro em vez de falhar.
                continue

            # --- FILTRO REATIVADO: Exclui alunos do Ensino Médio (EM) ---
            # Os registros cuja turma inicia com 'EM' (sigla do Ensino Médio) são
            # excluídos para focar nos segmentos Infantile/Fundamental.
            if turma_aluno.upper().startswith('EM'):
                continue

            # --- CORREÇÃO (INT): Usa 'in' para incluir turmas de período integral ---
            # Se o cliente da UI solicitou um filtro de grupo diferente de 'TODOS',
            # apenas inclui alunos cuja descrição da turma contenha essa sigla.
            if grupo_filtro != 'TODOS' and grupo_filtro not in turma_aluno.upper():
                continue

            # Normaliza o nome do aluno e verifica se todos os termos de busca
            # fornecidos aparecem no nome (ordem não importa).
            nome_completo_normalizado = normalize_text(aluno.get("nome"))
            if all(termo in nome_completo_normalizado for termo in termos_busca_normalizados):
                alunos_filtrados.append(aluno)
                codigos_alunos_adicionados.add(codigo_aluno)
        
        # Mapeia os alunos filtrados em uma estrutura mais compacta que será
        # enviada ao frontend. Usa o código do aluno como chave para facilitar
        # a associação com fotos obtidas em paralelo.
        alunos_map = {
            aluno.get("codigo"): {
                "id": aluno.get("codigo"),
                "nomeCompleto": aluno.get("nome", "Nome não encontrado"),
                "turma": aluno.get("turmas", [{}])[0].get("descricao", "Sem turma")
            } for aluno in alunos_filtrados if aluno.get("codigo")
        }

        # Busca fotos em paralelo apenas se houver alunos para buscar. A operação
        # é opcional: quando a foto não é encontrada, o campo 'fotoUrl' ficará
        # com valor None, e a interface do frontend deve lidar com isso.
        fotos = {}
        if alunos_map:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Submete chamadas assíncronas para fetch_photo para cada aluno.
                future_to_id = {executor.submit(fetch_photo, aluno_id, headers): aluno_id for aluno_id in alunos_map.keys()}
                for future in concurrent.futures.as_completed(future_to_id):
                    # future.result() retorna a tupla (aluno_id, foto_base64|None)
                    # conforme definido em fetch_photo. Usamos esse padrão para
                    # associar fotos por id de forma simples e tolerante a erros.
                    aluno_id, foto_data = future.result()
                    if foto_data:
                        fotos[aluno_id] = foto_data

        # Constrói a lista final que será serializada como JSON para o cliente.
        alunos_formatados = []
        for aluno_id, aluno_data in alunos_map.items():
            aluno_data['fotoUrl'] = fotos.get(aluno_id)
            alunos_formatados.append(aluno_data)

        return jsonify(alunos_formatados)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar alunos na API Sophia: {e}")
        return jsonify({"erro": "Ocorreu um erro ao buscar os dados no sistema Sophia."}), 500

@app.route('/api/chamar-aluno', methods=['POST'])
@login_obrigatorio
def chamar_aluno():
    """
    Endpoint HTTP que recebe uma chamada (POST) do frontend indicando que um
    aluno deve ser chamado/exibido no painel.

    Fluxo:
    1. Verifica se a conexão com o Firestore foi inicializada; caso contrário,
       retorna erro 500 (configuração ausente).
    2. Lê o payload JSON enviado pelo cliente e valida sua presença.
    3. Determina a coleção do Firestore onde o documento será inserido com base
       na turma do aluno:
       - turmas que começam com 'EI' -> 'chamados_ei'
       - turmas que contêm 'AI' ou 'AF' -> 'chamados_fund'
       - caso contrário -> 'chamados' (padrão)
    4. Anexa um campo 'timestamp' com o valor SERVER_TIMESTAMP do Firestore e
       grava o documento na coleção selecionada.

    Retornos HTTP:
    - 200: sucesso com mensagem de confirmação.
    - 400: payload ausente ou inválido.
    - 500: problemas de configuração do Firestore ou erro interno ao salvar.

    Observações:
    - O endpoint não valida a estrutura interna do objeto do aluno (por exemplo,
      campos obrigatórios além de 'turma'). Espera-se que o frontend envie um
      objeto bem formado.
    - Em ambientes de alta concorrência, a gravação no Firestore deve ser
      monitorada e, se necessário, implementados retries/exponential backoff.
    """
    if not db:
        # Este é o erro que está acontecendo!
        # db é 'None' por causa da falha de inicialização (vista nos logs).
        print("ERRO EM /api/chamar-aluno: A variável 'db' do Firestore é 'None'. Verifique a inicialização do SDK.")
        return jsonify({"erro": "A conexão com o Firestore não está configurada no servidor."}), 500

    student_data = request.get_json()
    if not student_data:
        return jsonify({"erro": "Nenhum dado do aluno foi recebido."}), 400

    turma = student_data.get("turma", "").strip().upper()
    collection_name = "chamados"

    # Seleciona a coleção destino com base em padrões simples na descrição da
    # turma. Padrões são suficientes para o caso de uso atual, mas podem ser
    # extraídos para uma função separada se a lógica crescer.
    if turma.startswith('EI'):
        collection_name = "chamados_ei"
    elif 'AI' in turma or 'AF' in turma:
        collection_name = "chamados_fund"

    print(f"Direcionando aluno '{student_data.get('nomeCompleto')}' para a coleção: {collection_name}")

    try:
        # Usa SERVER_TIMESTAMP para que o Firestore atribua o carimbo de tempo
        # no lado do servidor, garantindo consistência entre clientes.
        student_data['timestamp'] = firestore.SERVER_TIMESTAMP
        db.collection(collection_name).add(student_data)
        return jsonify({"sucesso": True, "mensagem": "Aluno chamado com sucesso!"}), 200
    except Exception as e:
        # Erros na gravação são logados e repassados ao cliente como mensagem
        # genérica para evitar vazamento de detalhes sensíveis.
        print(f"Erro ao salvar no Firestore na coleção '{collection_name}': {e}")
        return jsonify({"erro": f"Ocorreu um erro interno ao chamar o aluno: {e}"}), 500

# --- 6. ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO ---
@app.route('/')
def index():
    """
    Rota raiz que redireciona o usuário autenticado para o terminal; caso
    contrário direciona para a página de login.
    """
    if 'user' in session: return redirect(url_for('terminal'))
    return redirect(url_for('login'))

@app.route('/login')
def login(): return render_template('login.html')

@app.route('/entrar-google')
def login_google():
    redirect_uri = url_for('google_auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/google-auth')
def google_auth():
    # Ponto de callback do fluxo OAuth2. A biblioteca Authlib trata o fluxo
    # PKCE/OpenID Connect e retorna um dicionário com as informações do usuário.
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    # Verifica se o domínio do e-mail do usuário é permitido. Em falta dessa
    # configuração (ALLOWED_DOMAIN), o acesso também é negado por segurança.
    if not ALLOWED_DOMAIN or not user_info or not user_info.get('email', '').endswith(ALLOWED_DOMAIN):
        flash('Acesso negado. Utilize uma conta do Colégio Carbonell.', 'danger')
        return render_template('acesso_negado.html')

    # Armazena dados essenciais do usuário na sessão para uso posterior.
    session['user'] = {'email': user_info['email'], 'name': user_info['name']}
    return redirect(url_for('terminal'))

@app.route('/logout')
def logout():
    # Remove dados de autenticação da sessão do usuário.
    session.pop('user', None)
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))

# --- 7. ROTAS PRINCIPAIS DA APLICAÇÃO ---
@app.route('/terminal')
@login_obrigatorio
def terminal(): return render_template('terminal.html')

@app.route('/painel')
def painel(): return render_template('painel.html')

@app.route('/painel-infantil')
def painel_infantil():
    return render_template('painel_base.html', collection_name='chamados_ei')

@app.route('/painel-fundamental')
def painel_fundamental():
    return render_template('painel_base.html', collection_name='chamados_fund')

# --- 8. BLOCO DE EXECUÇÃO PARA DESENVOLVIMENTO ---
if __name__ == '__main__':
    # Executa o servidor Flask em modo de desenvolvimento. Em produção, um
    # servidor WSGI (gunicorn, uWSGI) deve ser usado no lugar deste bloco.
    app.run(host='0.0.0.0', port=5000, debug=True)