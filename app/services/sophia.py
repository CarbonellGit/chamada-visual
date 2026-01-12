import time
import threading
import unicodedata
import re
import requests
import concurrent.futures
import logging
from datetime import datetime
from flask import current_app
from firebase_admin import firestore

# Configura Logger
logger = logging.getLogger(__name__)
token_lock = threading.Lock()

def normalize_text(text):
    """
    Normaliza uma string removendo acentos e convertendo para minúsculas.

    Args:
        text (str): Texto original.

    Returns:
        str: Texto normalizado (ex: 'João' -> 'joao').
    """

    if not text: return ""
    text = str(text).lower()

    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def get_db():
    try:
        if current_app:
            return getattr(current_app, 'db', firestore.client())
        return firestore.client()
    except ValueError:
        return None

def get_sophia_token():
    """
    Gerencia a obtenção e renovação do token de autenticação da API Sophia.

    Implementa um padrão de Cache-Aside usando o Firestore para persistir o token
    e evitar chamadas excessivas ao endpoint de autenticação.
    Utiliza um `threading.Lock` para garantir thread-safety durante a renovação.

    Fluxo:
    1. Tenta ler token válido do Firestore.
    2. Se expirado ou inexistente, autentica na API Sophia.
    3. Salva novo token no Firestore com validade de 29 minutos.

    Returns:
        str | None: Token de acesso válido ou None em caso de falha.
    """
    with token_lock:
        db = get_db()
        if not db:
            logger.error("Firestore não disponível para recuperar token.")
            return None

        doc_ref = db.collection('system_config').document('sophia_token')

        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                # Verifica se o token ainda é válido (com margem de 30s)
                if time.time() < data.get('expires_at', 0) - 30:
                    return data.get('token')
        except Exception as e:
            logger.warning(f"Erro ao ler token do cache: {e}")

        base_url = current_app.config.get('SOPHIA_BASE_URL')
        if not base_url:
            logger.error("SOPHIA_BASE_URL não configurada.")
            return None

        try:
            logger.info("Renovando token da API Sophia...")
            auth_url = f"{base_url}/api/v1/Autenticacao"
            payload = {
                "usuario": current_app.config['SOPHIA_USER'],
                "senha": current_app.config['SOPHIA_PASSWORD']
            }
            # Timeout curto para não travar a thread por muito tempo
            response = requests.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            
            new_token = response.text.strip()
            # Define expiração para 29 minutos (API costuma expirar em 30)
            expires_at = time.time() + (29 * 60)
            
            doc_ref.set({
                'token': new_token,
                'expires_at': expires_at,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
                
            return new_token
        except Exception as e:
            logger.critical(f"Erro ao obter novo token Sophia: {e}")
            return None

def fetch_photo(aluno_id, headers, base_url):
    """
    Busca a foto de um aluno específico na API.

    Função auxiliar projetada para ser executada em thread separada.

    Args:
        aluno_id (str): ID/Código do aluno.
        headers (dict): Headers com token de autenticação.
        base_url (str): URL base da API.

    Returns:
        tuple: (aluno_id, dados_da_foto_base64) ou (aluno_id, None) em caso de erro.
    """
    try:
        url = f"{base_url}/api/v1/alunos/{aluno_id}/Fotos/FotosReduzida"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200 and resp.text:
            data = resp.json()
            return aluno_id, data.get('foto')
    except:
        pass
    return aluno_id, None

def search_students(parte_nome, grupo_filtro):
    """
    Busca alunos na API Sophia com base no nome e aplicas filtros de negócio.

    Lógica de Filtragem:
    1. Remove alunos de turmas ignoradas (ex: Ensino Médio 'EM').
    2. Filtra por grupo se especificado ('TODOS' traz tudo).
    3. Remove alunos de turmas antigas (ano anterior ao vigente).
    4. Realiza busca textual no nome normalizado.

    Otimização:
    - Realiza o fetch de fotos em paralelo (ThreadPool) para os alunos encontrados.

    Args:
        parte_nome (str): Termo de busca (nome parcial).
        grupo_filtro (str): Filtro de segmento (ex: 'EI', 'FI', 'TODOS').

    Returns:
        list[dict]: Lista de dicionários contendo dados dos alunos filtrados.
    """
    token = get_sophia_token()
    if not token:
        logger.error("Busca abortada: Falha de autenticação.")
        return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    
    ano_vigente = datetime.now().year
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()
    regex_ano = current_app.config.get('REGEX_CLASS_YEAR', r'(\d{4})')
    
    params = {"Nome": parte_nome}

    try:
        resp = requests.get(f"{base_url}/api/v1/alunos", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        raw_students = resp.json()
    except Exception as e:
        logger.error(f"Erro na requisição ao Sophia: {e}")
        return []

    termos_busca = normalize_text(parte_nome).split()
    alunos_filtrados = {}

    for aluno in raw_students:
        codigo = aluno.get("codigo")
        if not codigo or codigo in alunos_filtrados: continue

        turmas = aluno.get("turmas", [])
        if not turmas: continue
        turma_desc = turmas[0].get("descricao", "")
        turma_upper = turma_desc.upper()

        if prefixo_ignorado and turma_upper.startswith(prefixo_ignorado): continue
        if grupo_filtro != 'TODOS' and grupo_filtro not in turma_upper: continue

        match_ano = re.search(regex_ano, turma_desc)
        if match_ano and int(match_ano.group(1)) < ano_vigente: continue
        
        nome_norm = normalize_text(aluno.get("nome"))
        if all(t in nome_norm for t in termos_busca):
            alunos_filtrados[codigo] = {
                "id": codigo,
                "nomeCompleto": aluno.get("nome", "Nome Desconhecido"),
                "turma": turma_desc,
                "fotoUrl": None
            }

    if alunos_filtrados:
        # Busca fotos em paralelo para não travar a requisição
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(fetch_photo, aid, headers, base_url): aid for aid in alunos_filtrados}
            for future in concurrent.futures.as_completed(futures):
                aid, foto = future.result()
                if foto:
                    alunos_filtrados[aid]['fotoUrl'] = foto

    return list(alunos_filtrados.values())