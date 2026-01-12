import os
import firebase_admin
from firebase_admin import firestore
from flask import Flask
from authlib.integrations.flask_client import OAuth
from .config import config_by_name

# Inicializa extensões globalmente (mas sem vinculá-las ao app ainda)
oauth = OAuth()
db = None  # O cliente Firestore será inicializado dentro da factory

def create_app(config_name='default'):
    """
    Função Factory para criar a instância da aplicação Flask.
    Isso facilita testes e permite rodar múltiplas instâncias com configs diferentes.
    """
    app = Flask(__name__)
    
    # Carrega configurações do objeto Config
    app.config.from_object(config_by_name[config_name])

    # --- Inicialização do Firebase (Lógica migrada do antigo app.py) ---
    global db
    # Remove credenciais locais conflitantes (fix para GAE/Windows)
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    
    try:
        # Verifica se o app já foi inicializado para evitar erro de 'App already exists'
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={
                'projectId': 'singular-winter-471620-u0',
            })
        db = firestore.client()
        print("Firebase Admin SDK inicializado com sucesso.")
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao inicializar Firebase: {e}")
        db = None

    # --- Inicialização do OAuth ---
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
        client_kwargs={'scope': 'openid email profile'}
    )

   # --- REGISTRO DE BLUEPRINTS (Adicione isso no final da função create_app) ---
    from .routes import main, auth, api
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)

    return app
