import os
import firebase_admin
from firebase_admin import firestore
from flask import Flask
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect  # Nova importação
from .config import config_by_name

# Inicializa extensões globalmente
oauth = OAuth()
csrf = CSRFProtect()  # Inicialização da proteção CSRF
db = None

def create_app(config_name='default'):
    """
    Função Factory para criar a instância da aplicação Flask.
    """
    app = Flask(__name__)
    
    app.config.from_object(config_by_name[config_name])

    # --- Inicialização do Firebase ---
    global db
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={
                'projectId': 'singular-winter-471620-u0',
            })
        db = firestore.client()
        print("Firebase Admin SDK inicializado com sucesso.")
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao inicializar Firebase: {e}")
        db = None

    # --- Inicialização das Extensões ---
    oauth.init_app(app)
    csrf.init_app(app)  # Vincula o CSRFProtect ao app

    # Configuração do Google OAuth
    oauth.register(
        name='google',
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
        client_kwargs={'scope': 'openid email profile'}
    )

    # --- REGISTRO DE BLUEPRINTS ---
    from .routes import main, auth, api
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)

    return app