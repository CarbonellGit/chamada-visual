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
    nfkd_form = unicodedata.normalize('NFKD', str(text).lower())
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

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

def select_official_class(turmas_raw, ignore_prefix='EM'):
    if not turmas_raw: return None
    blacklist = ['FUTSAL', 'BASQUETE', 'VOLEI', 'HANDEBOL', 'XADREZ', 'JUDO', 'KARATE', 'JIU', 'BALLET', 'JAZZ', 'SAPATEADO', 'TEATRO', 'ROBOTICA', 'INFORMATICA', 'MAKER', 'DANCA', 'CORAL', 'MUSICA', 'VIOLAO', 'TECLADO', 'TREINAMENTO', 'APROFUNDAMENTO', 'MODALIDADE', 'SELECAO', 'MISTO', 'ALMOCO', 'PERIODO', 'EXTRA', 'INTEGRAL', 'CURSO', 'CIRCULO', 'OPCIONAL']
    valid_prefixes = ('EI', 'AI', 'AF', 'G1', 'G2', 'G3', 'G4', 'G5', '1', '2', '3', '4', '5', '6', '7', '8', '9')
    candidatos = []
    for t in turmas_raw:
        desc = t.get("descricao", "").strip()
        if "|" in desc: candidatos.extend([x.strip() for x in desc.split("|") if x.strip()])
        else: candidatos.append(desc)
    regex_ano = re.compile(r'20\d{2}') 
    melhor_turma = None
    for turma in candidatos:
        turma_norm = normalize_text(turma).upper()
        if any(extra in turma_norm for extra in blacklist): continue
        if ignore_prefix:
            prefix_norm = normalize_text(ignore_prefix).upper()
            if turma_norm.startswith(prefix_norm) or f"-{prefix_norm}" in turma_norm or f" {prefix_norm}" in turma_norm: return None 
        if not regex_ano.search(turma): continue
        if melhor_turma:
             if any(turma_norm.startswith(p) for p in valid_prefixes) and not any(normalize_text(melhor_turma).upper().startswith(p) for p in valid_prefixes): melhor_turma = turma
        else: melhor_turma = turma
    return melhor_turma

def search_students(parte_nome, grupo_filtro):
    token = get_sophia_token()
    if not token: return []
    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    ano_atual = datetime.now().year
    params = {"Nome": parte_nome, "AnoLetivo": str(ano_atual), "StatusMatricula": "Matriculado"}
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()

    try:
        resp = requests.get(f"{base_url}/api/v1/alunos", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        raw_students = resp.json()
    except Exception as e:
        logger.error(f"Erro Sophia: {e}")
        return []

    termos_busca = normalize_text(parte_nome).upper().split()
    alunos_filtrados = {}

    for aluno in raw_students:
        codigo = aluno.get("codigo")
        internal_id = aluno.get("id") 
        if not codigo or codigo in alunos_filtrados: continue
        turmas = aluno.get("turmas", [])
        turma_oficial = select_official_class(turmas, prefixo_ignorado)
        if not turma_oficial: continue 
        if grupo_filtro != 'TODOS' and grupo_filtro not in normalize_text(turma_oficial).upper(): continue
        
        nome_norm = normalize_text(aluno.get("nome")).upper()
        if all(t in nome_norm for t in termos_busca):
            final_id = str(internal_id) if internal_id else str(codigo)
            alunos_filtrados[codigo] = {
                "id": final_id,
                "matricula": codigo,
                "nomeCompleto": aluno.get("nome", "Nome Desconhecido"),
                "turma": turma_oficial,
                "fotoUrl": None
            }

    if alunos_filtrados:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(fetch_photo, aid, headers, base_url): aid for aid in alunos_filtrados}
            for future in concurrent.futures.as_completed(futures):
                aid, foto = future.result()
                if foto: alunos_filtrados[aid]['fotoUrl'] = foto

    return list(alunos_filtrados.values())

