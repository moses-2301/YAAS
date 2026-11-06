/* ═══════════════════════════ home: trending ideas ═══════════════════════════ */
const SRC_COLORS = { google: "#5cc8ff", wikipedia: "#f3f3f3", hackernews: "#ff9a3d", spaceflight: "#a98bff", arxiv: "#38ffb3" };
let trends = null, trendNiche = "all";

const NICHE_KEYWORDS = {
  tech: ["tech", "ai", "software", "code", "coding", "developer", "hardware", "chip", "semiconductor", "cyber", "robot", "cloud", "model", "algorithm", "llm", "apple", "google", "microsoft", "nvidia", "meta", "openai", "linux", "programming", "computer", "app", "web", "digital", "hack"],
  science: ["science", "physics", "quantum", "space", "astronomy", "biology", "chemistry", "research", "paper", "lab", "study", "planet", "star", "galaxy", "telescope", "nasa", "spacex", "orbit", "rocket", "dna", "gene", "particle", "gravity", "evolution", "phase"],
  space: ["space", "astronomy", "nasa", "spacex", "rocket", "orbit", "planet", "mars", "moon", "star", "galaxy", "telescope", "cosmic", "satellite", "astronaut", "universe", "iss", "launch", "flight"],
  finance: ["finance", "money", "invest", "stock", "market", "economy", "economic", "crypto", "bitcoin", "ethereum", "trading", "inflation", "fed", "rate", "dollar", "bank", "banking", "wealth", "fund", "revenue", "profit", "capital", "fintech", "startup", "valuation", "spend", "budget", "debt"],
  psychology: ["psychology", "psychological", "mind", "brain", "behavior", "mental", "cognitive", "bias", "decision", "emotion", "memory", "habit", "subconscious"],
  crypto: ["crypto", "bitcoin", "ethereum", "blockchain", "token", "web3", "defi", "wallet", "nft", "coinbase", "binance", "mining"],
  history: ["history", "historic", "historical", "ancient", "war", "battle", "century", "empire", "king", "queen", "dynasty", "civilization", "archaeology", "medieval", "past", "rebellion", "monarch", "wwii", "wwi", "roman", "egypt"],
  health: ["health", "fitness", "medical", "medicine", "doctor", "hospital", "disease", "virus", "vaccine", "diet", "nutrition", "workout", "exercise", "brain", "mental", "cure", "therapy", "wellness", "muscle", "cardio", "sleep"],
  gaming: ["game", "gaming", "playstation", "xbox", "nintendo", "steam", "gamer", "rpg", "multiplayer", "esports", "console", "gameplay", "trailer"],
};

function matchWord(word, text) {
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\b${escaped}s?\\b`, "i").test(text);
}

function matchesNiche(item, niche) {
  if (!niche || ["all", "general", "general (no niche)"].includes(niche.trim().toLowerCase())) return true;
  const n = niche.trim().toLowerCase();
  const title = (item.title || "").toLowerCase();
  const detail = (item.detail || "").toLowerCase();
  const src = (item.k || item.source || "").toLowerCase();
  const text = `${title} ${detail}`;

  if (text.includes(n)) return true;

  if (src === "spaceflight" && ["space", "astro", "flight", "universe"].some(k => n.includes(k))) return true;
  if (src === "hackernews" && ["tech", "software", "code", "programming", "developer", "startup", "computer"].some(k => n.includes(k))) return true;
  if (src === "arxiv" && ["science", "physics", "math", "academic", "research", "paper", "quantum"].some(k => n.includes(k))) return true;

  for (const [cat, kws] of Object.entries(NICHE_KEYWORDS)) {
    if (n.includes(cat)) {
      for (const kw of kws) {
        if (matchWord(kw, text)) return true;
      }
    }
  }

  const tokens = (n.match(/[a-z0-9]+/g) || []).filter(t => t.length > 2 && !["and", "the", "for", "with", "from", "about"].includes(t));
  for (const token of tokens) {
    for (const [cat, kws] of Object.entries(NICHE_KEYWORDS)) {
      if (token === cat || cat.includes(token)) {
        for (const kw of kws) {
          if (matchWord(kw, text)) return true;
        }
      }
    }
    if (matchWord(token, text)) return true;
  }
  return false;
}

async function loadTrends(refresh) {
  $("#trend-refresh").classList.add("spin");
  try { trends = await api("/api/trends" + (refresh ? "?refresh=1" : "")); renderTrends(); }
  catch (e) { $("#trend-list").innerHTML = `<div class="empty" style="grid-column:1/-1">Couldn't load trends. Check your internet connection.</div>`; }
  $("#trend-refresh").classList.remove("spin");
}

