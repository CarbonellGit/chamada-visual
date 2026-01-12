import logging
from firebase_admin import firestore
from flask import current_app

# Configura o logger específico para este módulo
logger = logging.getLogger(__name__)

def get_db():
    """
    Recupera a instância do cliente Firestore ativa.
    
    Tenta obter o cliente do contexto global da aplicação Flask (`current_app.db`).
    Se não estiver em um contexto de app (ex: script isolado), cria uma nova instância.

    Returns:
        google.cloud.firestore.Client | None: Cliente do Firestore ou None em caso de erro.
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
    Registra a solicitação de chamada de um aluno na coleção apropriada do Firestore.

    A função determina a coleção de destino com base na turma do aluno:
    - Turmas iniciando com 'EI' -> `chamados_ei` (Educação Infantil)
    - Turmas contendo 'AI' ou 'AF' -> `chamados_fund` (Ensino Fundamental)
    - Outros -> `chamados` (Padrão)

    Args:
        student_data (dict): Dicionário contendo os dados do aluno (nome, turma, foto, etc).

    Returns:
        bool: True se o registro foi salvo com sucesso, False caso contrário.
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
    Limpa todos os registros de chamados ativos em todas as coleções do sistema.

    Itera sobre as coleções `chamados`, `chamados_ei` e `chamados_fund`,
    deletando documento por documento.
    
    Atenção: Esta é uma operação destrutiva e irreversível.

    Returns:
        bool: True se a limpeza foi completa, False se houver erro.
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