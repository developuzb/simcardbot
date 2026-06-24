/* ============================================================
   chat.js — "Bepul sinab ko'rish" + tarif buyurtmasi lead modali.
   Jonli AI chat vidjeti OLIB TASHLANGAN (sotuv landing demosi).
   - [data-openchat]   -> "Bepul sinov" lead formasi (ism+telefon)
   - [data-plan-order] -> tarif (START/BIZNES/PREMIUM) lead formasi
   - Lead -> CONFIG.LEAD_API -> Telegram operator
   - [data-tg]/[data-phone] -> Telegram / telefon
   ============================================================ */
(function () {
  var C = window.CONFIG || {};
  var T = window.track || function () {};

  function byId(id){ return document.getElementById(id); }
  function esc(s){ return (s||"").replace(/[&<>]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c]; }); }

  var PLAN_LABELS = { start:"START", biznes:"BIZNES", premium:"PREMIUM" };
  function planPriceText(plan){
    var p = (C.PRICES||{})[plan];
    if(!p) return "";
    try { return p.toLocaleString("ru-RU").replace(/[, ]/g," ") + " so'm/oy"; } catch(e){ return p + " so'm/oy"; }
  }

  // --- Modal ---
  var pmodal = document.createElement("div");
  pmodal.className = "pmodal";
  pmodal.innerHTML =
    '<div class="pm-back"></div>' +
    '<div class="pm-card" role="dialog" aria-modal="true" aria-label="So\'rov">' +
      '<button class="pm-x" type="button" aria-label="Yopish">×</button><div class="pm-body"></div></div>';
  document.body.appendChild(pmodal);
  var pmBody = pmodal.querySelector(".pm-body");
  function closeModal(){ pmodal.classList.remove("open"); }
  pmodal.querySelector(".pm-x").onclick = closeModal;
  pmodal.querySelector(".pm-back").onclick = closeModal;
  document.addEventListener("keydown", function(e){ if(e.key==="Escape") closeModal(); });

  // Umumiy lead-forma: badge/title/desc + source/plan/okDesc
  function leadForm(o){
    pmBody.innerHTML =
      '<div class="pm-badge">'+o.badge+'</div>' +
      '<h3>'+o.title+'</h3>' +
      '<p>'+o.desc+'</p>' +
      '<input id="pmName" placeholder="Ismingiz" autocomplete="name" aria-label="Ism">' +
      '<input id="pmPhone" type="tel" placeholder="+998 __ ___ __ __" autocomplete="tel" inputmode="tel" aria-label="Telefon">' +
      '<div class="pm-err" id="pmErr">Iltimos, ism va to\'g\'ri telefon raqamini kiriting.</div>' +
      '<button class="pm-submit" id="pmSend" type="button">Bog\'lanishni so\'rash →</button>' +
      '<a class="pm-tg" href="'+C.TELEGRAM+'" target="_blank" rel="noopener">yoki Telegram orqali yozish ✈️</a>';
    pmodal.classList.add("open");
    var nm=byId("pmName"), ph=byId("pmPhone"), er=byId("pmErr"), bt=byId("pmSend");
    pmBody.querySelector(".pm-tg").onclick = function(){ T("telegram_click", {source:o.source}); };
    setTimeout(function(){ nm.focus(); }, 80);
    bt.onclick = function(){
      var name=(nm.value||"").trim(), phone=(ph.value||"").trim();
      if(name.length<2 || phone.replace(/\D/g,"").length<9){ er.style.display="block"; return; }
      er.style.display="none"; bt.disabled=true; bt.textContent="Yuborilmoqda…";
      var sent=false, fin=function(ok){
        if(sent) return; sent=true;
        T("lead_submitted", {plan:o.plan||"", ok:!!ok, source:o.source});
        pmBody.innerHTML =
          '<div class="pm-badge ok">✅ Qabul qilindi</div>' +
          '<h3>Rahmat, '+esc(name)+'!</h3>' +
          '<p>'+o.okDesc+'</p>' +
          '<a class="pm-submit pm-tglink" href="'+C.TELEGRAM+'" target="_blank" rel="noopener">✈️ Telegramda yozish</a>';
        pmBody.querySelector(".pm-tglink").onclick = function(){ T("telegram_click", {source:o.source}); };
      };
      if(!C.LEAD_API){ fin(false); return; }
      fetch(C.LEAD_API, {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({name:name, phone:phone, plan:o.plan||"", source:o.source})})
        .then(function(r){ fin(r && r.ok); }).catch(function(){ fin(false); });
      setTimeout(function(){ fin(false); }, 6000);
    };
    ph.addEventListener("keydown", function(e){ if(e.key==="Enter") bt.click(); });
  }

  // "Bepul sinab ko'rish" — bepul sinov so'rovi
  function openTrial(){
    T("trial_requested", {});
    leadForm({
      badge:"🎁 Bepul sinov",
      title:"Bepul sinab ko'ring",
      desc:"Ism va telefon raqamingizni qoldiring — AI sotuv tizimini biznesingizga <strong>bepul</strong> ulab, ishlatib ko'rsatamiz.",
      plan:"", source:"bepul-sinov",
      okDesc:"Operatorimiz tez orada bog'lanib, bepul sinovni ishga tushirib beradi."
    });
  }

  // Tarif (START/BIZNES/PREMIUM) buyurtmasi
  function openPlanModal(plan){
    T("plan_selected", {plan:plan});
    var label = PLAN_LABELS[plan] || String(plan).toUpperCase();
    var price = planPriceText(plan);
    leadForm({
      badge:"🎉 Tanlandi",
      title:'<strong>'+label+'</strong> tarifi'+(price?' <span class="pm-price">'+price+'</span>':''),
      desc:"Ism va telefon raqamingizni qoldiring — operatorimiz bog'lanib, tarifni sozlab, ishga tushirib beradi.",
      plan:plan, source:"narx-tarif",
      okDesc:"Operatorimiz <strong>"+label+"</strong> tarifini ulab berish uchun tez orada bog'lanadi."
    });
  }

  // --- Bindings ---
  document.querySelectorAll("[data-openchat]").forEach(function(b){
    b.addEventListener("click", function(e){ e.preventDefault(); openTrial(); });
  });
  document.querySelectorAll("[data-plan-order]").forEach(function(b){
    b.addEventListener("click", function(e){ e.preventDefault(); openPlanModal(b.getAttribute("data-plan-order")); });
  });
  document.querySelectorAll("[data-tg]").forEach(function(a){
    a.setAttribute("href", C.TELEGRAM);
    a.addEventListener("click", function(){ T("telegram_click", {source:"page"}); });
  });
  document.querySelectorAll("[data-phone]").forEach(function(a){
    a.setAttribute("href", "tel:"+(C.PHONE_TEL||""));
  });

  // main.js (exit-intent) uchun
  window.openChat = openTrial;
})();
