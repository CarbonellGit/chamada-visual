// firebase-config.js

/**
 * Este arquivo é responsável pela configuração e inicialização do Firebase.
 * Ele importa os módulos necessários do SDK do Firebase, define a configuração
 * do projeto e exporta a instância do Firestore para ser usada em outras
 * partes da aplicação (terminal.html e painel.html).
 */

// Importa as funções necessárias do Firebase SDK.
// initializeApp é usada para criar e inicializar uma instância de aplicativo Firebase.
// getFirestore é usada para obter a instância do serviço Cloud Firestore.
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.10/firebase-app.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/9.6.10/firebase-firestore.js";

// Objeto de configuração do Firebase para este projeto web.
// IMPORTANTE: A chave 'apiKey' deve ser preenchida com a chave de API real
// do seu projeto Firebase para que a aplicação funcione.
const firebaseConfig = {
    apiKey: "SUA_API_KEY", // Substitua pela sua chave de API
    authDomain: "chamada-visual-carbonell.firebaseapp.com",
    projectId: "chamada-visual-carbonell",
    storageBucket: "chamada-visual-carbonell.appspot.com",
    messagingSenderId: "230654155076",
    appId: "1:230654155076:web:8d37de62797f65d2265f11"
};

// Inicializa o Firebase com as configurações fornecidas.
// Isso cria uma conexão com o seu projeto Firebase na nuvem.
const app = initializeApp(firebaseConfig);

// Obtém e exporta a instância do banco de dados Firestore.
// A palavra-chave 'export' torna a variável 'db' disponível para importação
// em outros scripts que são do tipo "module".
export const db = getFirestore(app);
