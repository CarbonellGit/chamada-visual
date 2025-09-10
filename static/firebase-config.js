// firebase-config.js

/**
 * Este arquivo é responsável pela configuração e inicialização do Firebase.
 * Ele importa os módulos necessários do SDK do Firebase, define a configuração
 * do projeto e exporta a instância do Firestore para ser usada em outras
 * partes da aplicação (terminal.html e painel.html).
 */

// Importa as funções necessárias do Firebase SDK a partir de uma URL de exemplo.
// Substitua pela URL da versão do SDK do Firebase que você deseja usar.
import { initializeApp } from "https://www.gstatic.com/firebasejs/X.Y.Z/firebase-app.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/X.Y.Z/firebase-firestore.js";

// Objeto de configuração do Firebase para este projeto web.
// IMPORTANTE: Substitua os valores abaixo pelos dados do seu projeto Firebase.
const firebaseConfig = {
    apiKey: "SUA_API_KEY",
    authDomain: "SEU_PROJECT_ID.firebaseapp.com",
    projectId: "SEU_PROJECT_ID",
    storageBucket: "SEU_PROJECT_ID.appspot.com",
    messagingSenderId: "SEU_MESSAGING_SENDER_ID",
    appId: "SEU_APP_ID"
};

// Inicializa o Firebase com as configurações fornecidas.
const app = initializeApp(firebaseConfig);

// Obtém e exporta a instância do banco de dados Firestore.
export const db = getFirestore(app);
