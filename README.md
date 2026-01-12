# Chamada Visual - Colégio Carbonell

O sistema de Chamada Visual é uma aplicação web desenvolvida para otimizar o processo de chamada de alunos no Colégio Carbonell. A ferramenta permite que usuários autorizados busquem alunos em tempo real e os enviem para um painel de exibição.

## 🚀 Funcionalidades Principais

*   **Autenticação Segura:** Login exclusivo para usuários com contas Google do domínio `@colegiocarbonell.com.br`.
*   **Busca de Alunos:** Integração com a API do sistema de gestão Sophia para buscar alunos pelo nome.
*   **Filtros Inteligentes:** As buscas podem ser filtradas por segmento de ensino.
*   **Terminal de Chamada:** Uma interface simples onde o usuário busca por um aluno.
*   **Painel de Exibição:** Uma tela de exibição (ideal para TVs e monitores) que mostra os alunos chamados.

## 🛠️ Tecnologias Utilizadas

Este projeto foi construído com uma combinação de tecnologias de backend e frontend:

### Backend:

*   **Python:** A principal linguagem de programação.
*   **Flask:** Um microframework web para construir a aplicação e a API.
*   **Gunicorn:** Um servidor WSGI para executar a aplicação em produção.
*   **Authlib:** Para integração com o sistema de autenticação do Google (OAuth).

### Frontend:

*   **HTML5 / CSS3:** Para a estrutura e estilização das páginas.
*   **JavaScript (ES6 Modules):** Para interatividade no lado do cliente, como buscas e eventos de clique.

## ⚙️ Configuração do Projeto

Siga estes passos para configurar o projeto para desenvolvimento local.

### 1. Pré-requisitos

*   Python 3.7+
*   Gerenciador de pacotes `pip`

### 2. Clonar o Repositório

```bash
git clone <url-do-repositorio>
cd <diretorio-do-repositorio>
```

### 3. Configurar um Ambiente Virtual

É recomendado usar um ambiente virtual para gerenciar as dependências do projeto.

```bash
# Crie um ambiente virtual
python -m venv venv

# Ative o ambiente
# No Windows:
# venv\Scripts\activate
# No macOS/Linux:
source venv/bin/activate
```

### 4. Instalar as Dependências

Instale todos os pacotes necessários usando o arquivo `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 5. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto. Este arquivo armazenará credenciais e configurações sensíveis. Adicione as seguintes variáveis:

```
# Chave secreta do Flask para gerenciamento de sessão
SECRET_KEY='sua_chave_secreta_forte_aqui'

# Credenciais do Google OAuth
GOOGLE_CLIENT_ID='seu_id_de_cliente_google'
GOOGLE_CLIENT_SECRET='seu_segredo_de_cliente_google'

# Credenciais da API Sophia
SOPHIA_TENANT='seu_tenant_sophia'
SOPHIA_USER='seu_usuario_sophia'
SOPHIA_PASSWORD='sua_senha_sophia'
SOPHIA_API_HOSTNAME='seu_hostname_da_api_sophia'
```

Substitua os valores de exemplo por suas credenciais reais.

## 🏃‍♀️ Executando a Aplicação

### Modo de Desenvolvimento

Para desenvolvimento, você pode usar o servidor embutido do Flask:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
```

A aplicação estará disponível em `http://127.0.0.1:5000`.

### Modo de Produção

Para implantações em produção, é recomendado usar um servidor WSGI como o Gunicorn:

```bash
gunicorn --bind 0.0.0.0:8080 app:app
```

## 💻 Como Usar

1.  **Login:** Acesse a URL da aplicação e faça login com uma conta Google autorizada do domínio `@colegiocarbonell.com.br`.
2.  **Terminal:** Após o login, você será direcionado para a página do **Terminal**.
3.  **Busca:** Utilize a barra de busca para encontrar alunos pelo nome. Você também pode aplicar filtros para diferentes segmentos.
4.  **Painel:** A página **Painel** é projetada para ser exibida em uma tela pública (como uma TV) para mostrar os alunos chamados.

---
*Desenvolvedor Original: Thiago Marques*