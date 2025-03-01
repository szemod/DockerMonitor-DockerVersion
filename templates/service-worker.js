const CACHE_NAME = 'docker-monitor-cache-v1';
const urlsToCache = [
  '/',
  '/mobile.html',        // A fő HTML fájl elérési útja
  '/index.html',        // A fő HTML fájl elérési útja
  '/setup.html',        // A fő HTML fájl elérési útja
  '/login.html',        // A fő HTML fájl elérési útja
  '/favicon.ico', // favicon helye
  // Adja hozzá a további statikus erőforrásokat, ha szükséges
];

// Telepítési esemény
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching files');
        return cache.addAll(urlsToCache);
      })
  );
});

// Kész esemény
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch esemény
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Cache-ből válasz található?
        if (response) {
          return response;
        }
        // Ha nem található, akkor folytassuk a hálózati kérést
        return fetch(event.request);
      })
  );
});