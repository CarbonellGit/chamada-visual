import os
import logging
from app import create_app
# REMOVIDO: from app.services.cleanup import start_background_cleanup

# Configuração básica de logging para o console
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    
    # REMOVIDO: Bloco que iniciava o Garbage Collector (start_background_cleanup)
    # Isso permite que a instância do App Engine escale a zero e economize dinheiro.

    app.run(host='0.0.0.0', port=port, debug=True)