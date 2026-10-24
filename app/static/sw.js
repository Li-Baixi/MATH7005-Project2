/* Minimal service worker — demo shell caching so the phone demo works
   even if the venue Wi-Fi flakes. API calls always hit the network. */

const CACHE = "accesshk-v1";
const SHELL = ["./", "./style.css", "./app.js", "./manifest.json", "./icon.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;      // live data only
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
