const CACHE_NAME = "autoinsight-v1";
const ASSETS_TO_CACHE = [
  "/",
  "/dashboard",
  "/upload",
  "/nlq",
  "/admin",
  "/offline",
];

// Install event — cache core assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

// Activate event — clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch event — serve from cache, fall back to network
self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).catch(() => {
        // If both cache and network fail, show offline page
        if (event.request.mode === "navigate") {
          return caches.match("/offline");
        }
        return new Response("Offline", { status: 503 });
      });
    })
  );
});
