import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <App />
);

// Quita el splash inline (index.html) apenas React pintó la pantalla de carga v2.
requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById('noah-boot')?.remove()));

// Service worker: habilita instalar NOAH como app (botón "Instalar" en
// Android/Chrome). No cachea, así que no sirve versiones viejas tras un deploy.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
