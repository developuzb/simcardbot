/* ============================================================
   main.js — animatsiya, count-up, narx toggle, slotlar,
   sticky CTA, scroll-depth treking, exit-intent.
   Hammasi JS-off bo'lsa ham mantiqiy zaxira bilan ishlaydi.
   ============================================================ */
(function () {
  var C = window.CONFIG || {};
  var T = window.track || function () {};

  // --- 1) Reveal animatsiya ---
  var revs = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var ro = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); ro.unobserve(e.target); } });
    }, { threshold: 0.12 });
    revs.forEach(function (el) { ro.observe(el); });
  } else {
    revs.forEach(function (el) { el.classList.add("in"); });  // zaxira: darrov ko'rsat
  }

  // --- 2) Count-up (JS-off bo'lsa HTML'dagi yakuniy qiymat qoladi) ---
  function countUp(el) {
    var target = parseInt(el.getAttribute("data-count"), 10);
    if (isNaN(target)) return;
    var suffix = el.getAttribute("data-suffix") || "";
    var dur = 1200, start = null;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var val = Math.round(target * (0.2 + 0.8 * p) * (p < 1 ? p : 1)); // yengil ease
      el.textContent = Math.round(target * easeOut(p)) + suffix;
      if (p < 1) requestAnimationFrame(step); else el.textContent = target + suffix;
    }
    requestAnimationFrame(step);
  }
  function easeOut(p){ return 1 - Math.pow(1 - p, 3); }
  var nums = document.querySelectorAll("[data-count]");
  if ("IntersectionObserver" in window && !prefersReduced()) {
    var no = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { countUp(e.target); no.unobserve(e.target); } });
    }, { threshold: 0.5 });
    nums.forEach(function (el) { no.observe(el); });
  }
  function prefersReduced(){ return window.matchMedia && matchMedia("(prefers-reduced-motion:reduce)").matches; }

  // --- 3) Narx toggle (oylik/yillik) ---
  var tgs = document.querySelectorAll(".tg");
  var amts = document.querySelectorAll(".amt");
  tgs.forEach(function (b) {
    b.addEventListener("click", function () {
      tgs.forEach(function (x) { x.classList.remove("active"); x.setAttribute("aria-selected", "false"); });
      b.classList.add("active"); b.setAttribute("aria-selected", "true");
      var per = b.getAttribute("data-period");
      amts.forEach(function (a) {
        var v = a.getAttribute(per === "year" ? "data-year" : "data-month");
        if (v) a.textContent = v;
      });
      var perLabel = document.querySelectorAll(".plan .per");
      perLabel.forEach(function(p){ p.textContent = per === "year" ? "so'm/oy (yillik)" : "so'm/oy"; });
    });
  });

  // --- 4) Hudud o'rinlari (tanqislik) ---
  var slot = document.getElementById("slotN");
  if (slot && C.REGION_SLOTS != null) slot.textContent = C.REGION_SLOTS;

  // --- 5) Mobil sticky CTA (hero'dan o'tilganda) ---
  var mob = document.getElementById("mobCta");
  var footer = document.querySelector(".ftr");
  if (mob) {
    window.addEventListener("scroll", function () {
      var y = window.scrollY, vh = window.innerHeight;
      var nearFooter = footer && (footer.getBoundingClientRect().top < vh);
      if (y > vh * 0.7 && !nearFooter) mob.classList.add("show");
      else mob.classList.remove("show");
    }, { passive: true });
  }

  // --- 6) Scroll-depth treking (har biri bir marta) ---
  var marks = { 25: false, 50: false, 75: false, 100: false };
  window.addEventListener("scroll", function () {
    var st = window.scrollY, h = document.documentElement.scrollHeight - window.innerHeight;
    var pct = h > 0 ? (st / h) * 100 : 0;
    [25, 50, 75, 100].forEach(function (m) {
      if (!marks[m] && pct >= m) { marks[m] = true; T("scroll_depth", { percent: m }); }
    });
  }, { passive: true });

  // --- 7) Asosiy bo'limlar ko'rilishi ---
  var watch = ["demo", "narx", "isbot", "eksklyuziv"];
  if ("IntersectionObserver" in window) {
    var so = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) { T("section_view", { section: e.target.id }); so.unobserve(e.target); }
      });
    }, { threshold: 0.4 });
    watch.forEach(function (id) { var el = document.getElementById(id); if (el) so.observe(el); });
  }

  // --- 8) Exit-intent (desktop) — chatni ochadi (bir marta) ---
  if (C.FLAGS && C.FLAGS.exitIntent && window.matchMedia && matchMedia("(pointer:fine)").matches) {
    var fired = false;
    document.addEventListener("mouseout", function (e) {
      if (fired) return;
      if (e.clientY <= 0 && !e.relatedTarget) {
        fired = true;
        if (window.openChat) window.openChat();
      }
    });
  }
})();
