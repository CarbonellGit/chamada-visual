import logging
from firebase_admin import firestore
from flask import current_app

# Configura o logger específico para este módulo
logger = logging.getLogger(__name__)

def get_db():
    """
    Retorna o cliente do Firestore.
    Tenta pegar do contexto da aplicação (app.db) se disponível.
    """
    try:
        # Se estivermos dentro de um contexto de requisição Flask
        if current_app:
            return getattr(current_app, 'db', firestore.client())
        return firestore.client()
    except Exception as e:
        logger.error(f"Erro ao obter cliente Firestore: {e}")
        return None

def call_student(student_data):
    """
    Registra um aluno na coleção correta do Firestore.
    """
    db = get_db()
    if not db:
        logger.error("Tentativa de chamar aluno falhou: Firestore não inicializado.")
        return False

    turma = student_data.get("turma", "").strip().upper()
    
    collection_name = "chamados"
    if turma.startswith('EI'):
        collection_name = "chamados_ei"
    elif 'AI' in turma or 'AF' in turma:
        collection_name = "chamados_fund"

    try:
        student_data['timestamp'] = firestore.SERVER_TIMESTAMP
        db.collection(collection_name).add(student_data)
        logger.info(f"Aluno {student_data.get('nomeCompleto')} adicionado com sucesso em {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar no Firestore: {e}")
        return False

def clear_all_panels():
    """
    Remove todos os documentos das coleções de chamados.
    """
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