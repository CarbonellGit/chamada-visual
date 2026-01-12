# Chamada Visual - Colégio Carbonell

## Visão Geral
O sistem de **Chamada Visual** é uma solução corporativa desenvolvida para o Colégio Carbonell que integra o sistema de gestão acadêmica (Sophia) com painéis de exibição visual. O objetivo é modernizar o processo de chamada de alunos, permitindo que a portaria ou coordenação solicite alunos via sistema, e estes sejam exibidos instantaneamente em monitores distribuídos pela escola.

O fluxo de dados consiste na **Busca (integração com API Sophia)** -> **Processamento e Fila (Backend)** -> **Exibição em Tempo Real (Firestore + Frontend)**.

## Tech Stack

O projeto utiliza uma arquitetura baseada em microsserviços leves e serverless friendly.

### Backend
*   **Python 3.10+**
*   **Flask 3.0.0**: Framework web minimalista.
*   **Firebase Admin SDK 6.4.0**: Gerenciamento do banco de dados NoSQL (Firestore).
*   **Authlib 1.3.0**: Autenticação via OAuth 2.0 (Google Workspace).
*   **Requests 2.31.0**: Cliente HTTP para comunicação com API Sophia.
*   **Gunicorn 21.2.0**: Servidor WSGI para produção.

### Frontend
*   **HTML5 / CSS3**: Interfaces responsivas.
*   **JavaScript (ES6)**: Lógica client-side e manipulação de DOM.
*   **Firestore Client SDK**: Para listeners em tempo real (snapshots) nos painéis.

## Setup e Instalação

Siga os passos abaixo para preparar o ambiente de desenvolvimento local.

### Pré-requisitos
*   Python 3.10 ou superior instalado.
*   Google Cloud Credentials (arquivo JSON de conta de serviço).
*   Credenciais de API e acesso ao banco de dados do Sophia.

### Passo 1: Clonar e Configurar Ambiente

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd chamada-visual

# Crie o ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### Passo 2: Instalar Dependências

```bash
pip install -r requirements.txt
```

### Passo 3: Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto copiando o exemplo abaixo:

```ini
# Segurança e Sessão
SECRET_KEY='sua_chave_secreta_aqui'
ALLOWED_EMAIL_DOMAIN='colegiocarbonell.com.br'

# Google OAuth
GOOGLE_CLIENT_ID='seu_client_id'
GOOGLE_CLIENT_SECRET='seu_client_secret'

# Integração Sophia
SOPHIA_TENANT='seu_tenant'
SOPHIA_USER='usuario_api'
SOPHIA_PASSWORD='senha_api'
SOPHIA_API_HOSTNAME='api.sophia.com.br'

# Regras de Negócio
IGNORE_CLASS_PREFIX='EM'
```

## Scripts Disponíveis

### Rodar localmente (Desenvolvimento)
Inicia o servidor Flask com hot-reload ativo.

```bash
python run.py
```
Acesse: `http://localhost:5000`

### Rodar em Produção (Gunicorn)
Em ambientes linux ou containers, utilize o Gunicorn.

```bash
gunicorn --bind 0.0.0.0:8080 --workers 4 --threads 8 app:app
```

### Deploy
Este projeto está configurado para **Google App Engine**.
Para realizar o deploy:

```bash
gcloud app deploy app.yaml
```

## Estrutura de Diretórios
*   `app/`: Código fonte da aplicação.
    *   `routes/`: Endpoints e controladores (Blueprints).
    *   `services/`: Lógica de negócios e integrações externas.
    *   `static/`: Assets (CSS, JS, Imagens).
    *   `templates/`: Arquivos HTML (Jinja2).
*   `instance/`: Arquivos de configuração da instância (se houver).