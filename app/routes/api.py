import logging
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

@bp.route('/buscar-aluno', methods=['GET'])
@login_required
def buscar_aluno():
    parte_nome = request.args.get('parteNome', '').strip()
    grupo = request.args.get('grupo', 'todos').upper()
    
    if len(parte_nome) < 2:
        return jsonify([])

    try:
        alunos = sophia.search_students(parte_nome, grupo)
        return jsonify(alunos)
    except Exception as e:
        logger.error(f"Exceção não tratada na busca: {e}")
        return jsonify({"erro": "Erro interno ao buscar alunos"}), 500

@bp.route('/chamar-aluno', methods=['POST'])
@login_required
def chamar_aluno():
    data = request.get_json()
    if not data:
        logger.warning("Tentativa de chamada com dados inválidos.")
        return jsonify({"erro": "Dados inválidos"}), 400
        
    sucesso = firestore.call_student(data)
    if sucesso:
        return jsonify({"sucesso": True})
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