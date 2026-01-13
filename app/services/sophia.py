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
    """Normaliza texto (remove acentos e lowercase)."""
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
    """Gerencia token Sophia com cache."""
    with token_lock:
        db = get_db()
        if not db: return None

        doc_ref = db.collection('system_config').document('sophia_token')
        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                if time.time() < data.get('expires_at', 0) - 30:
                    return data.get('token')
        except Exception:
            pass

        base_url = current_app.config.get('SOPHIA_BASE_URL')
        if not base_url: return None

        try:
            auth_url = f"{base_url}/api/v1/Autenticacao"
            payload = {
                "usuario": current_app.config['SOPHIA_USER'],
                "senha": current_app.config['SOPHIA_PASSWORD']
            }
            resp = requests.post(auth_url, json=payload, timeout=10)
            resp.raise_for_status()
            
            new_token = resp.text.strip()
            doc_ref.set({
                'token': new_token,
                'expires_at': time.time() + (29 * 60),
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            return new_token
        except Exception as e:
            logger.error(f"Erro Auth Sophia: {e}")
            return None

def fetch_photo(aluno_id, headers, base_url):
    """Busca foto em background."""
    try:
        url = f"{base_url}/api/v1/alunos/{aluno_id}/Fotos/FotosReduzida"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200 and resp.text:
            data = resp.json()
            return aluno_id, data.get('foto')
    except:
        pass
    return aluno_id, None

def select_official_class(turmas_raw, ignore_prefix='EM'):
    """
    Seleciona a turma OFICIAL do aluno dentre a lista retornada pela API.
    Objetivo: Replicar o visual de produção (ex: 'AI-2A-M-2036').

    Lógica:
    1. Ignora atividades extras (Futsal, Xadrez, etc).
    2. Bloqueia se encontrar prefixo ignorado (EM).
    3. Procura por turmas que contenham o Ano Vigente ou Próximo (ex: 2036, 2025),
       pois as turmas oficiais geralmente têm esse formato completo.
    """
    if not turmas_raw:
        return None

    # Lista de atividades para ignorar
    blacklist = ['FUTSAL', 'BASQUETE', 'VOLEI', 'XADREZ', 'JUDO', 'BALLET', 
                 'TEATRO', 'ROBOTICA', 'DANCA', 'CORAL', 'TREINAMENTO', 'APROFUNDAMENTO', 'MODALIDADE']
    
    # Lista plana de todas as descrições (caso venha pipe | separa também)
    candidatos = []
    for t in turmas_raw:
        desc = t.get("descricao", "").strip()
        if "|" in desc:
            candidatos.extend([x.strip() for x in desc.split("|") if x.strip()])
        else:
            candidatos.append(desc)

    turma_escolhida = None
    
    # Regex para identificar ano (ex: 2025, 2036) na string
    regex_ano = re.compile(r'20\d{2}') 

    for turma in candidatos:
        turma_upper = turma.upper()

        # 1. BLOQUEIO DE SEGURANÇA (EM)
        # Se qualquer turma for do segmento ignorado, o aluno não deve aparecer.
        if ignore_prefix:
            if turma_upper.startswith(ignore_prefix) or f"-{ignore_prefix}" in turma_upper or f" {ignore_prefix}" in turma_upper:
                return None # Bloqueia o aluno imediatamente

        # 2. IGNORAR EXTRAS
        if any(extra in turma_upper for extra in blacklist):
            continue

        # 3. CRITÉRIO DE OURO: Ter o ano na string (Padrão 'AI-2A-M-2036')
        # Se a turma tiver 4 dígitos de ano, é muito provável que seja a oficial.
        if regex_ano.search(turma):
            turma_escolhida = turma
            break # Achamos a perfeita, paramos.

        # 4. CRITÉRIO DE PRATA: Começar com sigla acadêmica (EI, AI, AF)
        # Caso a escola mude o padrão e tire o ano, isso garante que pegamos a acadêmica.
        if not turma_escolhida and (turma_upper.startswith('EI') or turma_upper.startswith('AI') or turma_upper.startswith('AF')):
            turma_escolhida = turma

    return turma_escolhida

def search_students(parte_nome, grupo_filtro):
    """Busca textual."""
    token = get_sophia_token()
    if not token: return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    params = {"Nome": parte_nome}
    
    # Configs
    ano_vigente = datetime.now().year
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()

    try:
        resp = requests.get(f"{base_url}/api/v1/alunos", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        raw_students = resp.json()
    except Exception as e:
        logger.error(f"Erro Sophia: {e}")
        return []

    termos_busca = normalize_text(parte_nome).split()
    alunos_filtrados = {}

    for aluno in raw_students:
        codigo = aluno.get("codigo")
        if not codigo or codigo in alunos_filtrados: continue

        turmas = aluno.get("turmas", [])
        
        # --- Lógica de Seleção Restaurada ---
        turma_oficial = select_official_class(turmas, prefixo_ignorado)
        
        if not turma_oficial: continue # Aluno EM ou só Futsal -> Ignora

        # Validação de Ano Vigente (apenas se tiver ano na string)
        # O regex pega o ano da string ex: 2036. Se for menor que atual, ignora.
        match_ano = re.search(r'(20\d{2})', turma_oficial)
        if match_ano:
            ano_turma = int(match_ano.group(1))
            # Se for ano passado, ignora (ex: turma de 2023 em 2025)
            # Nota: usamos < ano_vigente. Turmas futuras (2036) são aceitas (matrícula antecipada/progressão)
            if ano_turma < ano_vigente: 
                continue

        # Filtro de Grupo Visual
        if grupo_filtro != 'TODOS' and grupo_filtro not in turma_oficial.upper(): continue

        nome_norm = normalize_text(aluno.get("nome"))
        if all(t in nome_norm for t in termos_busca):
            alunos_filtrados[codigo] = {
                "id": codigo,
                "nomeCompleto": aluno.get("nome", "Nome Desconhecido"),
                "turma": turma_oficial, # Exibe a string exata (ex: AI-2A-M-2036)
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

def get_student_by_code(student_code):
    """Busca por ID (QR Code)."""
    token = get_sophia_token()
    if not token: return None

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()

    try:
        url = f"{base_url}/api/v1/alunos/{student_code}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return None
        aluno_raw = resp.json()
    except Exception:
        return None

    turmas = aluno_raw.get("turmas", [])
    
    # --- Usa a mesma lógica da busca textual ---
    turma_oficial = select_official_class(turmas, prefixo_ignorado)

    if not turma_oficial:
        return None

    # Validação simples de ano apenas para garantir que não é antiga
    ano_vigente = datetime.now().year
    match_ano = re.search(r'(20\d{2})', turma_oficial)
    if match_ano and int(match_ano.group(1)) < ano_vigente:
        return None

    student_data = {
        "id": str(aluno_raw.get("codigo")),
        "nomeCompleto": aluno_raw.get("nome", "Nome Desconhecido"),
        "turma": turma_oficial,
        "fotoUrl": None
    }

    try:
        _, foto_base64 = fetch_photo(student_data["id"], headers, base_url)
        if foto_base64:
            student_data["fotoUrl"] = foto_base64
    except Exception:
        pass

    return student_data