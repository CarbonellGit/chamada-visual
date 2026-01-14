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
    Remove acentos e caracteres especiais.
    Ex: 'VÔLEI' -> 'VOLEI'
    """
    if not text: return ""
    text = str(text)
    normalized = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return normalized.upper()

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
    Seleciona a turma OFICIAL.
    CRITÉRIO RIGOROSO: Deve conter o Ano (20xx) na descrição (padrão Carbonell ex: AI-2A-T-2036).
    Se não tiver ano, a turma é descartada.
    """
    if not turmas_raw:
        if debug_student_id: print(f"ALUNO {debug_student_id}: Sem turmas.")
        return None

    # BLACKLIST
    blacklist = [
        'FUTSAL', 'BASQUETE', 'VOLEI', 'HANDEBOL', 'XADREZ', 'JUDO', 'KARATE', 'JIU', 
        'BALLET', 'JAZZ', 'SAPATEADO', 'TEATRO', 'ROBOTICA', 'INFORMATICA', 'MAKER',
        'DANCA', 'CORAL', 'MUSICA', 'VIOLAO', 'TECLADO',
        'TREINAMENTO', 'APROFUNDAMENTO', 'MODALIDADE', 'SELECAO', 'MISTO', 
        'ALMOCO', 'PERIODO', 'EXTRA', 'INTEGRAL', 'CURSO', 'CIRCULO', 'OPCIONAL'
    ]
    
    valid_prefixes = ('EI', 'AI', 'AF', 'G1', 'G2', 'G3', 'G4', 'G5', '1', '2', '3', '4', '5', '6', '7', '8', '9')

    candidatos = []
    for t in turmas_raw:
        desc = t.get("descricao", "").strip()
        if "|" in desc:
            candidatos.extend([x.strip() for x in desc.split("|") if x.strip()])
        else:
            candidatos.append(desc)

    # Regex Obrigatório: Ano (20xx)
    regex_ano = re.compile(r'20\d{2}') 
    
    melhor_turma = None
    
    for turma in candidatos:
        turma_norm = normalize_text(turma)

        # 1. Filtro Blacklist
        if any(extra in turma_norm for extra in blacklist):
            continue

        # 2. Filtro EM
        if ignore_prefix:
            prefix_norm = normalize_text(ignore_prefix)
            if turma_norm.startswith(prefix_norm) or f"-{prefix_norm}" in turma_norm or f" {prefix_norm}" in turma_norm:
                return None 

        # 3. CRITÉRIO OBRIGATÓRIO: Tem que ter Ano (20xx)
        if not regex_ano.search(turma):
            continue

        # 4. Seleção da melhor opção
        if melhor_turma:
             if any(turma_norm.startswith(p) for p in valid_prefixes) and not any(normalize_text(melhor_turma).startswith(p) for p in valid_prefixes):
                 melhor_turma = turma
        else:
            melhor_turma = turma

    return melhor_turma

def search_students(parte_nome, grupo_filtro):
    token = get_sophia_token()
    if not token: return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    
    # --- NOVIDADE: FILTRO DE ANO LETIVO ---
    # Força a API a trazer dados do ano corrente
    ano_atual = datetime.now().year
    
    params = {
        "Nome": parte_nome,
        "AnoLetivo": str(ano_atual),
        "StatusMatricula": "Matriculado" # Tenta filtrar apenas ativos
    }
    
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

        if grupo_filtro != 'TODOS' and grupo_filtro not in normalize_text(turma_oficial): continue

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
    """Busca por ID (V2 - via Lista com Filtro de Ano)"""
    print(f"--- INICIANDO BUSCA POR ID (V2): {student_code} ---")
    
    token = get_sophia_token()
    if not token: 
        print("Erro: Sem token Sophia")
        return None

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    prefixo_ignorado = current_app.config.get('IGNORE_CLASS_PREFIX', 'EM').upper()

    # --- NOVIDADE: FILTRO DE ANO LETIVO ---
    ano_atual = datetime.now().year

    try:
        url = f"{base_url}/api/v1/alunos"
        params = {
            'Codigo': student_code,
            'AnoLetivo': str(ano_atual) # Fundamental para não pegar histórico
        }
        print(f"Consultando Lista: {url} | Params: {params}")
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code != 200:
            print(f"Erro API Sophia: Status {resp.status_code}")
            return None
        lista_alunos = resp.json()
    except Exception as e:
        print(f"Exceção na requisição V2: {e}")
        return None

    aluno_encontrado = None
    if isinstance(lista_alunos, list):
        for a in lista_alunos:
            if str(a.get('codigo')) == str(student_code):
                aluno_encontrado = a
                break
    
    if not aluno_encontrado:
        print(f"Erro: Aluno {student_code} não encontrado no Ano Letivo {ano_atual}.")
        return None

    turmas = aluno_encontrado.get("turmas", [])
    
    turma_oficial = select_official_class(turmas, prefixo_ignorado, debug_student_id=student_code)

    if not turma_oficial:
        print(f"Erro: Aluno {student_code} bloqueado/sem turma padrão válida.")
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

def get_student_responsibles(student_id):
    """
    Busca a lista de responsáveis/autorizados de um aluno.
    Retorna uma lista de dicionários com id, nome, vinculo e autorização.
    """
    token = get_sophia_token()
    if not token: 
        return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    
    try:
        # Endpoint identificado na análise do sistema de referência
        url = f"{base_url}/api/v1/alunos/{student_id}/responsaveis"
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            logger.error(f"Erro ao buscar responsáveis do aluno {student_id}: {resp.status_code}")
            return []
            
        raw_data = resp.json()
        clean_list = []
        
        for item in raw_data:
            # Extrai apenas o necessário
            vinculo_desc = item.get('tipoVinculo', {}).get('descricao', 'Outros')
            
            clean_list.append({
                "id": str(item.get("id")),
                "nome": normalize_text(item.get("nome")),
                "vinculo": vinculo_desc,
                "autorizado": item.get("retiradaAutorizada", False)
            })
            
        return clean_list

    except Exception as e:
        logger.error(f"Exceção ao buscar responsáveis: {e}")
        return []

def get_responsible_photo_base64(responsible_id):
    """
    Busca a foto reduzida de um responsável e retorna a string base64 pura.
    Usado pela rota proxy.
    """
    token = get_sophia_token()
    if not token: return None

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token}
    
    try:
        url = f"{base_url}/api/v1/responsaveis/{responsible_id}/fotos/FotoReduzida"
        resp = requests.get(url, headers=headers, timeout=5)
        
        if resp.status_code == 200 and resp.text:
            data = resp.json()
            # O campo 'foto' vem no formato "data:image/jpeg;base64,..."
            # Se vier completo, retornamos direto. Se vier só o b64, ajustamos no proxy.
            return data.get('foto')
            
    except Exception as e:
        logger.error(f"Erro foto responsável {responsible_id}: {e}")
    
    return None