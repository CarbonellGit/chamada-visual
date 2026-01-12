import os
from dotenv import load_dotenv

# Carrega o .env explicitamente
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
    
    # CORREÇÃO: Construção direta da variável (sem @property)
    # Isso garante que o valor seja uma string (ou None) quando o Flask carregar
    SOPHIA_BASE_URL = None
    if SOPHIA_API_HOSTNAME and SOPHIA_TENANT:
        SOPHIA_BASE_URL = f"https://{SOPHIA_API_HOSTNAME}/SophiAWebApi/{SOPHIA_TENANT}"

    # --- REGRAS DE NEGÓCIO (Externalizadas) ---
    # Define o prefixo de turmas que devem ser IGNORADAS na busca (ex: Ensino Médio)
    # Se a escola mudar para "MEDIO", basta alterar aqui.
    IGNORE_CLASS_PREFIX = os.getenv('IGNORE_CLASS_PREFIX', 'EM')
    
    # Regex para extrair o ano da descrição da turma (ex: "Turma 2025")
    # Captura 4 dígitos consecutivos
    REGEX_CLASS_YEAR = r'(\d{4})'

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