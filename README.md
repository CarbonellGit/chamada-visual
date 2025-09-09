# Chamada Visual - Colégio Carbonell

O sistema **Chamada Visual** é uma aplicação web desenvolvida para otimizar o processo de chamada de alunos no Colégio Carbonell. A ferramenta permite que usuários autorizados busquem alunos em tempo real e os enviem para um painel de exibição, que é atualizado instantaneamente para todos que o estiverem visualizando.

## 🚀 Funcionalidades Principais

* **Autenticação Segura:** Login exclusivo para usuários com contas de e-mail do domínio `@colegiocarbonell.com.br` através do Google.
* **Busca de Alunos:** Integração com a API do sistema de gestão Sophia para buscar alunos por nome.
* **Filtros Inteligentes:** A busca pode ser filtrada por segmentos: Educação Infantil (EI), Anos Iniciais (AI) e Anos Finais (AF).
* **Terminal de Chamada:** Uma interface simples onde o usuário busca o aluno e, com um clique, o "chama".
* **Painel em Tempo Real:** Uma tela de exibição (ideal para TVs e monitores) que mostra os alunos chamados. O painel é atualizado para todos os clientes conectados em tempo real usando o Firebase Firestore.
* **Notificação Sonora:** O painel emite um som de notificação sempre que um novo aluno é adicionado.
* **Busca por Voz:** O terminal possui um botão para realizar buscas de alunos utilizando o microfone.
* **Limpeza Automática:** O painel remove automaticamente os alunos após um período de inatividade (10 minutos) e a lista se limita aos últimos 10 alunos chamados para manter a clareza.

## 🛠️ Tecnologias Utilizadas

Este projeto foi construído com uma combinação de tecnologias de backend, frontend e serviços em nuvem:

### Backend:

* **Python:** Linguagem de programação principal.
* **Flask:** Microframework web para construir a aplicação e a API.
* **Gunicorn:** Servidor WSGI para rodar a aplicação em produção.
* **Authlib:** Para integração com o sistema de autenticação do Google (OAuth).

### Frontend:

* **HTML5 / CSS3:** Estruturação e estilização das páginas.
* **JavaScript (ES6 Modules):** Para interatividade do lado do cliente, como buscas, eventos de clique e comunicação com o Firebase.

### Banco de Dados e Real-Time:

* **Google Firebase (Firestore):** Utilizado como um banco de dados NoSQL em tempo real para sincronizar os alunos chamados entre o terminal e o painel de exibição.
