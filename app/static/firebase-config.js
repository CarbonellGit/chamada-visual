// firebase-config.js

// Importe as funções necessárias do Firebase
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.10/firebase-app.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/9.6.10/firebase-firestore.js";

// Suas chaves de configuração do Firebase
const firebaseConfig = {

    apiKey: "AIzaSyCcur2f4wmzbXg1qKUMMfXJaCzSFh1zyFc",

    authDomain: "singular-winter-471620-u0.firebaseapp.com",

    projectId: "singular-winter-471620-u0",

    storageBucket: "singular-winter-471620-u0.firebasestorage.app",

    messagingSenderId: "159432382510",

    appId: "1:159432382510:web:449bfa58bfec3b6306e7bf"

};

// Inicializa o Firebase
const app = initializeApp(firebaseConfig);

// Exporta a instância do Firestore para ser usada em outros scripts
// A PALAVRA "EXPORT" ABAIXO É A SOLUÇÃO PARA O SEU PROBLEMA.
export const db = getFirestore(app);