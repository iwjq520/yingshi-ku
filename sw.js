/* 影视库 离线缓存外壳 v8:秒开 + 后台更新 + 弱网兜底 + 海报缓存 + 剧集离线缓存 */
var CACHE = "yingshiku-v56";
var IMG_CACHE = "yingshiku-imgs-v1";
var DL_CACHE = "yingshiku-dl";
var SHELL = ["./", "./index.html", "./dlplayer.html", "./icon-192.png", "./icon-512.png", "./manifest.webmanifest"];
var NET_TIMEOUT = 8000;
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE && k !== DL_CACHE && k.indexOf("imgs") < 0; }).map(function (k) { return caches.delete(k); }));
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
  // 已缓存到本机的剧集分片/清单：离线优先（无网也能播缓存的剧）
  if (u.indexOf(".ts") >= 0 || u.indexOf(".m3u8") >= 0) {
    e.respondWith(
      caches.open(DL_CACHE).then(function (c) {
        return c.match(e.request, { ignoreSearch: false }).then(function (hit) {
          if (hit) return hit;
          return fetch(e.request);
        });
      }).catch(function () { return fetch(e.request); })
    );
    return;
  }
  // 影视数据接口与云播放器：永远走网络（保证实时）
  if (u.indexOf("bfzyapi.com") >= 0 || u.indexOf("wsyzy") >= 0) return;
  // 海报图片：缓存优先（同一海报只拉一次，二次浏览秒出省流量）
  if (e.request.destination === "image") {
    e.respondWith(
      caches.open(IMG_CACHE).then(function (c) {
        return c.match(e.request).then(function (hit) {
          if (hit) return hit;
          return fetch(e.request).then(function (r) {
            if (r && (r.status === 200 || r.type === "opaque")) {
              c.put(e.request, r.clone());
              c.keys().then(function (keys) { if (keys.length > 200) c.delete(keys[0]); });
            }
            return r;
          }).catch(function () { return Response.error(); });
        });
      })
    );
    return;
  }
  // 页面导航：网络优先（保证第一时间拿到最新版），8秒超时/断网回退缓存秒开
  if (e.request.mode === "navigate" || /\.html?$/.test(u.split("?")[0]) || u.indexOf("manifest.webmanifest") >= 0) {
    e.respondWith(
      new Promise(function (resolve) {
        var done = false;
        var t = setTimeout(function () { if (!done) { done = true; resolve(null); } }, 8000);
        fetch(e.request, { cache: "reload" }).then(function (r) {
          if (done) return;
          done = true; clearTimeout(t);
          try { caches.open(CACHE).then(function (c) { c.put(e.request, r.clone()); }); } catch (err) {}
          resolve(r);
        }).catch(function () {
          if (done) return;
          done = true; clearTimeout(t);
          resolve(null);
        });
      }).then(function (r) {
        if (r) return r;
        return caches.match(e.request).then(function (c) { return c || caches.match("./index.html"); });
      })
    );
    return;
  }
  // 其余外壳资源（图标等）：缓存秒开，后台静默拉新版
  e.respondWith(
    caches.match(e.request).then(function (hit) {
      var updating = fetchWithTimeout(e.request);
      if (hit) return hit;
      return updating.then(function (r) {
        if (r) return r;
        return Response.error();
      });
    })
  );
});
