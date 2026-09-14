/* 2TO ERP — Service Worker (خفيف، شبكة أولاً مع سقوط للكاش) */
"use strict";

var CACHE_NAME = "2to-cache-v10";
var PRECACHE = [
  "/static/manifest.webmanifest",
  "/static/img/icon-192.png",
  "/static/img/icon-512.png",
  "/static/img/logo-mark.svg"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function (cache) { return cache.addAll(PRECACHE); })
      .then(function () { return self.skipWaiting(); })
      .catch(function () {})
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; })
          .map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET" || !req.url.startsWith(self.location.origin)) {
    return;
  }
  event.respondWith(
    fetch(req)
      .then(function (resp) {
        if (resp && resp.ok && req.url.indexOf("/api/") === -1) {
          var copy = resp.clone();
          caches.open(CACHE_NAME).then(function (cache) { cache.put(req, copy); });
        }
        return resp;
      })
      .catch(function () {
        return caches.match(req).then(function (hit) { return hit || caches.match(req.url); });
      })
  );
});