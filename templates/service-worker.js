const CACHE_NAME = 'docker-monitor-cache-v1';
const urlsToCache = [
  '/',
  '/mobile.html',        // Main HTML file path
  '/index.html',        // Main HTML file path
  '/setup.html',        // Main HTML file path
  '/login.html',        // Main HTML file path
  '/favicon.ico', // Path to favicon
  // Add here additional static resources if necessary
];

// Install event - caches specified files
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Caching files');
        return cache.addAll(urlsToCache);
      })
  );
});

// Activate event - cleans up old caches
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

// Fetch event - responds with cached files if available
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Is there a response in the cache?
        if (response) {
          return response;
        }
        // If not found, continue with the network request
        return fetch(event.request);
      })
  );
});