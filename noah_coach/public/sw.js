// sw.js — Service worker mínimo de NOAH.
// Su único objetivo es habilitar la instalación como app (Android / Chrome de
// escritorio necesitan un SW con handler de fetch para ofrecer "Instalar").
// NO cachea nada a propósito: así nunca sirve archivos viejos después de un
// deploy. En iPhone la instalación ("Agregar a inicio") funciona sin esto.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(
  caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k)))).then(() => self.clients.claim())
));
// Handler de fetch "passthrough": no llama a respondWith, así el navegador
// resuelve cada request normalmente (sin caché propia).
self.addEventListener('fetch', () => {});
