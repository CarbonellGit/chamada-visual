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
            response = requests.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            
            new_token = response.text.strip()
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
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(fetch_photo, aid, headers, base_url): aid for aid in alunos_filtrados}
            for future in concurrent.futures.as_completed(futures):
                aid, foto = future.result()
                if foto:
                    alunos_filtrados[aid]['fotoUrl'] = foto

    return list(alunos_filtrados.values())