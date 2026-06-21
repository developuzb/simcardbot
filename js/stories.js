/* ============================================================
   stories.js — "Tizim qanday ishlaydi" Instagram-uslub slayder.
   - Avto-aylanadi, progress barlar, yon ‹ › tugmalar, pauza
   - "Ovozli izoh" — o'zbekcha narratsiya (klip tugaganda keyingi slayd)
   - Ko'rinishda boshlanadi; suzuvchi chat tugmasi (FAB) vaqtincha yashirinadi
   ============================================================ */
(function () {
  var T = window.track || function () {};
  var V = "?v=3";
  var STEPS = [
    { img: "assets/story-1.jpg" + V, a: "assets/voice-1.mp3" + V, t: "Mijoz keladi",        d: "Mijoz SIM qidirib sizga yozadi — kechasimi, bayrammi, farqi yo'q." },
    { img: "assets/story-2.jpg" + V, a: "assets/voice-2.mp3" + V, t: "Chatga ulanadi",      d: "Bir tugma bilan AI bot suhbatni boshlaydi — siz band bo'lsangiz ham." },
    { img: "assets/story-3.jpg" + V, a: "assets/voice-3.mp3" + V, t: "AI gaplashadi",       d: "Bot o'zbekcha gaplashib, ehtiyojni so'rab, eng mos tarifni tavsiya qiladi." },
    { img: "assets/story-4.jpg" + V, a: "assets/voice-4.mp3" + V, t: "Buyurtma olinadi",    d: "Ism, telefon, manzil — hammasini o'zi so'rab, avtomatik yig'adi." },
    { img: "assets/story-5.jpg" + V, a: "assets/voice-5.mp3" + V, t: "Guruhga tushadi",     d: "Tayyor buyurtma operator va kuryer guruhingizga o'zi tushadi." },
    { img: "assets/story-6.jpg" + V, a: "assets/voice-6.mp3" + V, t: "Kuryer yetkazadi",    d: "Kuryer yetkazadi, mijoz xursand — siz faqat nazorat qilasiz." },
    { img: "assets/story-7.jpg" + V, a: "assets/voice-7.mp3" + V, t: "Siz dam olasiz",      d: "Siz dam olasiz yoki yangi g'oyalar ustida ishlaysiz — tizim o'zi sotaveradi." },
    { img: "assets/story-8.jpg" + V, a: "assets/voice-8.mp3" + V, t: "AI kunlik hisobot",   d: "Har kuni AI tayyor hisobot beradi: nechta buyurtma, qancha daromad." },
    { img: "assets/story-9.jpg" + V, a: "assets/voice-9.mp3" + V, t: "Har bir mijoz yodda", d: "Har bir mijoz haqida ma'lumot va AI insayt — hammasi bir joyda." }
  ];
  var DUR = 3600;  // ovozsiz rejimda har slayd (ms)

  var root = document.getElementById("stories");
  if (!root) return;
  var barsEl = document.getElementById("stBars"), slidesEl = document.getElementById("stSlides"),
      capEl = document.getElementById("stCap"), pp = document.getElementById("stPP"),
      soundBtn = document.getElementById("stSound");

  var idx = 0, raf = null, startTs = 0, elapsed = 0, playing = false, started = false, soundOn = false;

  // --- Audio (o'zbekcha narratsiya) ---
  var audio = new Audio();
  audio.preload = "none";
  audio.addEventListener("ended", function () { if (soundOn && playing) go(idx + 1); });
  audio.addEventListener("timeupdate", function () {
    if (soundOn && audio.duration && fills[idx]) fills[idx].style.width = (audio.currentTime / audio.duration * 100) + "%";
  });

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
  function clearRaf() { if (raf) { cancelAnimationFrame(raf); raf = null; } }
  function stopAudio() { try { audio.pause(); } catch (e) {} }
  function playAudio() { var p = audio.play(); if (p && p.catch) p.catch(function () {}); }

  function tick(ts) {
    if (!playing || soundOn) return;
    if (!startTs) startTs = ts;
    var cur = elapsed + (ts - startTs);
    var p = cur / DUR; if (p > 1) p = 1;
    fills[idx].style.width = (p * 100) + "%";
    if (p >= 1) { go(idx + 1); return; }
    raf = requestAnimationFrame(tick);
  }

  // Joriy slaydni boshidan boshlash
  function startCurrent() {
    clearRaf(); elapsed = 0; startTs = 0; stopAudio();
    if (soundOn && STEPS[idx].a) { audio.src = STEPS[idx].a; audio.currentTime = 0; playAudio(); }
    else { raf = requestAnimationFrame(tick); }
  }
  function setPlayIcon(on) { pp.textContent = on ? "⏸" : "▶"; pp.setAttribute("aria-label", on ? "To'xtatish" : "Davom ettirish"); }

  function play() { if (playing) return; playing = true; setPlayIcon(true); startCurrent(); }
  function resume() {  // pauzadan davom (slaydni qayta boshlamasdan)
    if (playing) return; playing = true; setPlayIcon(true);
    if (soundOn) playAudio();
    else { startTs = 0; raf = requestAnimationFrame(tick); }
  }
  function pause() {
    if (!playing) return; playing = false; clearRaf();
    if (soundOn) stopAudio();
    else if (startTs) { elapsed += (now() - startTs); startTs = 0; }
    setPlayIcon(false);
  }
  function go(i) {
    var loop = (i >= STEPS.length);
    idx = (i + STEPS.length) % STEPS.length;
    render();
    if (loop) T("stories_complete", {});
    if (!playing) { playing = true; setPlayIcon(true); }
    startCurrent();
  }

  // --- Ovozli izoh toggle ---
  function setSound(on) {
    soundOn = on;
    soundBtn.classList.toggle("on", on);
    soundBtn.textContent = on ? "🔊 Ovoz yoniq" : "🔈 Ovozli izoh";
    soundBtn.setAttribute("aria-label", on ? "Ovozni o'chirish" : "Ovozli izohni yoqish");
    if (on) { T("stories_sound", {}); idx = 0; render(); playing = true; setPlayIcon(true); startCurrent(); }
    else { stopAudio(); startCurrent(); }
  }
  if (soundBtn) soundBtn.onclick = function () { setSound(!soundOn); };

  // --- Boshqaruv ---
  document.getElementById("stPrev").onclick = function () { go(idx - 1); };
  document.getElementById("stNext").onclick = function () { go(idx + 1); };
  var aPrev = document.getElementById("stArrowPrev"), aNext = document.getElementById("stArrowNext");
  if (aPrev) aPrev.onclick = function (e) { e.stopPropagation(); go(idx - 1); };
  if (aNext) aNext.onclick = function (e) { e.stopPropagation(); go(idx + 1); };
  pp.onclick = function () { if (playing) pause(); else resume(); };
  root.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") go(idx - 1);
    else if (e.key === "ArrowRight") go(idx + 1);
    else if (e.key === " ") { e.preventDefault(); playing ? pause() : resume(); }
  });

  // Suzuvchi chat tugmasi (FAB) stories ko'rinishda yashirinadi — qoplab qolmasligi uchun
  function dimFab(on) {
    ["cFab", "cBubble"].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.classList.toggle("dim", on);
    });
  }

  // --- Ko'rinishda boshlash / chiqqanda pauza ---
  render();
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) {
          if (!started) { started = true; T("stories_view", {}); }
          if (!playing) resume();
          dimFab(true);
        } else { pause(); dimFab(false); }
      });
    }, { threshold: 0.5 });
    io.observe(root);
  } else { play(); }  // zaxira
})();
