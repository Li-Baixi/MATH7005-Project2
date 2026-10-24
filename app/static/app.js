/* AccessHK demo shell logic — plain JS, no frameworks.
   Two selects, one button, two route cards: deliberately simple. */

const $ = (id) => document.getElementById(id);

const L = {
  zh: {
    tagline: "無障礙出行規劃 · 全程免樓梯",
    from: "起點", to: "終點", go: "規劃路線",
    fastest: "最快路線", stepfree: "無障礙路線 ✓ 全程免樓梯",
    minutes: "分鐘", transfers: "次轉綫",
    ride: (s) => `乘 ${s.line} 綫：${s.board} → ${s.alight}（${s.stops} 站）`,
    transfer: (s) => `於 ${s.board} 轉綫`,
    enter: "入站建議", exit: "出站建議",
    via: "經", unnamed: "官方數據標記為無障礙（未具名入口）",
    fallbackTitle: "無障礙路線暫不可行",
    fallbackBody: (side, st, km) =>
      `此${side}車站未達全程無障礙標準。最近的無障礙車站：${st}（約 ${km} 公里）。`,
    originWord: "起點", destWord: "終點",
    src: "資料來源：data.gov.hk 港鐵路綫及無障礙設施開放數據（每月更新）",
  },
  en: {
    tagline: "Barrier-free journeys · step-free end to end",
    from: "From", to: "To", go: "Find route",
    fastest: "Fastest route", stepfree: "Step-free route ✓",
    minutes: "min", transfers: "transfer(s)",
    ride: (s) => `${s.line} line: ${s.board} → ${s.alight} (${s.stops} stops)`,
    transfer: (s) => `Change at ${s.board}`,
    enter: "Entrance advice", exit: "Exit advice",
    via: "via", unnamed: "official data marks step-free access (unnamed entrance)",
    fallbackTitle: "Step-free route not possible",
    fallbackBody: (side, st, km) =>
      `This ${side} is not step-free end to end. Nearest accessible station: ${st} (~${km} km).`,
    originWord: "origin", destWord: "destination",
    src: "Data: data.gov.hk — MTR routes & barrier-free facilities (monthly)",
  },
};
let lang = "zh";

function applyLang() {
  const t = L[lang];
  $("tagline").textContent = t.tagline;
  $("fromLbl").textContent = t.from;
  $("toLbl").textContent = t.to;
  $("goBtn").textContent = t.go;
  $("fastTitle").textContent = t.fastest;
  $("sfTitle").textContent = t.stepfree;
  $("fbTitle").textContent = t.fallbackTitle;
  $("srcNote").textContent = t.src;
  $("langBtn").textContent = lang === "zh" ? "EN" : "中文";
}

async function loadStations() {
  const res = await fetch("/api/stations");
  const stations = await res.json();
  for (const sel of [$("fromSel"), $("toSel")]) {
    sel.innerHTML = "";
    for (const st of stations) {
      const opt = document.createElement("option");
      opt.value = st.name_en;
      const label = lang === "zh"
        ? `${st.name_zh} ${st.step_free ? "♿" : ""}`
        : `${st.name_en}${st.step_free ? " ♿" : ""}`;
      opt.textContent = label;
      sel.appendChild(opt);
    }
  }
}

function renderItinerary(it, stepsEl, timeEl) {
  const t = L[lang];
  const fmt = (n) => (lang === "zh" ? `${Math.round(n)} ${t.minutes}` : `${Math.round(n)} ${t.minutes}`);
  timeEl.textContent = `${fmt(it.total_minutes)} · ${it.transfers} ${t.transfers}`;
  stepsEl.innerHTML = "";
  for (const s of it.segments) {
    const li = document.createElement("li");
    if (s.kind === "ride") li.textContent = t.ride(s);
    else { li.textContent = t.transfer(s); li.className = "transfer"; }
    stepsEl.appendChild(li);
  }
}

function renderAdvice(el, access, title) {
  const t = L[lang];
  if (!access.length) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<strong>${title}</strong><br>` + access.map((a) =>
    `♿ ${a.exit} — ${a.how === "step-free access" ? t.unnamed : `${t.via} ${a.how}`}`
  ).join("<br>");
}

async function planRoute(ev) {
  ev.preventDefault();
  const res = await fetch(`/api/route?from=${encodeURIComponent($("fromSel").value)}&to=${encodeURIComponent($("toSel").value)}`);
  if (!res.ok) { alert(await res.text()); return; }
  const data = await res.json();
  const t = L[lang];
  $("results").hidden = false;

  renderItinerary(data.fastest, $("fastSteps"), $("fastTime"));
  if (data.step_free) {
    $("sfCard").hidden = false;
    $("fbCard").hidden = true;
    renderItinerary(data.step_free, $("sfSteps"), $("sfTime"));
    renderAdvice($("sfAdvice"), [
      ...(data.step_free.origin_access || []).map(a => ({ ...a, exit: `${t.enter}: ${a.exit}` })),
      ...(data.step_free.destination_access || []).map(a => ({ ...a, exit: `${t.exit}: ${a.exit}` })),
    ].slice(0, 4), "");
  } else {
    $("sfCard").hidden = true;
    $("fbCard").hidden = false;
    const fb = data.fallback || {};
    let body = lang === "zh"
      ? "此路線無法保證全程無障礙。"
      : "This journey cannot be guaranteed step-free.";
    if (fb.origin) body += "<br>" + t.fallbackBody(t.originWord, fb.origin.station, fb.origin.distance_km);
    if (fb.destination) body += "<br>" + t.fallbackBody(t.destWord, fb.destination.station, fb.destination.distance_km);
    $("fbBody").innerHTML = body;
  }
  $("results").scrollIntoView({ behavior: "smooth" });
}

$("planForm").addEventListener("submit", planRoute);
$("langBtn").addEventListener("click", async () => {
  lang = lang === "zh" ? "en" : "zh";
  applyLang();
  await loadStations();
});

applyLang();
loadStations();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
