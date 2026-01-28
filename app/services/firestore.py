import logging
import re
from datetime import datetime, time
from firebase_admin import firestore
from flask import current_app

logger = logging.getLogger(__name__)

def get_db():
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
    """
    if not turma: return "chamados"
    
    turma = turma.strip().upper()
    
    # LOG DE DIAGNÓSTICO
    logger.info(f"--> CLASSIFICANDO TURMA: '{turma}'")
    
    # 1. Regra para Educação Infantil (EI e G1-G5)
    # Ex: 'EI-4B-T-2039', 'G4 A'
    if turma.startswith('EI') or turma.startswith('G'):
        return "chamados_ei"
    
    # 2. Regra Específica para 1ºs Anos (1A, 1B, 1C...)
    # Regex Explicado:
    # (?:^|[\s\-])  : O início deve ser o começo da linha (^) OU um separador (espaço ou traço).
    #                 Isso permite casar 'AI-1A' (por causa do traço) ou '1A' direto.
    # 1             : O número 1 literal.
    # [\sº°\-]?     : Um separador opcional (ex: '1-A', '1ºA', '1A').
    # [A-Z]         : A letra da turma.
    # (?![0-9])     : Lookahead negativo: garante que o próximo char NÃO é número (evita 10, 11).
    
    # Testes Mentais:
    # 'AI-1A-M' -> Casa (devido ao traço antes do 1)
    # '1B'      -> Casa (início de string)
    # 'AI-2A'   -> Não casa
    # '11A'     -> Não casa (separador previne início, lookahead previne fim)
    
    if re.search(r'(?:^|[\s\-])1[\sº°\-]?[A-Z](?![0-9])', turma):
        logger.info(f"--> Destino Definido: CHAMADOS_1ANO")
        return "chamados_1ano"

    # 3. Regra para Fundamental (Anos Iniciais e Finais - exceto 1º ano)
    logger.info(f"--> Destino Definido: CHAMADOS_FUND (Padrão)")
    return "chamados_fund"

def call_student(student_data):
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
    Conta chamadas de hoje com logs de diagnóstico.
    """
    db = get_db()
    if not db: return 0

    collection_name = _get_collection_name(turma)
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_id = str(student_id)

    try:
        docs = db.collection(collection_name).where("id", "==", target_id).stream()
        
        count = 0
        total_found = 0
        
        for doc in docs:
            data = doc.to_dict()
            total_found += 1
            
            doc_date = data.get('data_chamada')
            is_today = False
            
            if doc_date == today_str:
                is_today = True
            elif not doc_date:
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
        
        if total_found > 0 or count > 0:
            logger.info(f"CONTAGEM ID {target_id} em '{collection_name}': Encontrados={total_found}, Hoje={count}")
            
        return count
    except Exception as e:
        logger.error(f"Erro ao contar chamadas para {student_id}: {e}")
        return 0

def clear_all_panels():
    db = get_db()
    if not db: return False

    collections_to_clear = ["chamados", "chamados_ei", "chamados_fund", "chamados_1ano"]
    
    try:
        for coll_name in collections_to_clear:
            docs = db.collection(coll_name).stream()
            for doc in docs:
                doc.reference.delete()
        logger.info("Todos os painéis foram limpos com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao limpar painéis: {e}")
        return False