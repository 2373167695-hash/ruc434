// Service Worker for 人大434备考系统
var CACHE_VERSION = 'ruc434-v5';
var CACHE_URLS = [
  '.',
  'manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js',
  'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css',
  'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js'
];

// Install: pre-cache all core assets
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_VERSION).then(function(cache) {
      return cache.addAll(CACHE_URLS).catch(function(err) {
        console.log('SW install cache error:', err);
      });
    })
  );
});

// Activate: clean old caches
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(names) {
      return Promise.all(names.filter(function(n) { return n !== CACHE_VERSION; }).map(function(n) { return caches.delete(n); }));
    })
  );
});

// Fetch: cache-first for CDN, network-first for HTML
self.addEventListener('fetch', function(e) {
  var url = e.request.url;
  // CDN resources: cache-first
  if (url.indexOf('cdn.jsdelivr.net') >= 0) {
    e.respondWith(
      caches.match(e.request).then(function(cached) {
        return cached || fetch(e.request).then(function(resp) {
          return caches.open(CACHE_VERSION).then(function(cache) {
            cache.put(e.request, resp.clone());
            return resp;
          });
        });
      })
    );
    return;
  }
  // API calls: network-only
  if (url.indexOf('api.ruc434s.cloud') >= 0 || url.indexOf('xiaomimimo.com') >= 0) {
    return;
  }
  // Everything else (HTML, manifest): network-first, fallback to cache
  e.respondWith(
    fetch(e.request).then(function(resp) {
      return caches.open(CACHE_VERSION).then(function(cache) {
        cache.put(e.request, resp.clone());
        return resp;
      });
    }).catch(function() {
      return caches.match(e.request);
    })
  );
});
