import os
import logging
from app import create_app
from app.services.cleanup import start_background_cleanup

# Configuração básica de logging para o console
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

app = create_app()

if __name__ == '__main__':
    # Define a porta (padrão 5000)
    port = int(os.environ.get("PORT", 5000))
    
    # INICIA O SERVIÇO DE LIMPEZA EM BACKGROUND (GARBAGE COLLECTOR)
    # Apenas se não estiver no modo reloader (para evitar threads duplicadas no debug)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        try:
            start_background_cleanup()
        except Exception as e:
            logging.error(f"Falha ao iniciar Garbage Collector: {e}")

    # Roda a aplicação Flask
    # host='0.0.0.0' permite acesso externo na rede local
    app.run(host='0.0.0.0', port=port, debug=True)