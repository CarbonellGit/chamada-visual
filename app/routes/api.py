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
    """
    Endpoint para buscar alunos na base do Sophia.
    
    Query Params:
        parteNome (str): Parte do nome para busca. Mínimo 2 caracteres.
        grupo (str): Filtro de grupo ('todos' por padrão).

    Returns:
        JSON: Lista de alunos encontrados ou lista vazia.
    """
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

@bp.route('/buscar-por-id', methods=['GET'])
@login_required
def buscar_por_id():
    """
    Endpoint para buscar dados detalhados de um aluno específico pelo seu código (ID).
    
    Utilizado pela funcionalidade de leitura de QR Code.
    
    Query Params:
        codigo (str): O código do aluno a ser buscado.

    Returns:
        JSON: Objeto com dados do aluno se encontrado, ou erro 404/400.
    """
    student_code = request.args.get('codigo', '').strip()
    
    if not student_code:
        return jsonify({"erro": "Código do aluno não fornecido."}), 400

    try:
        # Chama o serviço recém-criado
        aluno = sophia.get_student_by_code(student_code)
        
        if aluno:
            return jsonify(aluno)
        else:
            # Retorna 404 para que o frontend saiba que o QR é inválido ou aluno não elegível
            return jsonify({"erro": "Aluno não encontrado ou não elegível para chamada."}), 404
            
    except Exception as e:
        logger.error(f"Erro interno na busca por ID: {e}")
        return jsonify({"erro": "Erro interno ao processar QR Code."}), 500

@bp.route('/chamar-aluno', methods=['POST'])
@login_required
def chamar_aluno():
    """
    Endpoint para registrar uma chamada de aluno.

    Body (JSON):
        Dados do aluno a ser chamado.

    Returns:
        JSON: {sucesso: bool} ou {erro: str}.
    """
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