// Minimal service worker — required for PWA install prompts.
// Deliberately does not cache API responses (/api/jobs, /api/alerts,
// /api/draft-statement) so job data and drafts are always fresh.
const CACHE = "career-pro-jobs-shell-v1";
const SHELL = ["/", "/static/manifest.json", "/static/icon-192.png", "/static/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return; // never cache live data
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
