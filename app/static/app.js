/* AccessHK demo shell logic — plain JS, no frameworks.
   Trilingual (繁/簡/EN), location-aware, deliberately simple.

   Runs in two modes from the same files:
   * backend mode (default): FastAPI at /api/...
   * static mode (GitHub Pages build): detects stations.json and uses
     precomputed data; live bus ETA is fetched DIRECTLY from
     rt.data.gov.hk (the API sends Access-Control-Allow-Origin: *). */

const $ = (id) => document.getElementById(id);

const BUS_API = "https://rt.data.gov.hk/v1/transport/mtr/bus/getSchedule";
let STATIC_MODE = false;
let BUS_DATA = null;
let STATIONS = [];            // picker data (sid, trilingual names, coords)
const NAME_BY_EN = {};        // name_en -> display names for itineraries

const zhName = (st) => (lang === "zhcn" ? st.name_zh_cn : st.name_zh) || st.name_zh;
const N = (nameEn) => {
  const m = NAME_BY_EN[nameEn];
  if (!m) return nameEn;
  return lang === "en" ? m.en : lang === "zhcn" ? m.cn : m.zh;
};

/* MTR line codes -> official trilingual names */
const LINE_L10N = {
  ISL: { zh: "港島綫", zhcn: "港岛线", en: "Island line" },
  TWL: { zh: "荃灣綫", zhcn: "荃湾线", en: "Tsuen Wan line" },
  KTL: { zh: "觀塘綫", zhcn: "观塘线", en: "Kwun Tong line" },
  TKL: { zh: "將軍澳綫", zhcn: "将军澳线", en: "Tseung Kwan O line" },
  EAL: { zh: "東鐵綫", zhcn: "东铁线", en: "East Rail line" },
  TML: { zh: "屯馬綫", zhcn: "屯马线", en: "Tuen Ma line" },
  TCL: { zh: "東涌綫", zhcn: "东涌线", en: "Tung Chung line" },
  AEL: { zh: "機場快綫", zhcn: "机场快线", en: "Airport Express" },
  DRL: { zh: "迪士尼綫", zhcn: "迪士尼线", en: "Disneyland Resort line" },
  SIL: { zh: "南港島綫", zhcn: "南港岛线", en: "South Island line" },
};
const lineName = (code) => {
  const m = LINE_L10N[code];
  if (!m) return lang === "en" ? `${code} line` : code;
  if (lang === "en") return `${m.en} (${code})`;
  return lang === "zhcn" ? `${code} 线（${m.zhcn}）` : `${code} 綫（${m.zh}）`;
};

/* Facility descriptions arrive as the English labels from the Python
   core (ITEM_LABELS); localise them here.  Tolerates both payload
   shapes ("how" and the older "via") for cached/offline data. */
const HOW_L10N = {
  "same-level entrance": { zh: "同層入口", zhcn: "同层入口" },
  "ramp": { zh: "斜道", zhcn: "坡道" },
  "lift (street to concourse)": { zh: "升降機（街道至大堂）", zhcn: "电梯（街道至大堂）" },
  "lift (non-MTR managed)": { zh: "升降機（非港鐵管理）", zhcn: "电梯（非港铁管理）" },
  "stair lift": { zh: "樓梯升降機", zhcn: "楼梯电梯" },
  "stair lift (non-MTR managed)": { zh: "樓梯升降機（非港鐵管理）", zhcn: "楼梯电梯（非港铁管理）" },
  "lift (concourse to platform)": { zh: "升降機（大堂至月台）", zhcn: "电梯（大堂至站台）" },
  "vertical lifting platform": { zh: "垂直升降台", zhcn: "垂直升降台" },
  "step-free access": { zh: "無障礙通道", zhcn: "无障碍通道" },
};
const howLabel = (a) => {
  const raw = a.how || a.via || "";
  if (lang === "en") return raw;
  return (HOW_L10N[raw] || {})[lang === "zhcn" ? "zhcn" : "zh"] || raw;
};

