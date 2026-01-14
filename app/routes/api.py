import logging
import concurrent.futures
from flask import Blueprint, request, jsonify, session
from app.services import sophia, firestore
from functools import wraps

# Configura Logger
logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__, url_prefix='/api')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"erro": "Não autorizado"}), 401
        return f(*args, **kwargs)
    return decorated_function

def enrich_with_call_count(aluno):
    """Função auxiliar para injetar a contagem de chamadas no objeto aluno."""
    try:
        count = firestore.get_student_call_count(aluno['id'], aluno['turma'])
        aluno['chamados_hoje'] = count
    except Exception as e:
        logger.error(f"Erro ao contar chamadas: {e}")
        aluno['chamados_hoje'] = 0
    return aluno

@bp.route('/buscar-aluno', methods=['GET'])
@login_required
def buscar_aluno():
    parte_nome = request.args.get('parteNome', '').strip()
    grupo = request.args.get('grupo', 'todos').upper()
    
    if len(parte_nome) < 2:
        return jsonify([])

    try:
        # 1. Busca no Sophia (já vem com fotos)
        alunos = sophia.search_students(parte_nome, grupo)
        
        # 2. Enriquece com contagem do Firestore (Paralelismo para performance)
        if alunos:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Mapeia a execução da função de contagem para cada aluno
                list(executor.map(enrich_with_call_count, alunos))

        return jsonify(alunos)
    except Exception as e:
        logger.error(f"Exceção na busca: {e}")
        return jsonify({"erro": "Erro interno ao buscar alunos"}), 500

@bp.route('/buscar-por-id', methods=['GET'])
@login_required
def buscar_por_id():
    student_code = request.args.get('codigo', '').strip()
    
    if not student_code:
        return jsonify({"erro": "Código não fornecido"}), 400

    try:
        # 1. Busca no Sophia
        aluno = sophia.get_student_by_code(student_code)
        
        if aluno:
            # 2. Enriquece com contagem (sem thread pool pois é só 1)
            enrich_with_call_count(aluno)
            return jsonify(aluno)
        else:
            return jsonify({"erro": "Aluno não encontrado"}), 404
            
    except Exception as e:
        logger.error(f"Erro busca ID: {e}")
        return jsonify({"erro": "Erro interno"}), 500

@bp.route('/chamar-aluno', methods=['POST'])
@login_required
def chamar_aluno():
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Dados inválidos"}), 400
        
    sucesso = firestore.call_student(data)
    if sucesso:
        # Retorna a nova contagem para atualizar o frontend imediatamente
        nova_contagem = firestore.get_student_call_count(data.get('id'), data.get('turma'))
        return jsonify({"sucesso": True, "nova_contagem": nova_contagem})
    else:
        return jsonify({"erro": "Falha ao registrar chamada"}), 500

@bp.route('/limpar-paineis', methods=['POST'])
@login_required
def limpar_paineis():
    sucesso = firestore.clear_all_panels()
    if sucesso:
        return jsonify({"sucesso": True})
    else:
        return jsonify({"erro": "Falha ao limpar painéis"}), 500