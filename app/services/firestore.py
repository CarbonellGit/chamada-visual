import logging
from datetime import datetime, time
from firebase_admin import firestore
from flask import current_app

logger = logging.getLogger(__name__)

def get_db():
    """
    Obtém a instância do cliente Firestore.

    Returns:
        google.cloud.firestore.Client: Cliente autenticado do Firestore ou None em caso de erro.
    """
    try:
        if current_app:
            return getattr(current_app, 'db', firestore.client())
        return firestore.client()
    except Exception as e:
        logger.error(f"Erro ao obter cliente Firestore: {e}")
        return None

def _get_collection_name(turma):
    """
    Determina a coleção do Firestore baseada no nome da turma.
    
    Regras de Negócio:
    1. EI ou G* -> chamados_ei (Educação Infantil)
    2. 1* (ex: 1A, 1B, 1C) -> chamados_1ano (Primeiros Anos)
    3. AI ou AF ou outros -> chamados_fund (Fundamental Geral)

    Args:
        turma (str): Nome da turma (ex: '1A', '3B', 'G4').

    Returns:
        str: Nome da coleção de destino.
    """
    if not turma: 
        return "chamados"
    
    turma = turma.strip().upper()
    
    # 1. Regra para Educação Infantil (EI e G1-G5)
    if turma.startswith('EI') or turma.startswith('G'):
        return "chamados_ei"
    
    # 2. Regra Específica para 1ºs Anos (1A, 1B, 1C)
    # Verifica se começa com '1' e o segundo caractere NÃO é um número (para evitar 10, 11, 12 do Médio)
    # Exemplo: '1A' (Passa), '10A' (Falha), '1B' (Passa)
    if turma.startswith('1') and len(turma) > 1 and not turma[1].isdigit():
        return "chamados_1ano"

    # 3. Regra para Fundamental (Anos Iniciais e Finais - exceto 1º ano)
    # Mantemos 'AI' e 'AF' ou qualquer outro caso residual que não seja EI ou 1º ano
    return "chamados_fund"

def call_student(student_data):
    """
    Registra uma nova chamada para um aluno no Firestore.

    Args:
        student_data (dict): Dicionário contendo dados do aluno (id, nome, turma, etc).

    Returns:
        bool: True se gravado com sucesso, False caso contrário.
    """
    db = get_db()
    if not db: return False

    turma = student_data.get("turma", "")
    collection_name = _get_collection_name(turma)

    try:
        # GARANTIA DE TIPAGEM: Força ID como string
        if 'id' in student_data:
            student_data['id'] = str(student_data['id'])

        # Dados de controle temporal
        student_data['timestamp'] = firestore.SERVER_TIMESTAMP
        student_data['data_chamada'] = datetime.now().strftime("%Y-%m-%d")
        
        db.collection(collection_name).add(student_data)
        logger.info(f"GRAVAÇÃO SUCESSO: Aluno {student_data.get('id')} - {student_data.get('nomeCompleto')} em '{collection_name}'")
        return True
    except Exception as e:
        logger.error(f"ERRO GRAVAÇÃO: {e}")
        return False

def get_student_call_count(student_id, turma):
    """
    Conta quantas vezes o aluno foi chamado hoje na coleção correta.

    Args:
        student_id (str): ID único do aluno.
        turma (str): Turma do aluno (usada para determinar a coleção).

    Returns:
        int: Número de chamadas encontradas hoje.
    """
    db = get_db()
    if not db: return 0

    collection_name = _get_collection_name(turma)
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_id = str(student_id)

    try:
        docs = db.collection(collection_name).where("id", "==", target_id).stream()
        
        count = 0
        
        for doc in docs:
            data = doc.to_dict()
            
            # Verifica data (String ou Timestamp)
            doc_date = data.get('data_chamada')
            is_today = False
            
            if doc_date == today_str:
                is_today = True
            elif not doc_date:
                # Fallback para registros antigos
                ts = data.get('timestamp')
                if ts:
                    try:
                        ts_val = ts.date() if hasattr(ts, 'date') else ts.today().date()
                        if ts_val == datetime.now().date():
                            is_today = True
                    except:
                        pass
            
            if is_today:
                count += 1
            
        return count
    except Exception as e:
        logger.error(f"Erro ao contar chamadas para {student_id}: {e}")
        return 0

def clear_all_panels():
    """
    Limpa TODAS as coleções de painéis manualmente.
    Atualizado para incluir 'chamados_1ano'.

    Returns:
        bool: True se sucesso.
    """
    db = get_db()
    if not db: return False

    # LISTA ATUALIZADA DE COLEÇÕES
    collections_to_clear = ["chamados", "chamados_ei", "chamados_fund", "chamados_1ano"]
    
    try:
        for coll_name in collections_to_clear:
            docs = db.collection(coll_name).stream()
            for doc in docs:
                doc.reference.delete()
        logger.info("Todos os painéis (incluindo 1º anos) foram limpos com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao limpar painéis: {e}")
        return False