const L = {
  zh: {
    tagline: "無障礙出行規劃 · 全程免樓梯",
    from: "起點", to: "終點", go: "規劃路線",
    fastest: "最快路線", stepfree: "無障礙路線 ✓ 全程免樓梯",
    minutes: "分鐘", transfers: "次轉綫",
    ride: (s) => `乘 ${lineName(s.line)}：${N(s.board)} → ${N(s.alight)}（${s.stops} 站）`,
    transfer: (s) => `於 ${N(s.board)} 轉綫`,
    enter: "入站建議", exit: "出站建議",
    unnamed: "官方數據標記為無障礙（未具名入口）",
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
    locate: "📍 使用我的位置", locating: "定位中…",
    locFail: "無法取得定位，請允許位置權限",
    locFound: (st, km) => `已設起點：${st}（最近的港鐵站，約 ${km} 公里）`,
    queryFail: "查詢失敗，請檢查網絡後重試。",
    noRoute: "此組合暫無可用路線。",
  },
  zhcn: {
    tagline: "无障碍出行规划 · 全程免楼梯",
    from: "起点", to: "终点", go: "规划路线",
    fastest: "最快路线", stepfree: "无障碍路线 ✓ 全程免楼梯",
    minutes: "分钟", transfers: "次转线",
    ride: (s) => `乘 ${lineName(s.line)}：${N(s.board)} → ${N(s.alight)}（${s.stops} 站）`,
    transfer: (s) => `于 ${N(s.board)} 转线`,
    enter: "入站建议", exit: "出站建议",
    unnamed: "官方数据标记为无障碍（未具名入口）",
    fallbackTitle: "无障碍路线暂不可行",
    fallbackBody: (side, st, km) =>
      `此${side}车站未达全程无障碍标准。最近的无障碍车站：${st}（约 ${km} 公里）。`,
    originWord: "起点", destWord: "终点",
    src: "数据来源：data.gov.hk 港铁路线及无障碍设施开放数据（每月更新）",
    insTitle: "数据洞察",
    insLead: (k, n) => `${n} 个车站按无障碍特征自动分为 ${k} 类（自写 k-means 算法）`,
    insWeakTitle: "最需改善的车站",
    insBench: (pct) => `A* 导航平均比戴克斯特拉少探讨 ${pct}% 节点`,
    stations: "站",
    busTitle: "接驳巴士实时到站",
    busNext: (t) => `下一班 ${t}`,
    busSuspended: "暂停服务",
    busEmpty: "此时段暂无预报班次",
    busSrc: (src, at, fare) => {
      const s = src === "live" ? "实时数据 rt.data.gov.hk" : "离线快照（非实时）";
      const f = fare ? ` · 长者/伤残 $${fare.octopus_elderly}` : "";
      return `${s} · ${at}${f}`;
    },
    fareLine: (f) => {
      if (!f) return "";
      const bits = [`成人 $${f.octopus_adult}`];
      if (f.octopus_elderly != null) bits.push(`长者 $${f.octopus_elderly}`);
      if (f.octopus_pwd != null) bits.push(`伤残 $${f.octopus_pwd}`);
      const note = f.note === "airport_express" ? "（机场快线票价）" : "";
      return `八达通车费：${bits.join(" · ")} ${note}`;
    },
    locate: "📍 使用我的位置", locating: "定位中…",
    locFail: "无法取得定位，请允许位置权限",
    locFound: (st, km) => `已设起点：${st}（最近的港铁站，约 ${km} 公里）`,
    queryFail: "查询失败，请检查网络后重试。",
    noRoute: "此组合暂无可用路线。",
  },
  en: {
    tagline: "Barrier-free journeys · step-free end to end",
    from: "From", to: "To", go: "Find route",
    fastest: "Fastest route", stepfree: "Step-free route ✓",
    minutes: "min", transfers: "transfer(s)",
    ride: (s) => `${lineName(s.line)}: ${N(s.board)} → ${N(s.alight)} (${s.stops} stops)`,
    transfer: (s) => `Change at ${N(s.board)}`,
    enter: "Entrance advice", exit: "Exit advice",
    unnamed: "official data marks step-free access (unnamed entrance)",
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
    locate: "📍 Use my location", locating: "Locating…",
    locFail: "Could not get your location — allow location permission",
    locFound: (st, km) => `Origin set: ${st} (nearest MTR station, ~${km} km)`,
    queryFail: "Query failed, check the network and retry.",
    noRoute: "No route available for this pair.",
  },
};
let lang = "zh";

