import os
import logging
import firebase_admin
from firebase_admin import firestore
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
from .config import config_by_name

# Inicializa extensões (objetos vazios que serão ligados ao app depois)
oauth = OAuth()
csrf = CSRFProtect()

def create_app(config_name='default'):
    """
    Função Factory para criar a instância da aplicação Flask.
    Configura Logs, Banco de Dados e Extensões.
    """
    # 1. Configuração de Logging (Primeira coisa a rodar)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # 2. Inicialização do Firebase (Banco de Dados)
    # Remove credenciais locais conflitantes (fix para GAE/Windows)
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={
                'projectId': 'singular-winter-471620-u0',
            })
        
        # Anexa o cliente do banco ao app (padrão factory)
        app.db = firestore.client()
        app.logger.info("Firebase Admin SDK inicializado com sucesso.")
        
    except Exception as e:
        app.logger.critical(f"FALHA CRÍTICA ao inicializar Firebase: {e}")
        app.db = None

    # 3. Inicialização das Extensões
    oauth.init_app(app)
    csrf.init_app(app)

    # Configuração do Google OAuth
    oauth.register(
        name='google',
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
        client_kwargs={'scope': 'openid email profile'}
    )

    # 4. Registro de Blueprints
    from .routes import main, auth, api
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)

    return app