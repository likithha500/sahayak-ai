
const CACHE_NAME = "sahayak-offline-v2";
const OFFLINE_PAGE = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);

      try {
        await cache.add(
          new Request(OFFLINE_PAGE, {
            cache: "reload",
          })
        );
      } catch (error) {
        console.warn("Offline page precache failed:", error);
      }

      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();

      await Promise.all(
        names
          .filter((name) =>
            name.startsWith("sahayak-offline-") &&
            name !== CACHE_NAME
          )
          .map((name) => caches.delete(name))
      );

      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  if (request.method !== "GET") return;

  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;

  // Never cache API requests.
  if (url.pathname.startsWith("/api/")) return;

  // Next.js development HMR and internal requests
  // must not be cached.
  if (
    url.pathname.startsWith("/_next/webpack-hmr") ||
    url.pathname.includes("__next")
  ) {
    return;
  }

  // Cache Next.js JavaScript, CSS, fonts and images.
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE_NAME);

        const cached = await cache.match(request);

        if (cached) return cached;

        const response = await fetch(request);

        if (response.ok) {
          await cache.put(request, response.clone());
        }

        return response;
      })()
    );

    return;
  }

  // Cache offline page after successful network load.
  if (
    request.mode === "navigate" &&
    url.pathname === OFFLINE_PAGE
  ) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE_NAME);

        try {
          const response = await fetch(request);

          if (response.ok) {
            await cache.put(
              OFFLINE_PAGE,
              response.clone()
            );
          }

          return response;
        } catch {
          const cached = await cache.match(OFFLINE_PAGE);

          return cached || Response.error();
        }
      })()
    );
  }
});
