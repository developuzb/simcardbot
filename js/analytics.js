/* ============================================================
   ANALYTICS — Yandex Metrica + GA4 (ixtiyoriy) + track() yordamchisi.
   ID'lar CONFIG'da bo'sh bo'lsa — hammasi jim no-op (xato bermaydi).
   Hodisalar: chat_open, chat_message_sent, lead_submitted,
              telegram_click, plan_selected, scroll_depth, chat_error
   ============================================================ */
(function () {
  var C = window.CONFIG || {};
  var mId = C.METRICA_ID, gId = C.GA4_ID;

  // --- Yandex Metrica ---
  if (mId) {
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (var j = 0; j < e.length; j++) { if (e[j] === r) { return; } }
      k = e.createElement(t); a = e.getElementsByTagName(t)[0];
      k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
    })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
    try {
      ym(mId, "init", { clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: false });
    } catch (e) {}
  }

  // --- Google Analytics 4 (ixtiyoriy) ---
  if (gId) {
    var s = document.createElement("script");
    s.async = 1; s.src = "https://www.googletagmanager.com/gtag/js?id=" + gId;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", gId);
  }

  // --- Yagona track() ---
  // track("lead_submitted", {plan:"biznes"})
  window.track = function (event, params) {
    params = params || {};
    try { if (mId && window.ym) { ym(mId, "reachGoal", event, params); } } catch (e) {}
    try { if (gId && window.gtag) { window.gtag("event", event, params); } } catch (e) {}
    // Konsolda ko'rinib tursin (debug uchun; analitika ulanmagan bo'lsa ham bilinadi):
    if (window.console && console.debug) { console.debug("[track]", event, params); }
  };
})();
