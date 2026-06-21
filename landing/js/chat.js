/* ============================================================
   chat.js — jonli bot vidjeti.
   - Har bir [data-openchat] tugma chatni ochadi
   - AI bilan suhbat (CONFIG.CHAT_API)
   - Lead-capture: ism+telefon -> CONFIG.LEAD_API + lead_submitted
   - Halol degradatsiya: backend yiqilsa, jim ssenariy EMAS — ochiq lead-forma
   - Hodisalar: chat_open, chat_message_sent, lead_submitted, telegram_click
   ============================================================ */
(function () {
  var C = window.CONFIG || {};
  var T = window.track || function () {};
  var root = document.getElementById("chatRoot");
  if (!root) return;

  // --- Holat ---
  var history = [];      // [{role, content}]
  var userMsgs = 0;
  var opened = false, openedOnce = false, busy = false;
  var leadShown = false, leadDone = false;
  var currentPlan = "";
  var bubbleShown = false;

  // --- DOM qurish ---
  root.innerHTML =
    '<button class="cfab" id="cFab" aria-label="Sotuv agenti bilan suhbat">' +
      '<span class="cav">🤖<i></i></span><span>Sinab ko\'ring</span></button>' +
    '<div class="cbubble" id="cBubble" role="status"><span class="x" id="cBubbleX" aria-label="Yopish">×</span>' +
      '<b>Salom! 👋</b> Qanaqa SIM kerakligini yozing — 30 soniyada tarif tanlab beraman.</div>' +
    '<div class="cwin" id="cWin" role="dialog" aria-modal="false" aria-label="Sotuv agenti chati">' +
      '<div class="cw-top"><span class="cav">🤖</span><div class="t"><b>Texnoset sotuvchi</b>' +
        '<small><i></i> onlayn · darrov javob</small></div>' +
        '<button class="cx" id="cClose" aria-label="Chatni yopish">×</button></div>' +
      '<div class="cw-body" id="cBody" aria-live="polite"></div>' +
      '<div class="cchips" id="cChips"></div>' +
      '<form class="cfoot" id="cForm" autocomplete="off">' +
        '<input id="cInput" placeholder="Xabar yozing…" aria-label="Xabar yozing" autocomplete="off">' +
        '<button type="submit" aria-label="Yuborish">➤</button></form>' +
    '</div>';

  var fab = byId("cFab"), bubble = byId("cBubble"), win = byId("cWin"),
      body = byId("cBody"), chips = byId("cChips"), form = byId("cForm"), input = byId("cInput");
  function byId(id){ return document.getElementById(id); }

  // --- Yordamchilar ---
  function esc(s){ return (s||"").replace(/[&<>]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c]; }); }
  function md(s){ return esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/\n/g,"<br>"); }
  function scroll(){ body.scrollTop = body.scrollHeight; }
  function addUser(t){ var d=document.createElement("div"); d.className="cmsg u"; d.textContent=t; body.appendChild(d); scroll(); }
  function addBot(html){ var d=document.createElement("div"); d.className="cmsg b"; d.innerHTML=html; body.appendChild(d); scroll(); return d; }
  function typing(){ var d=document.createElement("div"); d.className="ctyping"; d.innerHTML="<i></i><i></i><i></i>"; body.appendChild(d); scroll(); return d; }
  function setChips(arr){
    chips.innerHTML="";
    (arr||[]).forEach(function(c){
      var b=document.createElement("button");
      b.className="cchip"+(c.cta?" cta":""); b.type="button"; b.textContent=c.t;
      b.onclick=function(){ if(c.href){ openTg(c.href); return; } send(c.t); };
      chips.appendChild(b);
    });
  }
  function botSay(html, delay, cb){
    busy=true; setChips([]); var tp=typing();
    setTimeout(function(){ tp.remove(); addBot(html); busy=false; if(cb)cb(); }, delay||700);
  }
  function openTg(href){
    T("telegram_click", {source:"chat"});
    window.open(href || C.TELEGRAM, "_blank");
  }

  // --- Ochish / yopish ---
  function open(seedMsg){
    win.classList.add("open"); fab.classList.add("hide"); hideBubble();
    opened=true;
    if(!openedOnce){
      openedOnce=true;
      T("chat_open", {});
      boot(seedMsg);
    } else if (seedMsg) { send(seedMsg); }
    setTimeout(function(){ input.focus(); }, 250);
  }
  function close(){ win.classList.remove("open"); fab.classList.remove("hide"); opened=false; }
  window.openChat = open;   // main.js (exit-intent) uchun

  function boot(seedMsg){
    history=[]; userMsgs=0; leadShown=false; leadDone=false;
    botSay("Assalomu alaykum! 😊 Men Texnoset sotuv agenti — sizga mos SIM-tarifni tanlab beraman.<br>Nima qidiryapsiz?", 600, function(){
      setChips([{t:"📶 Internet ko'p"},{t:"💸 Arzonroq"},{t:"▶️ YouTube"}]);
      if (seedMsg) send(seedMsg);
    });
  }

  // --- Xabar yuborish ---
  function send(text){
    if(busy || !text || leadShown) return;
    addUser(text);
    history.push({role:"user", content:text});
    userMsgs++;
    T("chat_message_sent", {n:userMsgs});
    aiReply();
  }

  function intentBuy(t){
    return /(olaman|olamiz|bo'?ladi|xohlayman|kerak menga|sotib|buyurtma|qancha|narx|narxi|boshlay|ulang|ariza|telefon)/i.test(t||"");
  }

  // --- AI javobi (+ halol degradatsiya) ---
  function aiReply(){
    busy=true; setChips([]); var tp=typing();
    fetch(C.CHAT_API, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({messages: history})
    })
    .then(function(r){ if(!r.ok) throw new Error("http "+r.status); return r.json(); })
    .then(function(d){
      tp.remove(); busy=false;
      var reply = (d && (d.reply || d.message || d.content)) || "";
      if(!reply) throw new Error("empty");
      addBot(md(reply));
      history.push({role:"assistant", content:reply});
      // Lead so'rash sharti: yetarli xabar YOKI xarid niyati
      var last = history[history.length-1] ? "" : "";
      var lastUser = "";
      for (var i=history.length-1;i>=0;i--){ if(history[i].role==="user"){ lastUser=history[i].content; break; } }
      if(!leadDone && !leadShown && (userMsgs >= (C.CHAT&&C.CHAT.leadAfterMessages||3) || intentBuy(lastUser))){
        setTimeout(askLead, 600);
      } else {
        // suhbat davom etadi — tabiiy (majburiy CTA YO'Q)
      }
    })
    .catch(function(){
      tp.remove(); busy=false;
      // HALOL DEGRADATSIYA: jim ssenariy emas — ochiq holat + lead-forma
      addBot("Hozir operatorga ulayapman 🙌 Raqamingizni qoldiring — bir necha daqiqada o'zimiz bog'lanamiz va hammasini ko'rsatamiz.");
      T("chat_error", {});
      askLead(true);
    });
  }

  // --- Lead-forma (chat ichida) ---
  function askLead(isFallback){
    if(leadShown || leadDone) return;
    leadShown = true; setChips([]);
    if(!isFallback){
      addBot("Zo'r! 🎉 Sizga shaxsiy demo va narxlarni tayyorlab beramiz. Ismingiz va telefon raqamingizni qoldiring — operatorimiz darrov bog'lanadi:");
    }
    var wrap = document.createElement("div");
    wrap.className = "clead";
    wrap.innerHTML =
      '<p>📩 Bepul demo uchun ma\'lumotlaringiz:</p>' +
      '<input id="ldName" placeholder="Ismingiz" aria-label="Ism" autocomplete="name">' +
      '<input id="ldPhone" type="tel" placeholder="+998 __ ___ __ __" aria-label="Telefon" autocomplete="tel" inputmode="tel">' +
      '<div class="err" id="ldErr">Iltimos, ism va to\'g\'ri telefon raqamini kiriting.</div>' +
      '<button type="button" id="ldSend">Bog\'lanishni so\'rash →</button>' +
      '<small>🔒 Ma\'lumotingiz faqat siz bilan bog\'lanish uchun. Spam yo\'q.</small>';
    body.appendChild(wrap); scroll();
    var nm=byId("ldName"), ph=byId("ldPhone"), er=byId("ldErr"), bt=byId("ldSend");
    setTimeout(function(){ nm.focus(); }, 100);
    bt.onclick = function(){
      var name=(nm.value||"").trim();
      var phoneRaw=(ph.value||"").trim();
      var digits=phoneRaw.replace(/\D/g,"");
      if(name.length<2 || digits.length<9){ er.style.display="block"; return; }
      er.style.display="none"; bt.disabled=true; bt.textContent="Yuborilmoqda…";
      submitLead(name, phoneRaw, wrap, bt);
    };
    ph.addEventListener("keydown", function(e){ if(e.key==="Enter"){ bt.click(); } });
  }

  function submitLead(name, phone, wrap, bt){
    var payload = { name:name, phone:phone, source:"sayt-chat", plan: currentPlan || "" };
    var done = function(ok){
      leadDone = true; leadShown = false;
      wrap.remove();
      T("lead_submitted", {plan: currentPlan||"", ok: !!ok});
      addBot("Rahmat, <strong>"+esc(name)+"</strong>! ✅ Tez orada bog'lanamiz.<br>Tezroq bo'lsin desangiz — hoziroq Telegramda yozing 👇");
      setChips([{t:"✈️ Telegramda yozish", cta:true, href:C.TELEGRAM}]);
    };
    var sent = false, finish = function(ok){ if(sent) return; sent=true; done(ok); };
    if(!C.LEAD_API){ finish(false); return; }
    fetch(C.LEAD_API, {
      method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)
    }).then(function(r){ finish(r && r.ok); })
      .catch(function(){ finish(false); });
    // Tarmoq osilib qolsa ham foydalanuvchini ushlamaymiz:
    setTimeout(function(){ finish(false); }, 6000);
  }

  // --- Proaktiv bubble ---
  function showBubble(){
    if(bubbleShown || opened || !(C.FLAGS && C.FLAGS.proactiveBubble)) return;
    bubbleShown = true; bubble.classList.add("show");
  }
  function hideBubble(){ bubble.classList.remove("show"); }
  if(C.FLAGS && C.FLAGS.proactiveBubble){
    setTimeout(showBubble, (C.CHAT && C.CHAT.proactiveDelayMs) || 12000);
    window.addEventListener("scroll", function once(){
      if(window.scrollY > window.innerHeight*0.8){ showBubble(); window.removeEventListener("scroll", once); }
    }, {passive:true});
  }
  bubble.onclick = function(){ open(); };
  byId("cBubbleX").onclick = function(e){ e.stopPropagation(); hideBubble(); bubbleShown=true; };

  // --- Hodisa ulashlari ---
  fab.onclick = function(){ open(); };
  byId("cClose").onclick = close;
  form.addEventListener("submit", function(e){ e.preventDefault(); var v=input.value.trim(); if(v){ input.value=""; send(v); } });
  document.addEventListener("keydown", function(e){ if(e.key==="Escape" && opened) close(); });

  // Barcha [data-openchat] (sahifadagi har bir "Sinab ko'rish" -> SIM demo chat)
  document.querySelectorAll("[data-openchat]").forEach(function(b){
    b.addEventListener("click", function(e){ e.preventDefault(); open(); });
  });

  // ===== TARIF (xizmat reja) buyurtmasi — SIM chatga EMAS, to'g'ridan-to'g'ri buyurtma formasiga =====
  var PLAN_LABELS = { start:"START", biznes:"BIZNES", premium:"PREMIUM" };
  function planPriceText(plan){
    var p = (C.PRICES||{})[plan];
    if(!p) return "";
    try { return p.toLocaleString("ru-RU").replace(/[, ]/g," ") + " so'm/oy"; } catch(e){ return p + " so'm/oy"; }
  }
  var pmodal = document.createElement("div");
  pmodal.className = "pmodal";
  pmodal.innerHTML =
    '<div class="pm-back"></div>' +
    '<div class="pm-card" role="dialog" aria-modal="true" aria-label="Tarif buyurtmasi">' +
      '<button class="pm-x" type="button" aria-label="Yopish">×</button><div class="pm-body"></div></div>';
  document.body.appendChild(pmodal);
  var pmBody = pmodal.querySelector(".pm-body");
  function closePlan(){ pmodal.classList.remove("open"); }
  pmodal.querySelector(".pm-x").onclick = closePlan;
  pmodal.querySelector(".pm-back").onclick = closePlan;
  document.addEventListener("keydown", function(e){ if(e.key==="Escape") closePlan(); });

  function openPlanModal(plan){
    currentPlan = plan;
    T("plan_selected", {plan:plan});
    var label = PLAN_LABELS[plan] || plan.toUpperCase();
    var price = planPriceText(plan);
    pmBody.innerHTML =
      '<div class="pm-badge">🎉 Tanlandi</div>' +
      '<h3><strong>'+label+'</strong> tarifi'+(price?' <span class="pm-price">'+price+'</span>':'')+'</h3>' +
      '<p>Ism va telefon raqamingizni qoldiring — operatorimiz bog\'lanib, tarifni sozlab, ishga tushirib beradi.</p>' +
      '<input id="pmName" placeholder="Ismingiz" autocomplete="name" aria-label="Ism">' +
      '<input id="pmPhone" type="tel" placeholder="+998 __ ___ __ __" autocomplete="tel" inputmode="tel" aria-label="Telefon">' +
      '<div class="pm-err" id="pmErr">Iltimos, ism va to\'g\'ri telefon raqamini kiriting.</div>' +
      '<button class="pm-submit" id="pmSend" type="button">Bog\'lanishni so\'rash →</button>' +
      '<a class="pm-tg" href="'+C.TELEGRAM+'" target="_blank" rel="noopener">yoki Telegram orqali yozish ✈️</a>';
    pmodal.classList.add("open");
    var nm=byId("pmName"), ph=byId("pmPhone"), er=byId("pmErr"), bt=byId("pmSend");
    pmBody.querySelector(".pm-tg").onclick = function(){ T("telegram_click", {source:"plan"}); };
    setTimeout(function(){ nm.focus(); }, 80);
    bt.onclick = function(){
      var name=(nm.value||"").trim(), phone=(ph.value||"").trim();
      if(name.length<2 || phone.replace(/\D/g,"").length<9){ er.style.display="block"; return; }
      er.style.display="none"; bt.disabled=true; bt.textContent="Yuborilmoqda…";
      var sent=false, fin=function(ok){
        if(sent) return; sent=true;
        T("lead_submitted", {plan:plan, ok:!!ok, source:"plan"});
        pmBody.innerHTML =
          '<div class="pm-badge ok">✅ Qabul qilindi</div>' +
          '<h3>Rahmat, '+esc(name)+'!</h3>' +
          '<p>Operatorimiz <strong>'+label+'</strong> tarifini ulab berish uchun tez orada bog\'lanadi. Tezroq bo\'lsin desangiz — Telegramda yozing 👇</p>' +
          '<a class="pm-submit pm-tglink" href="'+C.TELEGRAM+'" target="_blank" rel="noopener">✈️ Telegramda yozish</a>';
        pmBody.querySelector(".pm-tglink").onclick = function(){ T("telegram_click", {source:"plan"}); };
      };
      if(!C.LEAD_API){ fin(false); return; }
      fetch(C.LEAD_API, {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({name:name, phone:phone, plan:plan, source:"narx-tarif"})})
        .then(function(r){ fin(r && r.ok); }).catch(function(){ fin(false); });
      setTimeout(function(){ fin(false); }, 6000);
    };
    ph.addEventListener("keydown", function(e){ if(e.key==="Enter") bt.click(); });
  }
  document.querySelectorAll("[data-plan-order]").forEach(function(b){
    b.addEventListener("click", function(e){ e.preventDefault(); openPlanModal(b.getAttribute("data-plan-order")); });
  });

  // Telegram / telefon linklari (CONFIG'dan + treking)
  document.querySelectorAll("[data-tg]").forEach(function(a){
    a.setAttribute("href", C.TELEGRAM);
    a.addEventListener("click", function(){ T("telegram_click", {source:"page"}); });
  });
  document.querySelectorAll("[data-phone]").forEach(function(a){
    a.setAttribute("href", "tel:"+(C.PHONE_TEL||""));
  });
})();
