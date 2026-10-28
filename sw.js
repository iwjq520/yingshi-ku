/* 影视库 离线缓存外壳 v7:缓存秒开 + 后台静默更新 + 弱网兜底 */
var CACHE = "yingshiku-v7";
var SHELL = ["./", "./index.html", "./icon-192.png", "./icon-512.png", "./manifest.webmanifest"];
var NET_TIMEOUT = 8000;
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
function fetchWithTimeout(req) {
  return new Promise(function (resolve) {
    var done = false;
    var t = setTimeout(function () { if (!done) { done = true; resolve(null); } }, NET_TIMEOUT);
    fetch(req).then(function (r) {
      if (done) return;
      done = true; clearTimeout(t);
      try { caches.open(CACHE).then(function (c) { c.put(req, r.clone()); }); } catch (err) {}
      resolve(r);
    }).catch(function () {
      if (done) return;
      done = true; clearTimeout(t); resolve(null);
    });
  });
}
self.addEventListener("fetch", function (e) {
  var u = e.request.url;
  if (e.request.method !== "GET") return;
  // 影视数据接口与视频流：永远走网络（保证实时）
  if (u.indexOf("bfzyapi.com") >= 0 || u.indexOf(".m3u8") >= 0 || u.indexOf(".ts") >= 0 || u.indexOf("wsyzy") >= 0) return;
  // 外壳与图标：缓存秒开，后台静默拉新版，下次打开生效
  e.respondWith(
    caches.match(e.request).then(function (hit) {
      var updating = fetchWithTimeout(e.request);
      if (hit) return hit;
      return updating.then(function (r) {
        if (r) return r;
        // 无缓存且网络弱：导航请求回退缓存的 index.html，避免白屏
        if (e.request.mode === "navigate") return caches.match("./index.html");
        return Response.error();
      });
    })
  );
});
