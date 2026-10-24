/* AccessHK demo shell logic — plain JS, no frameworks.
   Two selects, one button, two route cards: deliberately simple.

   Runs in two modes from the same files:
   * backend mode (default): FastAPI at /api/...
   * static mode (GitHub Pages build): detects stations.json and uses
     precomputed data; live bus ETA is fetched DIRECTLY from
     rt.data.gov.hk (the API sends Access-Control-Allow-Origin: *). */

const $ = (id) => document.getElementById(id);

const BUS_API = "https://rt.data.gov.hk/v1/transport/mtr/bus/getSchedule";
let STATIC_MODE = false;
let BUS_DATA = null;

async function detectMode() {
  try {
    const r = await fetch("stations.json", { method: "HEAD" });
    STATIC_MODE = r.ok;
  } catch (e) { STATIC_MODE = false; }
}

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
    insTitle: "數據洞察",
    insLead: (k, n) => `${n} 個車站按無障礙特徵自動分為 ${k} 類（自寫 k-means 演算法）`,
    insWeakTitle: "最需改善的車站",
    insBench: (pct) => `A* 導航平均比戴克斯特拉少探討 ${pct}% 節點`,
    stations: "站",
    busTitle: "接駁巴士實時到站",
    busNext: (t) => `下一班 ${t}`,
    busSuspended: "暫停服務",
    busLive: "實時數據",
    busCached: "離線快取（演示用）",
    busEmpty: "此時段暫無預報班次",
    busSrc: (src, at, fare) => {
      const s = src === "live" ? "實時數據 rt.data.gov.hk" : "離線快照（非實時）";
      const f = fare ? ` · 長者/傷殘 $${fare.octopus_elderly}` : "";
      return `${s} · ${at}${f}`;
    },
    fareLine: (f) => {
      if (!f) return "";
      const bits = [`成人 $${f.octopus_adult}`];
      if (f.octopus_elderly != null) bits.push(`長者 $${f.octopus_elderly}`);
      if (f.octopus_pwd != null) bits.push(`傷殘 $${f.octopus_pwd}`);
      const note = f.note === "airport_express" ? "（機場快綫票價）" : "";
      return `八達通車費：${bits.join(" · ")} ${note}`;
    },
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
    insTitle: "Data insights",
    insLead: (k, n) => `${n} stations grouped into ${k} tiers (hand-written k-means)`,
    insWeakTitle: "Stations needing most work",
    insBench: (pct) => `A* explores ${pct}% fewer nodes than Dijkstra on average`,
    stations: "stations",
    busTitle: "Live feeder-bus arrivals",
    busNext: (t) => `Next ${t}`,
    busSuspended: "suspended",
    busLive: "live",
    busCached: "cached (demo)",
    busEmpty: "no departures predicted right now",
    busSrc: (src, at, fare) => {
      const s = src === "live" ? "live · rt.data.gov.hk" : "cached snapshot (not live)";
      const f = fare ? ` · elderly/PWD $${fare.octopus_elderly}` : "";
      return `${s} · ${at}${f}`;
    },
    fareLine: (f) => {
      if (!f) return "";
      const bits = [`adult $${f.octopus_adult}`];
      if (f.octopus_elderly != null) bits.push(`elderly $${f.octopus_elderly}`);
      if (f.octopus_pwd != null) bits.push(`PWD $${f.octopus_pwd}`);
      const note = f.note === "airport_express" ? " (Airport Express)" : "";
      return `Octopus fare: ${bits.join(" · ")}${note}`;
    },
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
  $("insTitle").textContent = t.insTitle;
  $("insWeakTitle").textContent = t.insWeakTitle;
  $("busTitle").textContent = t.busTitle;
  $("langBtn").textContent = lang === "zh" ? "EN" : "中文";
  if (lastInsights) renderInsights(lastInsights);
  if (lastBus) renderBus(lastBus);
}

