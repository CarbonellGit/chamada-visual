import os
from dotenv import load_dotenv

# Carrega o .env explicitamente para garantir que as variáveis estejam disponíveis
load_dotenv()

class Config:
    """Configurações base comuns a todos os ambientes."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'chave_padrao_insegura_para_dev')
    ALLOWED_DOMAIN = os.getenv('ALLOWED_EMAIL_DOMAIN')
    
    # Configurações do Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    # Configurações do SophiA
    SOPHIA_TENANT = os.getenv('SOPHIA_TENANT')
    SOPHIA_USER = os.getenv('SOPHIA_USER')
    SOPHIA_PASSWORD = os.getenv('SOPHIA_PASSWORD')
    SOPHIA_API_HOSTNAME = os.getenv('SOPHIA_API_HOSTNAME')
    
    @property
    def SOPHIA_BASE_URL(self):
        """Propriedade dinâmica para montar a URL base apenas se configurado."""
        if self.SOPHIA_API_HOSTNAME and self.SOPHIA_TENANT:
            return f"https://{self.SOPHIA_API_HOSTNAME}/SophiAWebApi/{self.SOPHIA_TENANT}"
        return None

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

# Dicionário para facilitar a seleção de configuração
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}