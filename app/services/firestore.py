import logging
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
    if not turma: return "chamados"
    turma = turma.strip().upper()
    if turma.startswith('EI') or turma.startswith('G'):
        return "chamados_ei"
    elif 'AI' in turma or 'AF' in turma:
        return "chamados_fund"
    return "chamados"

def call_student(student_data):
    db = get_db()
    if not db: return False

    turma = student_data.get("turma", "")
    collection_name = _get_collection_name(turma)

    try:
        # GARANTIA DE TIPAGEM: Força ID como string para evitar divergência no banco
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
    
    # GARANTIA DE TIPAGEM: Busca sempre como string
    target_id = str(student_id)

    try:
        # Busca documentos onde o campo 'id' é igual ao target_id
        docs = db.collection(collection_name).where("id", "==", target_id).stream()
        
        count = 0
        total_found = 0
        
        for doc in docs:
            data = doc.to_dict()
            total_found += 1
            
            # Verifica data (String ou Timestamp)
            doc_date = data.get('data_chamada')
            is_today = False
            
            if doc_date == today_str:
                is_today = True
            elif not doc_date:
                # Fallback para registros antigos sem data_chamada
                ts = data.get('timestamp')
                if ts:
                    try:
                        # Verifica se o timestamp é de hoje (ignorando hora)
                        ts_val = ts.date() if hasattr(ts, 'date') else ts.today().date()
                        if ts_val == datetime.now().date():
                            is_today = True
                    except:
                        pass
            
            if is_today:
                count += 1
        
        # LOG DE DIAGNÓSTICO (Aparecerá no seu terminal)
        # Se total_found > 0 mas count == 0, o problema é a data.
        # Se total_found == 0, o problema é o ID ou a Coleção.
        if total_found > 0 or count > 0:
            logger.info(f"CONTAGEM ID {target_id} em '{collection_name}': Encontrados={total_found}, Hoje={count}")
            
        return count
    except Exception as e:
        logger.error(f"Erro ao contar chamadas para {student_id}: {e}")
        return 0

def clear_all_panels():
    db = get_db()
    if not db: return False

    collections_to_clear = ["chamados", "chamados_ei", "chamados_fund"]
    
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