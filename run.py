import os
from app import create_app

# Obtém o ambiente atual (padrão para development se não definido)
env_name = os.getenv('FLASK_ENV', 'development')
app = create_app(env_name)

if __name__ == '__main__':
    # No GAE, o gunicorn chama 'app' diretamente. 
    # Localmente, rodamos assim:
    app.run(host='0.0.0.0', port=5000, debug=(env_name == 'development'))