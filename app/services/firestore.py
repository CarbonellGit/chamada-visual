from firebase_admin import firestore

def get_db():
    """Retorna o cliente do Firestore de forma segura."""
    try:
        return firestore.client()
    except ValueError:
        return None

def call_student(student_data):
    """
    Registra um aluno na coleção correta do Firestore.
    Retorna True se sucesso, False caso contrário.
    """
    db = get_db()
    if not db:
        print("Erro: Firestore não inicializado.")
        return False

    turma = student_data.get("turma", "").strip().upper()
    
    # Lógica de seleção de coleção baseada na turma
    collection_name = "chamados"
    if turma.startswith('EI'):
        collection_name = "chamados_ei"
    elif 'AI' in turma or 'AF' in turma:
        collection_name = "chamados_fund"

    try:
        # Adiciona timestamp do servidor para consistência
        student_data['timestamp'] = firestore.SERVER_TIMESTAMP
        db.collection(collection_name).add(student_data)
        print(f"Aluno {student_data.get('nomeCompleto')} adicionado em {collection_name}")
        return True
    except Exception as e:
        print(f"Erro ao salvar no Firestore: {e}")
        return False

def clear_all_panels():
    """
    Remove todos os documentos das coleções de chamados.
    Executado pelo backend (Admin SDK), ignorando regras de segurança do cliente.
    """
    db = get_db()
    if not db: return False

    collections_to_clear = ["chamados", "chamados_ei", "chamados_fund"]
    
    try:
        for coll_name in collections_to_clear:
            docs = db.collection(coll_name).stream()
            for doc in docs:
                doc.reference.delete()
        return True
    except Exception as e:
        print(f"Erro ao limpar painéis: {e}")
        return False