async function detectMode() {
  try {
    const r = await fetch("stations.json", { method: "HEAD" });
    STATIC_MODE = r.ok;
  } catch (e) { STATIC_MODE = false; }
}

function applyLang() {
  const t = L[lang];
  document.documentElement.lang =
    lang === "zh" ? "zh-Hant" : lang === "zhcn" ? "zh-Hans" : "en";
  $("tagline").textContent = t.tagline;
  $("fromLbl").textContent = t.from;
  $("toLbl").textContent = t.to;
  $("goBtn").textContent = t.go;
  $("locBtn").textContent = t.locate;
  $("fastTitle").textContent = t.fastest;
  $("sfTitle").textContent = t.stepfree;
  $("fbTitle").textContent = t.fallbackTitle;
  $("srcNote").textContent = t.src;
  $("insTitle").textContent = t.insTitle;
  $("insWeakTitle").textContent = t.insWeakTitle;
  $("busTitle").textContent = t.busTitle;
  for (const b of document.querySelectorAll(".langBtn")) {
    b.classList.toggle("active", b.dataset.lang === lang);
  }
  if (lastInsights) renderInsights(lastInsights);
  if (lastBus) renderBus(lastBus);
  populateStations();
}

function sortStations(list) {
  const key = lang === "en" ? "name_en" : lang === "zhcn" ? "name_zh_cn" : "name_zh";
  const locale = lang === "en" ? "en" : lang === "zhcn" ? "zh-Hans" : "zh-Hant";
  return [...list].sort((a, b) => a[key].localeCompare(b[key], locale));
}

function populateStations() {
  for (const sel of [$("fromSel"), $("toSel")]) {
    const prev = sel.value;
    sel.innerHTML = "";
    for (const st of sortStations(STATIONS)) {
      const opt = document.createElement("option");
      opt.value = st.sid;
      const label = lang === "en"
        ? `${st.name_en}${st.step_free ? " ♿" : ""}`
        : `${zhName(st)} ${st.step_free ? "♿" : ""}`;
      opt.textContent = label;
      sel.appendChild(opt);
    }
    if (prev) sel.value = prev;
  }
}

async function loadStations() {
  const res = await fetch(STATIC_MODE ? "stations.json" : "/api/stations");
  STATIONS = await res.json();
  for (const st of STATIONS) {
    NAME_BY_EN[st.name_en] = { en: st.name_en, zh: st.name_zh, cn: st.name_zh_cn || st.name_zh };
  }
  populateStations();
  // prefill a demonstrative pair so the first tap shows the product's point
  const byEn = (name) => STATIONS.find((s) => s.name_en === name)?.sid;
  $("fromSel").value = byEn("Central") || STATIONS[0].sid;
  $("toSel").value = byEn("Fortress Hill") || STATIONS[1].sid;
}

/* --- geolocation: nearest MTR station becomes the origin --- */

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371.0088, rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad, dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function locateMe() {
  const t = L[lang];
  const note = $("locNote");
  note.hidden = false;
  note.textContent = t.locating;
  if (!navigator.geolocation) { note.textContent = t.locFail; return; }
  navigator.geolocation.getCurrentPosition((pos) => {
    let best = null, bestKm = Infinity;
    for (const st of STATIONS) {
      if (st.lat == null || st.lon == null) continue;
      const km = haversineKm(pos.coords.latitude, pos.coords.longitude, st.lat, st.lon);
      if (km < bestKm) { bestKm = km; best = st; }
    }
    if (!best) { note.textContent = t.locFail; return; }
    $("fromSel").value = best.sid;
    note.textContent = t.locFound(
      lang === "en" ? best.name_en : zhName(best), bestKm.toFixed(1));
  }, () => { note.textContent = t.locFail; },
  { timeout: 8000, maximumAge: 60000 });
}

