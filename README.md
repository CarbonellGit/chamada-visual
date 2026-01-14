# 🏫 Chamada Visual - Colégio Carbonell

Bem-vindo à documentação oficial do sistema **Chamada Visual**. Esta aplicação corporativa foi projetada para modernizar e agilizar a comunicação entre a gestão escolar (Portaria/Coordenação) e os alunos, integrando o ERP acadêmico (Sophia) com monitores de exibição em tempo real.

---

## 📖 Visão Geral

O **Chamada Visual** resolve o problema de notificação de alunos em um ambiente escolar movimentado. Ao invés de sistemas sonoros ou avisos manuais, a escola utiliza painéis visuais distribuídos estrategicamente.

### Fluxo Principal
1.  **Solicitação**: A portaria ou coordenação busca um aluno (pelo nome ou matrícula) através de uma interface web segura.
2.  **Integração**: O sistema consulta a API do ERP Sophia para validar os dados e obter informações atualizadas (turma, fotos, etc).
3.  **Fila de Chamada**: O aluno é adicionado a uma fila de chamada no banco de dados em tempo real.
4.  **Exibição**: Monitores conectados ao sistema recebem a notificação instantaneamente (via WebSocket/Listeners) e exibem o chamado visual e sonoro.

---

## 🚀 Funcionalidades

*   **Autenticação Corporativa**: Login seguro via Google Workspace (apenas domínio `@colegiocarbonell.com.br`).
*   **Integração Sophia ERP**: Conexão direta com a API do sistema acadêmico para busca de alunos e validação de matrículas.
*   **Tempo Real (Real-time)**: Atualização instantânea dos painéis sem necessidade de *refresh* (uso de Firestore Listeners).
*   **Cache Inteligente**: Otimização de requisições à API do Sophia para performance e economia de recursos.
*   **Gestão Automática**:
    *   *Garbage Collector*: Serviço de *background* que limpa chamadas antigas automaticamente para manter a fila relevante.
    *   *Limpeza de Cache*: Rotinas para invalidar dados obsoletos.
*   **Interface Responsiva**: Design adaptável para Desktops (Portaria) e Smart TVs (Painéis).

---

## 🛠️ Tech Stack

O projeto foi construído sobre uma arquitetura de microsserviços leve, focada em manutenibilidade e escalabilidade no Google Cloud Platform (GCP).

### Backend
*   **Linguagem**: [Python 3.10+](https://www.python.org/)
*   **Framework Web**: [Flask 3.0.0](https://flask.palletsprojects.com/)
*   **Banco de Dados**: [Google Firestore](https://firebase.google.com/docs/firestore) (NoSQL)
*   **Autenticação**: [Authlib](https://docs.authlib.org/) (OAuth 2.0 / OIDC)
*   **Servidor WSGI**: [Gunicorn](https://gunicorn.org/) (Produção)

### Frontend
*   **Markup/Style**: HTML5, CSS3 Semântico.
*   **Scripting**: JavaScript ES6+ (Vanilla).
*   **SDK**: Firebase JS SDK (Client-side listeners).

---

## 📂 Estrutura do Projeto

A organização de diretórios segue o padrão de *Application Factories* do Flask:

```
chamada-visual/
├── app/
│   ├── __init__.py          # Factory da Aplicação (Configura Flask, DB, Auth)
│   ├── config.py            # Configurações de Ambiente (Dev/Prod/Test)
│   ├── routes/              # Blueprints (Controladores)
│   │   ├── api.py           # Endpoints JSON (Busca, Limpeza)
│   │   ├── auth.py          # Rotas de Login/Logout (Google OAuth)
│   │   └── main.py          # Rotas de Renderização de Views
│   ├── services/            # Lógica de Negócios e Integrações
│   │   ├── cleanup.py       # Background Worker (Garbage Collector)
│   │   ├── firestore.py     # Camada de Acesso a Dados (DAO)
│   │   └── sophia.py        # Cliente API Sophia
│   ├── static/              # Assets Públicos (CSS, JS, Imagens)
│   └── templates/           # Arquivos HTML (Jinja2)
├── instance/                # Configurações sensíveis (ignorado no git)
├── .env                     # Variáveis de Ambiente
├── app.yaml                 # Configuração de Deploy (App Engine)
├── requirements.txt         # Dependências Python
└── run.py                   # Entrypoint da Aplicação
```

---

## ⚡ Setup e Instalação

Siga este guia para configurar o ambiente de desenvolvimento local.

### Pré-requisitos
1.  **Python 3.10+** instalado.
2.  **Conta de Serviço Google** (JSON) com permissão no Firestore.
3.  **Credenciais Sophia** (Tenant, Usuário e Senha da API).
4.  **Credenciais OAuth 2.0** do Google Cloud Console.

### 1. Clonar o Repositório

```bash
git clone https://github.com/CarbonellGit/chamada-visual.git
cd chamada-visual
```

### 2. Criar Ambiente Virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes chaves:

```ini
# --- Configurações Gerais do Flask ---
FLASK_APP=run.py
FLASK_DEBUG=1
SECRET_KEY='gerar_uma_uuid4_segura_aqui'

# --- Segurança ---
# Domínio permitido para login (Google Workspace)
ALLOWED_EMAIL_DOMAIN='colegiocarbonell.com.br'

# --- Google OAuth 2.0 ---
# Obtenha no Google Cloud Console > APIs & Services > Credentials
GOOGLE_CLIENT_ID='seu_client_id_aqui'
GOOGLE_CLIENT_SECRET='seu_client_secret_aqui'
GOOGLE_DISCOVERY_URL='https://accounts.google.com/.well-known/openid-configuration'

# --- Integração Sophia ERP ---
SOPHIA_API_HOSTNAME='api.sophia.com.br'
SOPHIA_TENANT='seu_tenant_id'
SOPHIA_USER='usuario_integracao'
SOPHIA_PASSWORD='senha_integracao'

# --- Regras de Negócio ---
# Ignorar turmas com este prefixo na busca (ex: Ensino Médio)
IGNORE_CLASS_PREFIX='EM'
```

> **Nota**: Para o Firestore funcionar localmente, certifique-se de estar autenticado via `gcloud auth application-default login` ou defina a variável `GOOGLE_APPLICATION_CREDENTIALS` apontando para seu JSON de serviço.

---

## 🏃‍♂️ Executando a Aplicação

### Modo Desenvolvimento
Inicia o servidor Flask com *hot-reload* e *debug mode*.

```bash
python run.py
```
*   Acesse: `http://localhost:5000`

### Modo Produção (Gunicorn)
Recomendado para servidores Linux ou Containers (Docker/App Engine).

```bash
gunicorn --bind 0.0.0.0:8080 --workers 4 --threads 8 --timeout 0 app:app
```

---

## ☁️ Deploy (Google App Engine)

Este projeto contém o arquivo `app.yaml` configurado para o ambiente *Standard* do App Engine.

1.  **Configurar Projeto**:
    ```bash
    gcloud config set project ID_DO_PROJETO
    ```

2.  **Deploy**:
    ```bash
    gcloud app deploy app.yaml
    ```
    *   O sistema provisionará automaticamente as instâncias e o SSL gerenciado.

---

## 🔧 Scripts Utilitários

### Exportação de Alunos
Script para gerar CSV com base nos dados brutos do Sophia (útil para conferência).

```bash
python exportar_alunos.py
```
*   Gera: `lista_alunos_2026.csv`

---

<br>
<br>

<div align="center">
    <p>Desenvolvido by: Thiago Marques Luiz</p>
</div>