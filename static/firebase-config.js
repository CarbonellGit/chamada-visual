// firebase-config.js

// Importe as funções necessárias do Firebase
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.10/firebase-app.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/9.6.10/firebase-firestore.js";

// Suas chaves de configuração do Firebase
const firebaseConfig = {
    apiKey: "SUA_API_KEY",
    authDomain: "chamada-visual-carbonell.firebaseapp.com",
    projectId: "chamada-visual-carbonell",
    storageBucket: "chamada-visual-carbonell.appspot.com",
    messagingSenderId: "230654155076",
    appId: "1:230654155076:web:8d37de62797f65d2265f11"
};

// Inicializa o Firebase
const app = initializeApp(firebaseConfig);

// Exporta a instância do Firestore para ser usada em outros scripts
// A PALAVRA "EXPORT" ABAIXO É A SOLUÇÃO PARA O SEU PROBLEMA.
export const db = getFirestore(app);