function renderTrends() {
  if (!trends || !trends.sources) return;
  const ok = Object.entries(trends.sources).filter(([, s]) => s.ok && s.items.length);

  // Extract saved niches from profileList and trends.niches
  const savedNiches = [];
  if (Array.isArray(profileList)) {
    for (const p of profileList) {
      const n = (p.niche || "").trim();
      if (n && !savedNiches.some(x => x.toLowerCase() === n.toLowerCase())) {
        savedNiches.push(n);
      }
    }
  }
  if (trends && Array.isArray(trends.niches)) {
    for (const n of trends.niches) {
      const trimmed = (n || "").trim();
      if (trimmed && !savedNiches.some(x => x.toLowerCase() === trimmed.toLowerCase())) {
        savedNiches.push(trimmed);
      }
    }
  }

  // If current trendNiche is not in savedNiches and not "all", fallback to "all"
  if (trendNiche !== "all" && !savedNiches.some(n => n.toLowerCase() === trendNiche.toLowerCase())) {
    trendNiche = "all";
  }

  // Render tabs: "All" first, then each unique saved niche
  let chipsHtml = `<span class="chip ${trendNiche === "all" ? "on" : ""}" data-niche="all">All</span>`;
  if (savedNiches.length > 0) {
    chipsHtml += savedNiches.map(n =>
      `<span class="chip ${trendNiche.toLowerCase() === n.toLowerCase() ? "on" : ""}" data-niche="${esc(n)}">${esc(n)}</span>`
    ).join("");
  }
  $("#src-filter").innerHTML = chipsHtml;
  $$("#src-filter .chip").forEach(c => c.onclick = () => {
    trendNiche = c.dataset.niche;
    renderTrends();
  });

  // Interleave items from available sources
  const lists = ok.map(([k, s]) => s.items.map(it => ({ ...it, k })));
  const allItems = [];
  for (let i = 0; lists.some(l => l[i]); i++) lists.forEach(l => l[i] && allItems.push(l[i]));

  // Filter items matching active niche tab
  const items = (trendNiche === "all")
    ? allItems
    : allItems.filter(it => matchesNiche(it, trendNiche));

  const limit = trendNiche === "all" ? 14 : 20;
  $("#trend-list").innerHTML = items.slice(0, limit).map(it =>
    `<button class="trend-item" data-title="${esc(it.title)}" title="${esc(it.detail || it.title)}"><i style="background:${SRC_COLORS[it.k] || '#fff'}"></i><span>${esc(it.title)}</span><em>Use →</em></button>`
  ).join("") || `<div class="empty" style="grid-column:1/-1">No trending ideas found for "${esc(trendNiche)}". Try "All" or refresh.</div>`;

  $$("#trend-list .trend-item").forEach(el => el.onclick = () => useTopic(el.dataset.title));
  const age = Math.round((Date.now() / 1000 - trends.fetched_at) / 60);
  $("#trend-age").textContent = age < 1 ? "just updated" : `updated ${age} min ago`;
}
function useTopic(title) {
  if (heroMode === "running") return toast("A video is already being made. Wait for it to finish");
  setHero("form");
  $("#topic-input").value = title;
  window.scrollTo({ top: 0, behavior: "smooth" });
  setTimeout(() => { $("#topic-input").focus(); $("#topic-input").select(); }, 350);
  toast("Topic added. Edit it if you like, then press Make video");
}
$("#trend-refresh").onclick = () => loadTrends(true);