async function loadStations() {
  const res = await fetch(STATIC_MODE ? "stations.json" : "/api/stations");
  const stations = await res.json();
  for (const sel of [$("fromSel"), $("toSel")]) {
    sel.innerHTML = "";
    for (const st of stations) {
      const opt = document.createElement("option");
      opt.value = st.sid ?? st.name_en;
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
  const fromId = $("fromSel").value, toId = $("toSel").value;
  let data = null;
  try {
    if (STATIC_MODE) {
      const res = await fetch(`routes/${encodeURIComponent(fromId)}.json`);
      if (!res.ok) throw new Error("origin data missing");
      const perOrigin = await res.json();
      data = perOrigin.pairs[toId] || null;
    } else {
      const res = await fetch(`/api/route?from=${encodeURIComponent(fromId)}&to=${encodeURIComponent(toId)}`);
      if (!res.ok) throw new Error(await res.text());
      data = await res.json();
    }
  } catch (e) {
    alert(lang === "zh" ? "查詢失敗，請檢查網絡後重試。" : "Query failed, check the network and retry.");
    return;
  }
  if (!data || !data.fastest) {
    alert(lang === "zh" ? "此組合暫無可用路線。" : "No route available for this pair.");
    return;
  }
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
  const fareEl = $("fareLine");
  if (data.fares) {
    fareEl.hidden = false;
    fareEl.textContent = t.fareLine(data.fares);
  } else fareEl.hidden = true;
  $("results").scrollIntoView({ behavior: "smooth" });
}

let lastInsights = null;
let lastBus = null;

function renderBus(data) {
  const t = L[lang];
  $("busCard").hidden = false;
  const list = $("busStops");
  list.innerHTML = "";
  if (!data.stops.length) {
    const li = document.createElement("li");
    li.textContent = t.busEmpty;
    list.appendChild(li);
  }
  for (const stop of data.stops.slice(0, 5)) {
    const li = document.createElement("li");
    const name = lang === "zh" ? stop.name_zh : stop.name_en;
    const next = stop.suspended
      ? t.busSuspended
      : (stop.arrivals[0] ? t.busNext(stop.arrivals[0].text) : "—");
    li.innerHTML = `<strong>${name}</strong><br>${next}`;
    list.appendChild(li);
  }
  $("busSrc").textContent =
    t.busSrc(data.source, (data.fetched_at || "").slice(11, 16), data.fares);
}

function summarizeBus(raw, stops) {
  return (raw.busStop || []).map((s) => ({
    stop_id: s.busStopId,
    name_en: (stops[s.busStopId] || {}).name_en || s.busStopId,
    name_zh: (stops[s.busStopId] || {}).name_zh || s.busStopId,
    suspended: s.isSuspended === "1",
    arrivals: (s.bus || []).slice(0, 3).map((b) => ({
      text: b.arrivalTimeText || "",
      in_minutes: Math.round((+b.arrivalTimeInSecond || 0) / 60),
      is_scheduled: b.isScheduled === "1",
      is_delayed: b.isDelayed === "1",
    })),
  }));
}

function localIso() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}` +
         `T${p(d.getHours())}:${p(d.getMinutes())}:00+08:00`;
}

async function loadBusRoutes() {
  try {
    if (STATIC_MODE) {
      const res = await fetch("bus_data.json");
      if (!res.ok) return;
      BUS_DATA = await res.json();
    } else {
      const res = await fetch("/api/bus-routes");
      if (!res.ok) return;
      BUS_DATA = await res.json();
    }
    if (!BUS_DATA.routes.length) return;
    $("busCard").hidden = false;
    const chips = $("busChips");
    chips.innerHTML = "";
    for (const r of BUS_DATA.routes) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip chipBtn";
      chip.textContent = r;
      chip.addEventListener("click", () => selectBus(r, chips));
      chips.appendChild(chip);
    }
    selectBus(BUS_DATA.routes.includes("K12") ? "K12" : BUS_DATA.routes[0], chips);
  } catch (e) { /* bus card stays hidden */ }
}

async function selectBus(route, chips) {
  for (const c of chips.children) {
    c.classList.toggle("active", c.textContent === route);
  }
  try {
    if (STATIC_MODE) {
      // direct browser call: rt.data.gov.hk sends Access-Control-Allow-Origin: *
      const res = await fetch(BUS_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: lang === "zh" ? "zh" : "en", routeName: route }),
      });
      if (!res.ok) return;
      const raw = await res.json();
      lastBus = {
        route,
        source: "live",
        fetched_at: localIso(),
        refresh_seconds: +raw.appRefreshTimeInSecond || 60,
        stops: summarizeBus(raw, BUS_DATA.stops || {}),
        fares: (BUS_DATA.fares || {})[route],
      };
    } else {
      const res = await fetch(`/api/bus-eta?route=${encodeURIComponent(route)}&lang=${lang === "zh" ? "zh" : "en"}`);
      if (!res.ok) return;
      lastBus = await res.json();
    }
    renderBus(lastBus);
  } catch (e) { /* keep previous render */ }
}

function renderInsights(data) {
  const t = L[lang];
  $("insights").hidden = false;
  $("insLead").textContent =
    t.insLead(data.kmeans.chosen_k, data.meta.n_stations);

  const chips = $("insClusters");
  chips.innerHTML = "";
  for (const c of data.clusters) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = lang === "zh"
      ? `${c.label_zh} · ${c.size} ${t.stations}`
      : `${c.label_en} · ${c.size} ${t.stations}`;
    chips.appendChild(chip);
  }

  const weak = $("insWeak");
  weak.innerHTML = "";
  for (const st of data.gaps.bottom.slice(0, 5)) {
    const li = document.createElement("li");
    const name = lang === "zh" ? st.name_zh : st.name_en;
    li.textContent = `${name} — ${st.score}`;
    weak.appendChild(li);
  }

  $("insBench").textContent = t.insBench(data.benchmark.nodes_saved_pct);
}

async function loadAnalysis() {
  try {
    const res = await fetch(STATIC_MODE ? "analysis.json" : "/api/analysis");
    if (!res.ok) return;
    lastInsights = await res.json();
    renderInsights(lastInsights);
  } catch (e) { /* card stays hidden when the API is unreachable */ }
}

$("planForm").addEventListener("submit", planRoute);
$("langBtn").addEventListener("click", async () => {
  lang = lang === "zh" ? "en" : "zh";
  applyLang();
  await loadStations();
});

applyLang();
detectMode().then(() => {
  loadStations();
  loadAnalysis();
  loadBusRoutes();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
