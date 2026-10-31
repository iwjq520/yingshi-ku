/* 自毁 Service Worker：旧影视库 PWA 迁移用 —— 清空全部缓存、注销自身，然后让页面重新走网络 */
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.registration.unregister(); })
      .then(function () { return self.clients.matchAll({ type: "window" }); })
      .then(function (list) {
        list.forEach(function (c) {
          try { c.navigate(c.url); } catch (err) { try { c.location.reload(); } catch (e2) {} }
        });
      })
  );
});
/* 不拦截任何请求：一律走网络 */
