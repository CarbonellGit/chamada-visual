import os
import time
import threading
import unicodedata
import re
import requests
import concurrent.futures
from datetime import datetime
from flask import current_app
from firebase_admin import firestore

# Lock para evitar que múltiplas threads na mesma instância tentem renovar o token simultaneamente
token_lock = threading.Lock()

def normalize_text(text):
    """Normaliza strings removendo acentos e caracteres especiais."""
    if not text: return ""
    text = str(text).lower()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def get_db():
    """Retorna o cliente do Firestore."""
    try:
        return firestore.client()
    except ValueError:
        return None

def get_sophia_token():
    """
    Gerencia a obtenção e renovação do token da API Sophia usando o Firestore como cache centralizado.
    """
    with token_lock:
        db = get_db()
        if not db:
            print("Erro: Firestore não disponível para recuperar token.")
            return None

        doc_ref = db.collection('system_config').document('sophia_token')

        # 1. Tenta recuperar do Firestore
        try:
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                # Verifica se o token ainda é válido (com margem de segurança de 30s)
                if time.time() < data.get('expires_at', 0) - 30:
                    return data.get('token')
        except Exception as e:
            print(f"Aviso: Erro ao ler token do Firestore: {e}")

        # 2. Se não tem cache válido, solicita novo token à API Sophia
        base_url = current_app.config.get('SOPHIA_BASE_URL')
        if not base_url:
            return None

        try:
            print("Renovando token da API Sophia...")
            auth_url = f"{base_url}/api/v1/Autenticacao"
            payload = {
                "usuario": current_app.config['SOPHIA_USER'],
                "senha": current_app.config['SOPHIA_PASSWORD']
            }
            response = requests.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            
            new_token = response.text.strip()
            # O token do Sophia dura 30 minutos, renovamos com folga
            expires_at = time.time() + (29 * 60)
            
            # 3. Salva o novo token no Firestore
            doc_ref.set({
                'token': new_token,
                'expires_at': expires_at,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
                
            return new_token
        except Exception as e:
            print(f"Erro crítico ao obter novo token Sophia: {e}")
            return None

def fetch_photo(aluno_id, headers, base_url):
    """
    Busca foto do aluno. Função auxiliar para execução paralela.
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
    Realiza a busca de alunos aplicando regras de negócio.
    """
    token = get_sophia_token()
    if not token:
        # Retorna lista vazia ou levanta erro, dependendo da estratégia de UI.
        # Aqui, logamos e retornamos vazio para não quebrar o frontend.
        print("Abortando busca: Falha na autenticação com Sophia.")
        return []

    base_url = current_app.config.get('SOPHIA_BASE_URL')
    headers = {'token': token, 'Accept': 'application/json'}
    
    try:
        # Busca na API
        resp = requests.get(f"{base_url}/api/v1/alunos", headers=headers, params={"Nome": parte_nome}, timeout=15)
        resp.raise_for_status()
        raw_students = resp.json()
    except Exception as e:
        print(f"Erro na requisição ao Sophia: {e}")
        return []

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

    # Busca de fotos em paralelo
    if alunos_filtrados:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(fetch_photo, aid, headers, base_url): aid for aid in alunos_filtrados}
            for future in concurrent.futures.as_completed(futures):
                aid, foto = future.result()
                if foto:
                    alunos_filtrados[aid]['fotoUrl'] = foto

    return list(alunos_filtrados.values())