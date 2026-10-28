/* 影视库 离线缓存外壳 */
var CACHE = "yingshiku-v6";
var SHELL = ["./", "./index.html", "./icon-192.png", "./icon-512.png", "./manifest.webmanifest"];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  var u = e.request.url;
  if (e.request.method !== "GET") return;
  // 影视数据接口与视频流：永远走网络（保证实时）
  if (u.indexOf("bfzyapi.com") >= 0 || u.indexOf(".m3u8") >= 0 || u.indexOf(".ts") >= 0 || u.indexOf("wsyzy") >= 0) return;
  // 页面外壳与图标：缓存优先（离线也能打开App）
  e.respondWith(
    caches.match(e.request).then(function (hit) {
      return hit || fetch(e.request).then(function (r) {
        var copy = r.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
        return r;
      });
    })
  );
});