def get_student_by_code(student_code):
    token = get_sophia_token()
    if not token: return None
    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()
    ano_atual = datetime.now().year
    try:
        url = f"{base_url}/api/v1/alunos"
        params = {'Codigo': student_code, 'AnoLetivo': str(ano_atual)}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200: return None
        lista_alunos = resp.json()
    except Exception: return None

    aluno_encontrado = None
    if isinstance(lista_alunos, list):
        for a in lista_alunos:
            if str(a.get('codigo')) == str(student_code):
                aluno_encontrado = a
                break
    if not aluno_encontrado: return None
    turmas = aluno_encontrado.get("turmas", [])
    turma_oficial = select_official_class(turmas, prefixo_ignorado)
    if not turma_oficial: return None

    internal_id = aluno_encontrado.get("id")
    final_id = str(internal_id) if internal_id else str(student_code)

    student_data = {
        "id": final_id,
        "matricula": str(aluno_encontrado.get("codigo")),
        "nomeCompleto": aluno_encontrado.get("nome", "Nome Desconhecido"),
        "turma": turma_oficial,
        "fotoUrl": None
    }
    try:
        _, foto_base64 = fetch_photo(student_data["id"], headers, base_url)
        if foto_base64: student_data["fotoUrl"] = foto_base64
    except Exception: pass
    return student_data

# --- FUNÇÕES DE RESPONSÁVEIS (CORRIGIDAS) ---

def get_student_responsibles(student_id):
    """
    Busca responsáveis filtrando o próprio aluno e recuperando o ID correto para a foto.
    AGORA ACEITA 'CODIGO' COMO ID SE 'ID' ESTIVER AUSENTE.
    """
    token = get_sophia_token()
    if not token: return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    
    # 1. Busca nome do aluno para filtro
    nome_aluno_norm = ""
    try:
        url_aluno = f"{base_url}/api/v1/Alunos/{student_id}"
        resp_aluno = requests.get(url_aluno, headers=headers, timeout=5)
        if resp_aluno.status_code == 200:
            dados_aluno = resp_aluno.json()
            nome_aluno_norm = normalize_text(dados_aluno.get('nome'))
    except Exception: pass

    # 2. Busca lista de responsáveis
    try:
        url = f"{base_url}/api/v1/alunos/{student_id}/responsaveis"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return []
            
        raw_data = resp.json()
        clean_list = []
        
        for item in raw_data:
            raw_name = item.get('nome')
            pessoa_data = item.get('pessoa')
            if pessoa_data and isinstance(pessoa_data, dict):
                raw_name = pessoa_data.get('nome') or raw_name
            
            nome_resp_norm = normalize_text(raw_name)
            
            # Filtra o próprio aluno
            if nome_aluno_norm and nome_aluno_norm == nome_resp_norm: continue

            # LÓGICA DE RECUPERAÇÃO DE ID (CRUCIAL)
            # Ordem de prioridade: item['id'] -> pessoa['id'] -> item['codigo']
            resp_id = None
            
            # 1. Tenta ID direto
            if item.get('id'):
                resp_id = str(item.get('id'))
            
            # 2. Tenta ID da Pessoa (se o anterior for None)
            if not resp_id and item.get('pessoa', {}).get('id'):
                resp_id = str(item.get('pessoa').get('id'))
                
            # 3. Tenta CODIGO (conforme visto nos logs)
            if not resp_id and item.get('codigo'):
                resp_id = str(item.get('codigo'))
                
            # Se ainda for None, não temos como identificar
            if not resp_id:
                logger.warning(f"Responsável ignorado (sem ID/Código): {raw_name}")
                continue

            # Tratamento do Vínculo
            vinculo_data = item.get('tipoVinculo')
            if vinculo_data and isinstance(vinculo_data, dict):
                vinculo_desc = vinculo_data.get('descricao', 'Outros')
            else:
                vinculo_desc = 'Outros'
            
            clean_list.append({
                "id": resp_id,
                "nome": raw_name, 
                "vinculo": vinculo_desc
            })
            
        return clean_list

    except Exception as e:
        logger.error(f"Exceção responsaveis: {e}")
        return []

def get_responsible_photo_base64(responsible_id):
    """
    Busca foto com Estratégia Dupla:
    1. Tenta endpoint de /responsaveis
    2. Se falhar, tenta endpoint de /pessoas
    """
    token = get_sophia_token()
    if not token: return None

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token}
    
    # TENTATIVA 1: Endpoint de Vínculo/Responsável
    try:
        url = f"{base_url}/api/v1/responsaveis/{responsible_id}/fotos/FotoReduzida"
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if data and 'foto' in data: return data.get('foto')
    except Exception: pass

    # TENTATIVA 2: Endpoint de Pessoa (Fallback)
    try:
        url_pessoa = f"{base_url}/api/v1/pessoas/{responsible_id}/fotos/FotoReduzida"
        resp = requests.get(url_pessoa, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if data and 'foto' in data: return data.get('foto')
    except Exception: pass
    
    return None