/* --- itinerary rendering --- */

function renderItinerary(it, stepsEl, timeEl) {
  const t = L[lang];
  const fmt = (n) => `${Math.round(n)} ${t.minutes}`;
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
  el.innerHTML = `<strong>${title}</strong><br>` + access.map((a) => {
    const how = a.how || a.via || "";
    const label = how === "step-free access"
      ? (lang === "en" ? t.unnamed : HOW_L10N["step-free access"][lang === "zhcn" ? "zhcn" : "zh"])
      : howLabel(a);
    return `♿ ${N(a.exit)} — ${label}`;
  }).join("<br>");
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
    alert(L[lang].queryFail);
    return;
  }
  if (!data || !data.fastest) {
    alert(L[lang].noRoute);
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
      : lang === "zhcn"
        ? "此路线无法保证全程无障碍。"
        : "This journey cannot be guaranteed step-free.";
    if (fb.origin) body += "<br>" + t.fallbackBody(t.originWord, N(fb.origin.station), fb.origin.distance_km);
    if (fb.destination) body += "<br>" + t.fallbackBody(t.destWord, N(fb.destination.station), fb.destination.distance_km);
    $("fbBody").innerHTML = body;
  }
  const fareEl = $("fareLine");
  if (data.fares) {
    fareEl.hidden = false;
    fareEl.textContent = t.fareLine(data.fares);
  } else fareEl.hidden = true;
  $("results").scrollIntoView({ behavior: "smooth" });
}

/* --- analytics card --- */

let lastInsights = null;

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
    chip.textContent = lang === "en"
      ? `${c.label_en} · ${c.size} ${t.stations}`
      : lang === "zhcn"
        ? `${c.label_zh_cn || c.label_zh} · ${c.size} ${t.stations}`
        : `${c.label_zh} · ${c.size} ${t.stations}`;
    chips.appendChild(chip);
  }

  const weak = $("insWeak");
  weak.innerHTML = "";
  for (const st of data.gaps.bottom.slice(0, 5)) {
    const li = document.createElement("li");
    li.textContent = `${lang === "en" ? st.name_en : lang === "zhcn" ? (st.name_zh_cn || st.name_zh) : st.name_zh} — ${st.score}`;
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

/* --- feeder-bus card --- */

let lastBus = null;

function summarizeBus(raw, stops) {
  return (raw.busStop || []).map((s) => ({
    stop_id: s.busStopId,
    name_en: (stops[s.busStopId] || {}).name_en || s.busStopId,
    name_zh: (stops[s.busStopId] || {}).name_zh || s.busStopId,
    name_zh_cn: (stops[s.busStopId] || {}).name_zh_cn || (stops[s.busStopId] || {}).name_zh || s.busStopId,
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
    const name = lang === "en" ? stop.name_en
      : lang === "zhcn" ? (stop.name_zh_cn || stop.name_zh) : stop.name_zh;
    const next = stop.suspended
      ? t.busSuspended
      : (stop.arrivals[0] ? t.busNext(stop.arrivals[0].text) : "—");
    li.innerHTML = `<strong>${name}</strong><br>${next}`;
    list.appendChild(li);
  }
  $("busSrc").textContent =
    t.busSrc(data.source, (data.fetched_at || "").slice(11, 16), data.fares);
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
        body: JSON.stringify({ language: lang === "en" ? "en" : "zh", routeName: route }),
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
      const res = await fetch(`/api/bus-eta?route=${encodeURIComponent(route)}&lang=${lang === "en" ? "en" : "zh"}`);
      if (!res.ok) return;
      lastBus = await res.json();
    }
    renderBus(lastBus);
  } catch (e) { /* keep previous render */ }
}

/* --- wiring --- */

$("planForm").addEventListener("submit", planRoute);
$("locBtn").addEventListener("click", locateMe);
for (const b of document.querySelectorAll(".langBtn")) {
  b.addEventListener("click", () => { lang = b.dataset.lang; applyLang(); });
}

applyLang();
detectMode().then(() => {
  loadStations();
  loadAnalysis();
  loadBusRoutes();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