/* ═══════════════════════════ home: setup, services, stats, latest ═══════════════════════════ */
let providers = [], settings = {}, library = null;
const SETUP_URL = "https://github.com/raunakpatil/youtube-agentic-ai-studio/blob/main/SETUP.md";
function renderChecklist() {
  if (!providers.length) return;
  const P = id => providers.find(p => p.id === id) || {};
  const gemini = P("gemini").ready, backup = P("groq").ready || P("openrouter").ready;
  const named = settings.channel_name && settings.channel_name !== "My AI Channel";
  const items = [
    { ok: true, t: "Voiceover", s: "Built in, free, no setup" },
    { ok: true, t: "Visuals", s: P("pexels").ready ? "Pexels + free image sources" : "Free image sources. Add Pexels for nicer photos" },
    { ok: gemini || backup, opt: true, t: "Script writer", s: gemini ? "Gemini connected" : backup ? "Backup AI connected" : "Free backup AI works. A free Gemini key writes better scripts", act: !gemini && ["Add key", "#settings"] },
    { ok: named, opt: true, t: "Channel name", s: named ? settings.channel_name : "Shown in your videos. Set it once", act: !named && ["Set name", "#settings"] },
    { ok: P("youtube_upload").ready, t: "Publishing", s: P("youtube_upload").ready ? "Ready to upload" : "Only needed to upload from here. You can always download the MP4", act: !P("youtube_upload").ready && ["Guide", SETUP_URL] },
  ];
  const n = items.filter(i => i.ok).length;
  $("#ready-num").textContent = `${n}/${items.length}`;
  $("#ready-text").textContent = "ready. You can make a video now";
  $("#checklist").innerHTML = items.map(i => `
    <div class="ck ${i.ok ? "ok" : i.opt ? "opt" : ""}"><span class="ic">${i.ok ? "✓" : i.opt ? "!" : "○"}</span>
      <div><b>${i.t}</b><small>${esc(i.s)}</small></div>
      ${i.act ? `<a class="btn btn-ghost btn-xs" href="${i.act[1]}" ${i.act[1].startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>${i.act[0]}</a>` : ""}</div>`).join("");
}
async function loadHealth(probe) {
  const btn = $("#api-probe");
  if (probe) { busy(btn, true, "Testing…"); $("#api-details").open = true; }
  try {
    providers = (await api("/api/health" + (probe ? "?probe=1" : ""))).providers;
    const ready = providers.filter(p => p.ready && !(p.probe && !p.probe.ok)).length;
    $("#api-count").textContent = `${ready} of ${providers.length} on`;
    const groups = [...new Set(providers.map(p => p.group))];
    const GROUP = { AI: "Writing", Media: "Voice & visuals", Research: "Research & ideas", Growth: "Growth & publishing" };
    $("#api-grid").innerHTML = groups.map(g => `<div class="api-group">${GROUP[g] || g}</div>` +
      providers.filter(p => p.group === g).map(p => {
        const down = p.probe && !p.probe.ok;
        const meta = down ? "offline" : p.probe ? `${p.probe.ms} ms` : p.keyless ? "free" : p.ready ? "connected" : "needs key";
        return `<div class="api ${down ? "down" : p.ready ? "ready" : ""}" title="${esc(p.probe && p.probe.error || p.role)}"><i></i><div><b>${esc(p.name)}</b><small>${esc(p.role)}</small></div>${!p.ready && !p.keyless ? `<a class="tag amber" href="#settings">${meta}</a>` : `<span class="tag ${down ? "pink" : p.keyless ? "green" : ""}">${meta}</span>`}</div>`;
      }).join("")).join("");
    renderChecklist();
  } catch (e) { }
  if (probe) { busy(btn, false); toast("Connection test finished"); }
}
$("#api-probe").onclick = () => loadHealth(true);

async function loadChannel() {
  const lib = library || { totals: {}, activity: [] };
  const ch = await api("/api/channel-stats").catch(() => null);
  if (ch && ch.ok) {
    $("#pulse-src").textContent = ch.title;
    $("#pulse-stats").innerHTML = [[fmt(ch.subscribers), "subscribers"], [fmt(ch.views), "total views"], [fmt(ch.videos), "videos on YouTube"], [lib.totals.videos || 0, "made with YAAS"]]
      .map(([v, l]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join("");
    const recent = ch.recent.slice(-30);
    drawBars($("#pulse-bars"), recent.map(v => v.views), recent.map(v => `${fmt(v.views)} views · ${v.title.slice(0, 36)}`));
    $("#pulse-foot").innerHTML = `<span>views per video</span><span>newest →</span>`;
    $("#pulse-hint").textContent = "";
  } else {
    $("#pulse-src").textContent = "";
    $("#pulse-stats").innerHTML = [[lib.totals.videos || 0, "videos made"], [lib.totals.uploaded || 0, "published"], [lib.totals.shorts || 0, "shorts"], [lib.totals.minutes || 0, "minutes of video"]]
      .map(([v, l]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join("");
    drawBars($("#pulse-bars"), lib.activity.map(a => a.count), lib.activity.map(a => `${a.day}: ${a.count} video${a.count === 1 ? "" : "s"}`));
    $("#pulse-foot").innerHTML = `<span>last 60 days</span><span>today</span>`;
    $("#pulse-hint").innerHTML = ch && ch.configured ? `Couldn't reach YouTube: ${esc(ch.error || "")}` : `Want subscribers and views here? Add a free <a href="#settings">YouTube Data API key</a>.`;
  }
}
function renderLatest() {
  const m = library && library.items[0];
  if (!m) { $("#latest").innerHTML = `<div class="empty" style="min-height:110px">Your videos will show up here.</div>`; return; }
  $("#latest").innerHTML = `
    <div class="thumb-frame ${m.video_type === "shorts" ? "tall" : ""}">${m.files.thumb ? `<img src="/library/${m.id}/thumbnail.jpg?t=${Date.now()}" alt="">` : ""}<span class="badge tag ${m.yt_url ? "green" : ""}">${m.yt_url ? "published" : m.video_type === "shorts" ? "short · not published" : "not published"}</span></div>
    <div style="margin-top:10px"><div class="vid-title">${esc(m.title)}</div><div class="vid-meta"><span>${ago(m.created_at)}</span>${m.duration ? `<span>· ${clock(m.duration)}</span>` : ""}</div></div>
    <div style="display:flex;gap:6px;margin-top:12px;flex-wrap:wrap"><button class="btn btn-white btn-sm" onclick="openProject('${m.id}')">Review &amp; publish</button>${m.yt_url ? `<a class="btn btn-ghost btn-sm" href="${esc(m.yt_url)}" target="_blank" rel="noopener">Watch on YouTube ↗</a>` : ""}</div>`;
}
