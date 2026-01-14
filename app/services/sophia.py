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
    try:
        url = f"{base_url}/api/v1/alunos/{aluno_id}/Fotos/FotosReduzida"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200 and resp.text:
            data = resp.json()
            return aluno_id, data.get('foto')
    except:
        pass
    return aluno_id, None

def select_official_class(turmas_raw, ignore_prefix='EM', debug_student_id=None):
    """
    Seleciona a melhor turma possível com Fallback.
    """
    if not turmas_raw:
        if debug_student_id: print(f"ALUNO {debug_student_id}: Sem turmas (lista vazia ou None).")
        return None

    blacklist = ['FUTSAL', 'BASQUETE', 'VOLEI', 'XADREZ', 'JUDO', 'BALLET', 
                 'TEATRO', 'ROBOTICA', 'DANCA', 'CORAL', 'TREINAMENTO', 'APROFUNDAMENTO', 'MODALIDADE', 'ALMOÇO', 'PERÍODO']
    
    candidatos = []
    for t in turmas_raw:
        desc = t.get("descricao", "").strip()
        if "|" in desc:
            candidatos.extend([x.strip() for x in desc.split("|") if x.strip()])
        else:
            candidatos.append(desc)

    if debug_student_id:
        print(f"ALUNO {debug_student_id} - Candidatos Brutos: {candidatos}")

    turma_escolhida = None
    regex_ano = re.compile(r'20\d{2}') 
    candidatos_validos = []

    # 1. FILTRAGEM INICIAL
    for turma in candidatos:
        turma_upper = turma.upper()

        # Bloqueio de EM
        if ignore_prefix:
            if turma_upper.startswith(ignore_prefix) or f"-{ignore_prefix}" in turma_upper or f" {ignore_prefix}" in turma_upper:
                if debug_student_id: print(f"ALUNO {debug_student_id}: Bloqueado por EM na turma '{turma}'")
                return None 

        # Ignorar Extras
        if any(extra in turma_upper for extra in blacklist):
            continue

        candidatos_validos.append(turma)

    if not candidatos_validos:
        if debug_student_id: print(f"ALUNO {debug_student_id}: Todas as turmas foram filtradas (Blacklist).")
        return None

    # 2. SELEÇÃO HIERÁRQUICA
    
    # Ouro: Tem Ano (20xx)
    for turma in candidatos_validos:
        if regex_ano.search(turma):
            turma_escolhida = turma
            if debug_student_id: print(f"ALUNO {debug_student_id}: Selecionada (OURO - Ano): {turma}")
            break

    # Prata: Tem Sigla Acadêmica
    if not turma_escolhida:
        for turma in candidatos_validos:
            t_up = turma.upper()
            if t_up.startswith('EI') or t_up.startswith('AI') or t_up.startswith('AF') or t_up.startswith('G'):
                turma_escolhida = turma
                if debug_student_id: print(f"ALUNO {debug_student_id}: Selecionada (PRATA - Sigla): {turma}")
                break
    
    # Bronze (Fallback): Pega a primeira que sobrou
    if not turma_escolhida:
        turma_escolhida = candidatos_validos[0]
        if debug_student_id: print(f"ALUNO {debug_student_id}: Selecionada (BRONZE - Fallback): {turma_escolhida}")

    return turma_escolhida

def search_students(parte_nome, grupo_filtro):
    token = get_sophia_token()
    if not token: return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    params = {"Nome": parte_nome}
    
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
        
        turma_oficial = select_official_class(turmas, prefixo_ignorado, debug_student_id=None)
        
        if not turma_oficial: continue 

        match_ano = re.search(r'(20\d{2})', turma_oficial)
        if match_ano:
            if int(match_ano.group(1)) < ano_vigente: continue

        if grupo_filtro != 'TODOS' and grupo_filtro not in turma_oficial.upper(): continue

        nome_norm = normalize_text(aluno.get("nome"))
        if all(t in nome_norm for t in termos_busca):
            alunos_filtrados[codigo] = {
                "id": codigo,
                "nomeCompleto": aluno.get("nome", "Nome Desconhecido"),
                "turma": turma_oficial,
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
    """Busca por ID (QR Code) - Versão V2: Busca por Lista"""
    print(f"--- INICIANDO BUSCA POR ID (V2): {student_code} ---")
    
    token = get_sophia_token()
    if not token: 
        print("Erro: Sem token Sophia")
        return None

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()

    # ESTRATÉGIA NOVA: Usar o endpoint de Lista filtrando por Código
    # Motivo: O endpoint /alunos/{id} não estava retornando as turmas.
    try:
        url = f"{base_url}/api/v1/alunos"
        params = {'Codigo': student_code} # Tentamos filtrar pelo código na lista
        print(f"Consultando Lista: {url} | Params: {params}")
        
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code != 200:
            print(f"Erro API Sophia: Status {resp.status_code}")
            return None
            
        lista_alunos = resp.json()
    except Exception as e:
        print(f"Exceção na requisição V2: {e}")
        return None

    # Verifica se retornou algo e encontra o aluno certo na lista
    aluno_encontrado = None
    if isinstance(lista_alunos, list):
        for a in lista_alunos:
            # Garante que é o aluno certo (caso a API ignore o filtro e traga todos)
            if str(a.get('codigo')) == str(student_code):
                aluno_encontrado = a
                break
    
    if not aluno_encontrado:
        print(f"Erro: Aluno {student_code} não encontrado na lista retornada.")
        return None

    # Agora extraímos as turmas do objeto "rico"
    turmas = aluno_encontrado.get("turmas", [])
    
    # Debug e Seleção
    turma_oficial = select_official_class(turmas, prefixo_ignorado, debug_student_id=student_code)

    if not turma_oficial:
        print(f"Erro: Aluno {student_code} bloqueado/sem turma válida (mesmo na V2).")
        return None

    # Validação de Ano
    ano_vigente = datetime.now().year
    match_ano = re.search(r'(20\d{2})', turma_oficial)
    if match_ano and int(match_ano.group(1)) < ano_vigente:
        print(f"Erro: Turma antiga detectada ({turma_oficial}).")
        return None

    student_data = {
        "id": str(aluno_encontrado.get("codigo")),
        "nomeCompleto": aluno_encontrado.get("nome", "Nome Desconhecido"),
        "turma": turma_oficial,
        "fotoUrl": None
    }

    try:
        _, foto_base64 = fetch_photo(student_data["id"], headers, base_url)
        if foto_base64:
            student_data["fotoUrl"] = foto_base64
    except Exception:
        pass

    print(f"Sucesso! Retornando aluno: {student_data['nomeCompleto']} - {student_data['turma']}")
    return student_data