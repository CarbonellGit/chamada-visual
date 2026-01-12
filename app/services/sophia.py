import os
import time
import json
import threading
import tempfile
import unicodedata
import re
import requests
import concurrent.futures
from datetime import datetime
from flask import current_app

# Cache do token em arquivo temporário para persistência entre recargas do servidor
TOKEN_CACHE_FILE = os.path.join(tempfile.gettempdir(), 'sophia_token.json')
token_lock = threading.Lock()

def normalize_text(text):
    """Normaliza strings removendo acentos e caracteres especiais."""
    if not text: return ""
    text = str(text).lower()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def get_sophia_token():
    """
    Gerencia a obtenção e renovação do token da API Sophia.
    Usa lock de thread para evitar condições de corrida.
    """
    with token_lock:
        # Tenta recuperar do cache
        try:
            if os.path.exists(TOKEN_CACHE_FILE):
                with open(TOKEN_CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    if time.time() < cache.get('expires_at', 0):
                        return cache.get('token')
        except Exception:
            pass  # Ignora erros de cache e força renovação

        # Se não tem cache válido, solicita novo token
        base_url = current_app.config.get('SOPHIA_BASE_URL')
        if not base_url:
            return None

        try:
            auth_url = f"{base_url}/api/v1/Autenticacao"
            payload = {
                "usuario": current_app.config['SOPHIA_USER'],
                "senha": current_app.config['SOPHIA_PASSWORD']
            }
            response = requests.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            
            new_token = response.text.strip()
            # Cache por 29 minutos
            expires_at = time.time() + (29 * 60)
            
            with open(TOKEN_CACHE_FILE, 'w') as f:
                json.dump({'token': new_token, 'expires_at': expires_at}, f)
                
            return new_token
        except Exception as e:
            print(f"Erro ao obter token Sophia: {e}")
            return None

def fetch_photo(aluno_id, headers, base_url):
    """
    Busca foto do aluno. Função auxiliar para execução paralela.
    Recebe base_url como argumento para evitar erro de contexto fora da thread principal.
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
    Realiza a busca de alunos aplicando regras de negócio:
    - Filtra por nome (mínimo 2 chars)
    - Filtra formandos de anos anteriores
    - Filtra Ensino Médio (se necessário)
    - Busca fotos em paralelo
    """
    token = get_sophia_token()
    if not token:
        raise ConnectionError("Falha na autenticação com Sophia")

    # Extraímos a URL aqui, dentro do contexto da aplicação (Thread Principal)
    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    
    # Busca na API
    resp = requests.get(f"{base_url}/api/v1/alunos", headers=headers, params={"Nome": parte_nome}, timeout=15)
    resp.raise_for_status()
    raw_students = resp.json()

    # Processamento e Filtragem
    ano_vigente = datetime.now().year
    termos_busca = normalize_text(parte_nome).split()
    alunos_filtrados = {}

    for aluno in raw_students:
        codigo = aluno.get("codigo")
        if not codigo or codigo in alunos_filtrados: continue

        # Validação de Turma
        turmas = aluno.get("turmas", [])
        if not turmas: continue
        turma_desc = turmas[0].get("descricao", "")
        
        # Filtro de Ano (Ex: remove formados em 2024 se estamos em 2025)
        match_ano = re.search(r'(\d{4})', turma_desc)
        if match_ano and int(match_ano.group(1)) < ano_vigente:
            continue

        # Filtro de Ensino Médio
        if turma_desc.upper().startswith('EM'):
            continue

        # Filtro de Grupo (EI, AI, AF)
        if grupo_filtro != 'TODOS' and grupo_filtro not in turma_desc.upper():
            continue

        # Match do Nome
        nome_norm = normalize_text(aluno.get("nome"))
        if all(t in nome_norm for t in termos_busca):
            alunos_filtrados[codigo] = {
                "id": codigo,
                "nomeCompleto": aluno.get("nome", "Nome Desconhecido"),
                "turma": turma_desc,
                "fotoUrl": None # Será preenchido depois
            }

    # Busca de fotos em paralelo (Otimização de performance)
    if alunos_filtrados:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Passamos 'base_url' explicitamente para a função da thread
            futures = {executor.submit(fetch_photo, aid, headers, base_url): aid for aid in alunos_filtrados}
            for future in concurrent.futures.as_completed(futures):
                aid, foto = future.result()
                if foto:
                    alunos_filtrados[aid]['fotoUrl'] = foto

    return list(alunos_filtrados.values())