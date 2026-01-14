import logging
import concurrent.futures
import base64
from flask import Blueprint, request, jsonify, session, Response
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
    """Injeta contagem atual no objeto aluno."""
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
        alunos = sophia.search_students(parte_nome, grupo)
        
        # Enriquece com contagem em paralelo
        if alunos:
            with concurrent.futures.ThreadPoolExecutor() as executor:
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
        aluno = sophia.get_student_by_code(student_code)
        
        if aluno:
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
    
    # 1. Obtém a contagem ATUAL (antes de inserir o novo)
    # Isso garante que pegamos o número consolidado no banco.
    contagem_previa = 0
    try:
        contagem_previa = firestore.get_student_call_count(data.get('id'), data.get('turma'))
    except Exception:
        pass
        
    # 2. Registra o novo chamado
    sucesso = firestore.call_student(data)
    
    if sucesso:
        # 3. Retorna a contagem prévia + 1
        # Matemática simples vence latência de banco de dados.
        nova_contagem_real = contagem_previa + 1
        return jsonify({"sucesso": True, "nova_contagem": nova_contagem_real})
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

# --- NOVAS ROTAS PARA RESPONSÁVEIS ---

@bp.route('/aluno/<student_id>/responsaveis', methods=['GET'])
@login_required
def listar_responsaveis(student_id):
    """
    Retorna a lista de responsáveis de um aluno específico.
    """
    if not student_id:
        return jsonify({"erro": "ID do aluno necessário"}), 400

    try:
        responsaveis = sophia.get_student_responsibles(student_id)
        # Se retornar lista vazia, o front tratará mostrando aviso
        return jsonify(responsaveis)
    except Exception as e:
        logger.error(f"Erro na rota de responsáveis: {e}")
        return jsonify({"erro": "Erro interno ao buscar responsáveis"}), 500

@bp.route('/responsavel/<resp_id>/foto', methods=['GET'])
@login_required
def foto_responsavel(resp_id):
    """
    Proxy para a foto do responsável.
    Decodifica o Base64 do Sophia e retorna como imagem binária (blob).
    """
    try:
        b64_string = sophia.get_responsible_photo_base64(resp_id)
        
        if not b64_string:
            # Retorna 404 para que o frontend possa exibir uma imagem padrão (placeholder)
            return jsonify({"erro": "Foto não encontrada"}), 404

        # Tratamento robusto do Base64 (ex: "data:image/jpeg;base64,/9j/4AAQ...")
        # Separa o cabeçalho "data:..." do conteúdo real se existir
        if ',' in b64_string:
            header, encoded = b64_string.split(',', 1)
            # Tenta extrair o mime type dinamicamente (ex: image/png ou image/jpeg)
            try:
                mime_type = header.split(':')[1].split(';')[0]
            except IndexError:
                mime_type = 'image/jpeg'
        else:
            # Fallback caso a API retorne a string crua sem cabeçalho
            encoded = b64_string
            mime_type = 'image/jpeg'

        img_data = base64.b64decode(encoded)
        
        return Response(img_data, mimetype=mime_type)
        
    except Exception as e:
        logger.error(f"Erro no proxy de foto do responsável {resp_id}: {e}")
        return jsonify({"erro": "Falha ao processar imagem"}), 500