import logging
from datetime import datetime, time
from firebase_admin import firestore
from flask import current_app

# Configura o logger específico para este módulo
logger = logging.getLogger(__name__)

def get_db():
    """
    Recupera a instância do cliente Firestore ativa.
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
    Define a coleção baseada na turma (Lógica centralizada).
    """
    turma = turma.strip().upper()
    if turma.startswith('EI') or turma.startswith('G'): # G para G1, G2... se houver
        return "chamados_ei"
    elif 'AI' in turma or 'AF' in turma:
        return "chamados_fund"
    return "chamados"

def call_student(student_data):
    """
    Registra a solicitação de chamada de um aluno.
    """
    db = get_db()
    if not db:
        logger.error("Tentativa de chamar aluno falhou: Firestore não inicializado.")
        return False

    turma = student_data.get("turma", "")
    collection_name = _get_collection_name(turma)

    try:
        # Adiciona timestamp do servidor
        student_data['timestamp'] = firestore.SERVER_TIMESTAMP
        # Adiciona data legível para facilitar auditoria futura (opcional, mas útil)
        student_data['data_chamada'] = datetime.now().strftime("%Y-%m-%d")
        
        db.collection(collection_name).add(student_data)
        logger.info(f"Aluno {student_data.get('nomeCompleto')} adicionado em {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar no Firestore: {e}")
        return False

def get_student_call_count(student_id, turma):
    """
    Conta quantas vezes o aluno foi chamado HOJE.
    
    Args:
        student_id (str): ID do aluno.
        turma (str): Turma do aluno (para saber qual coleção consultar).
        
    Returns:
        int: Número de chamadas realizadas hoje.
    """
    db = get_db()
    if not db: return 0

    collection_name = _get_collection_name(turma)
    
    # Define o início do dia atual (00:00:00)
    now = datetime.now()
    start_of_day = datetime.combine(now.date(), time.min)

    try:
        # Consulta: Onde ID é igual E timestamp é maior que hoje 00:00
        # Nota: O Firestore exige índice composto para consultas com filtro de igualdade + desigualdade.
        # Se der erro de índice, o link para criar aparecerá no log do console.
        # Alternativa simples sem índice: Filtrar apenas por data_chamada (string) se criado acima,
        # ou filtrar no código se o volume for baixo. 
        # Vamos tentar a query direta pelo ID e filtrar em memória os de hoje (mais seguro sem criar indices complexos agora).
        
        docs = db.collection(collection_name).where("id", "==", str(student_id)).stream()
        
        count = 0
        for doc in docs:
            data = doc.to_dict()
            # Verifica se o timestamp é de hoje
            # O timestamp do Firestore vem como objeto datetime com timezone ou similar
            ts = data.get('timestamp')
            if ts:
                # Se for datetime, compara. Se for server_timestamp pendente, assume agora.
                try:
                    # Converte para naive datetime para comparação simples ou compara date()
                    ts_date = ts.date() if hasattr(ts, 'date') else ts.today().date()
                    if ts_date == now.date():
                        count += 1
                except:
                    pass
                    
        return count
    except Exception as e:
        logger.error(f"Erro ao contar chamadas para {student_id}: {e}")
        return 0

def clear_all_panels():
    """
    Limpa todos os registros de chamados ativos.
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