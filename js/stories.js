/* ============================================================
   stories.js — "Tizim qanday ishlaydi" Instagram-uslub slayder.
   Avto-aylanadi, progress barlar to'ladi, yon tomon bosish bilan
   oldinga/orqaga, pauza tugmasi, ko'rinishga kirganda boshlanadi.
   ============================================================ */
(function () {
  var T = window.track || function () {};
  var V = "?v=2";  // rasm versiyasi (yangilanganda oshiring — kesh tozalanadi)
  var STEPS = [
    { img: "assets/story-1.jpg" + V, t: "Mijoz keladi",      d: "Mijoz SIM qidirib sizga murojaat qiladi." },
    { img: "assets/story-2.jpg" + V, t: "Chatga ulanadi",    d: "Bir tugma — va AI bot bilan suhbat boshlanadi." },
    { img: "assets/story-3.jpg" + V, t: "AI gaplashadi",     d: "Bot ehtiyojni so'rab, mos tarifni tanlaydi." },
    { img: "assets/story-4.jpg" + V, t: "Buyurtma olinadi",  d: "Ism, telefon, manzil — avtomatik yig'iladi." },
    { img: "assets/story-5.jpg" + V, t: "Guruhga tushadi",   d: "Buyurtma operator/kuryer Telegram guruhiga ketadi." },
    { img: "assets/story-6.jpg" + V, t: "Kuryer yetkazadi",  d: "Siz faqat yetkazasiz. Mijoz xursand 🎉" }
  ];
  var DUR = 3800;  // har slayd (ms)

  var root = document.getElementById("stories");
  if (!root) return;
  var barsEl = document.getElementById("stBars"),
      slidesEl = document.getElementById("stSlides"),
      capEl = document.getElementById("stCap"),
      pp = document.getElementById("stPP");

  var idx = 0, raf = null, startTs = 0, elapsed = 0, playing = false, started = false;

  // --- Qurish ---
  STEPS.forEach(function (s, i) {
    var bar = document.createElement("div"); bar.className = "st-bar";
    bar.innerHTML = '<span class="fill"></span>'; barsEl.appendChild(bar);
    var sl = document.createElement("div"); sl.className = "st-slide";
    var im = document.createElement("img");
    im.src = s.img; im.alt = s.t; im.loading = (i === 0 ? "eager" : "lazy");
    im.onerror = function () { sl.classList.add("noimg"); };
    sl.appendChild(im); slidesEl.appendChild(sl);
  });
  var fills = barsEl.querySelectorAll(".st-bar .fill");
  var slides = slidesEl.querySelectorAll(".st-slide");

  function render() {
    for (var i = 0; i < slides.length; i++) slides[i].classList.toggle("on", i === idx);
    var s = STEPS[idx];
    capEl.innerHTML = '<span class="st-num">' + (idx + 1) + ' / ' + STEPS.length + '</span>' +
      '<h4>' + s.t + '</h4><p>' + s.d + '</p>';
    for (var j = 0; j < fills.length; j++) fills[j].style.width = (j < idx ? "100%" : "0%");
  }

  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  function tick(ts) {
    if (!playing) return;
    if (!startTs) startTs = ts;
    var cur = elapsed + (ts - startTs);
    var p = cur / DUR; if (p > 1) p = 1;
    fills[idx].style.width = (p * 100) + "%";
    if (p >= 1) { go(idx + 1); return; }
    raf = requestAnimationFrame(tick);
  }
  function play() {
    if (playing) return;
    playing = true; startTs = 0; pp.textContent = "⏸"; pp.setAttribute("aria-label", "To'xtatish");
    raf = requestAnimationFrame(tick);
  }
  function pause() {
    if (!playing) return;
    playing = false; if (raf) cancelAnimationFrame(raf);
    if (startTs) elapsed += (now() - startTs); startTs = 0;
    pp.textContent = "▶"; pp.setAttribute("aria-label", "Davom ettirish");
  }
  function go(i) {
    if (raf) cancelAnimationFrame(raf);
    var loop = (i >= STEPS.length);
    idx = (i + STEPS.length) % STEPS.length;
    elapsed = 0; startTs = 0;
    render();
    if (loop) T("stories_complete", {});
    if (playing) raf = requestAnimationFrame(tick); else play();
  }

  // --- Boshqaruv ---
  document.getElementById("stPrev").onclick = function () { go(idx - 1); };
  document.getElementById("stNext").onclick = function () { go(idx + 1); };
  pp.onclick = function () { if (playing) pause(); else play(); };
  root.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { go(idx - 1); } else if (e.key === "ArrowRight") { go(idx + 1); }
    else if (e.key === " ") { e.preventDefault(); playing ? pause() : play(); }
  });

  // --- Ko'rinishda boshlash / chiqqanda pauza ---
  render();
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) {
          if (!started) { started = true; T("stories_view", {}); }
          play();
        } else { pause(); }
      });
    }, { threshold: 0.5 });
    io.observe(root);
  } else { play(); }  // zaxira
})();
