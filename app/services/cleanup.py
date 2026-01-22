import time
import threading
import logging
from datetime import datetime, timedelta, timezone
from firebase_admin import firestore
from flask import current_app

# Configura logger
logger = logging.getLogger(__name__)

# Configuração
CLEANUP_INTERVAL_SECONDS = 60  # Verifica a cada 1 minuto
MAX_AGE_MINUTES = 10           # Tempo máximo de vida de um chamado

def get_db():
    """Obtém instância do Firestore (funciona fora do contexto Flask)."""
    try:
        return firestore.client()
    except Exception as e:
        logger.error(f"Erro ao obter cliente Firestore no cleanup: {e}")
        return None

def delete_old_records():
    """
    Varre as coleções e deleta documentos mais antigos que MAX_AGE_MINUTES.
    OTIMIZAÇÃO: Usa query do Firestore (.where) para baixar APENAS os documentos expirados.
    Isso economiza custos de leitura (Read Ops).
    """
    db = get_db()
    if not db: return

    collections = ["chamados", "chamados_ei", "chamados_fund"]
    
    # Define o tempo de corte (agora - 10 minutos)
    # Usamos timezone UTC pois o Firestore armazena datas em UTC
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=MAX_AGE_MINUTES)
    
    total_deleted = 0

    for collection_name in collections:
        try:
            # --- OTIMIZAÇÃO DE CUSTO AQUI ---
            # Antes: db.collection(collection_name).stream() -> Baixava TUDO (Caro!)
            # Agora: Filtramos no servidor do Google. Só baixamos o que vai ser deletado.
            docs = db.collection(collection_name)\
                     .where("timestamp", "<", cutoff_time)\
                     .stream()
            
            batch = db.batch()
            batch_count = 0
            
            for doc in docs:
                # Como a query já filtrou, tudo que vem aqui é para deletar
                batch.delete(doc.reference)
                batch_count += 1
                total_deleted += 1

                # Firestore tem limite de 500 operações por batch.
                # Se acumular muito, comitamos e abrimos um novo.
                if batch_count >= 400:
                    batch.commit()
                    batch = db.batch()
                    batch_count = 0

            # Comita o restante
            if batch_count > 0:
                batch.commit()
                logger.info(f"LIMPEZA: {batch_count + (total_deleted - batch_count)} chamados expirados removidos de '{collection_name}'.")

        except Exception as e:
            logger.error(f"Erro ao limpar coleção '{collection_name}': {e}")

    if total_deleted > 0:
        logger.info(f"--- Ciclo de Limpeza Concluído: {total_deleted} registros removidos no total ---")

def _cleanup_loop():
    """Loop infinito que roda em background."""
    logger.info("Serviço de Limpeza Automática (Garbage Collector) INICIADO.")
    while True:
        try:
            delete_old_records()
        except Exception as e:
            logger.error(f"Erro fatal no loop de limpeza: {e}")
        
        # Aguarda X segundos antes da próxima verificação
        time.sleep(CLEANUP_INTERVAL_SECONDS)

def start_background_cleanup():
    """
    Inicia a thread de limpeza em background (Daemon).
    Deve ser chamado no run.py.
    """
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    cleanup_thread.start()