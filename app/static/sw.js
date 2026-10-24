/* Service worker — demo shell caching + offline route data.
   Same file serves both deployments:
   - static build (GitHub Pages): JSON data is cached network-first so
     visited queries survive offline; cross-origin live bus calls are
     never intercepted.
   - backend build (FastAPI): /api/ requests pass through untouched. */

const CACHE = "accesshk-v6";
const SHELL = ["./", "./style.css", "./app.js", "./manifest.json",
               "./icon.svg", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE)
        .map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);

  // cross-origin (live bus API) and backend /api/ calls: never intercept
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  const isData = url.pathname.endsWith(".json");
  if (isData) {
    // data: network-first (stay fresh), cache fallback (offline demo)
    e.respondWith(
      fetch(e.request).then((r) => {
        if (r.ok) {
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return r;
      }).catch(() => caches.match(e.request))
    );
  } else {
    // shell: cache-first for instant opens
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request))
    );
  }
});
