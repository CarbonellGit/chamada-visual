# Chamada Visual - Colégio Carbonell

O sistema **Chamada Visual** é uma aplicação web desenvolvida para otimizar o processo de chamada de alunos no Colégio Carbonell. A ferramenta permite que usuários autorizados busquem alunos em tempo real e os enviem para um painel de exibição, que é atualizado instantaneamente para todos que o estiverem visualizando.

## 🚀 Funcionalidades Principais

*   **Autenticação Segura:** Login exclusivo para usuários com contas de e-mail do domínio `@colegiocarbonell.com.br` através do Google (OAuth 2.0).
*   **Busca de Alunos:** Integração com a API do sistema de gestão Sophia para buscar alunos por nome.
*   **Filtros Inteligentes:** A busca pode ser filtrada por segmentos: Educação Infantil (EI), Anos Iniciais (AI) e Anos Finais (AF).
*   **Terminal de Chamada:** Uma interface simples onde o usuário busca o aluno e, com um clique, o "chama".
*   **Painel em Tempo Real:** Uma tela de exibição (ideal para TVs e monitores) que mostra os alunos chamados. O painel é atualizado para todos os clientes conectados em tempo real usando o Firebase Firestore.
*   **Notificação Sonora:** O painel emite um som de notificação sempre que um novo aluno é adicionado.
*   **Busca por Voz:** O terminal possui um botão para realizar buscas de alunos utilizando o microfone (Web Speech API).
*   **Limpeza Automática:** O painel remove automaticamente os alunos após um período de inatividade (10 minutos) e a lista se limita aos últimos 10 alunos chamados para manter a clareza.

## 🛠️ Tecnologias Utilizadas

*   **Backend:** Python, Flask, Gunicorn, Authlib
*   **Frontend:** HTML5, CSS3, JavaScript (ES6 Modules)
*   **Serviços:** Google Cloud App Engine, Google OAuth, Firebase Firestore

## ⚙️ Configuração e Instalação

Siga os passos abaixo para configurar e rodar o projeto em um ambiente de desenvolvimento local.

### 1. Pré-requisitos

*   Python 3.8 ou superior
*   Conta do Google para autenticação
*   Um projeto no Google Cloud com o App Engine e a API do Identity Platform ativadas.
*   Um projeto no Firebase com o Firestore habilitado.

### 2. Instalação

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/seu-usuario/chamada-visual.git
    cd chamada-visual
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # No Windows, use `venv\Scripts\activate`
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

### 3. Configuração do Ambiente

1.  **Crie um arquivo `.env`** na raiz do projeto. Este arquivo armazenará suas chaves de API e outras configurações sensíveis.

2.  **Adicione as seguintes variáveis de ambiente ao arquivo `.env`:**

    ```dotenv
    # Chave secreta para a sessão do Flask (pode ser qualquer string aleatória)
    SECRET_KEY='sua_chave_secreta_aqui'

    # Credenciais do Google OAuth 2.0
    # Obtenha no console do Google Cloud em "APIs e Serviços" > "Credenciais"
    GOOGLE_CLIENT_ID='seu-client-id.apps.googleusercontent.com'
    GOOGLE_CLIENT_SECRET='seu-client-secret'

    # Credenciais da API do sistema Sophia
    SOPHIA_TENANT='seu_tenant_sophia'
    SOPHIA_USER='seu_usuario_sophia'
    SOPHIA_PASSWORD='sua_senha_sophia'
    SOPHIA_API_HOSTNAME='api.sophia.com.br' # Exemplo
    ```

### 4. Configuração do Firebase

1.  Vá para o seu projeto no [console do Firebase](https://console.firebase.google.com/).
2.  Nas configurações do projeto, na aba "Geral", adicione um novo aplicativo Web.
3.  O Firebase fornecerá um objeto de configuração `firebaseConfig`.
4.  Abra o arquivo `static/firebase-config.js`.
5.  **Substitua o valor da `apiKey`** no objeto `firebaseConfig` pela chave de API fornecida pelo Firebase. As outras chaves geralmente já vêm pré-configuradas corretamente.

    ```javascript
    // static/firebase-config.js
    const firebaseConfig = {
        apiKey: "SUA_API_KEY_DO_FIREBASE", // <-- COLOQUE SUA CHAVE AQUI
        authDomain: "chamada-visual-carbonell.firebaseapp.com",
        projectId: "chamada-visual-carbonell",
        storageBucket: "chamada-visual-carbonell.appspot.com",
        messagingSenderId: "230654155076",
        appId: "1:230654155076:web:8d37de62797f65d2265f11"
    };
    ```

### 5. Rodando a Aplicação

Com o ambiente virtual ativado e as variáveis de ambiente configuradas, inicie a aplicação com o Flask:

```bash
flask run
```

Acesse a aplicação em `http://127.0.0.1:5000` no seu navegador.

## 🚀 Deploy

Este projeto está configurado para ser implantado no Google Cloud App Engine. O arquivo `app.yaml` (não incluído neste repositório base) e o `requirements.txt` são usados pelo App Engine para o deploy.

---

*Desenvolvido por: Thiago Marques*
