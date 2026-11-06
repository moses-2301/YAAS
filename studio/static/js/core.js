/* ═══════════════════════════ helpers ═══════════════════════════ */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M" : n >= 1e4 ? Math.round(n / 1e3) + "K" : n >= 1e3 ? (n / 1e3).toFixed(1) + "K" : String(n ?? 0);
const clock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
async function api(url, body, method) {
  const opt = body !== undefined ? { method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : (method ? { method } : {});
  const r = await fetch(url, opt);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind; t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => { t.style.transition = "opacity .4s"; t.style.opacity = 0; setTimeout(() => t.remove(), 400); }, 3800);
}
function busy(btn, on, label) {
  if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; if (label) btn.textContent = label; }
  else { btn.disabled = false; if (btn.dataset.label) btn.innerHTML = btn.dataset.label; }
}
function ago(iso) {
  const s = (Date.now() - new Date(iso)) / 1000;
  return s < 60 ? "just now" : s < 3600 ? Math.round(s / 60) + " min ago" : s < 86400 ? Math.round(s / 3600) + " h ago" : new Date(iso).toLocaleDateString();
}

// the site's spectrum: yellow → orange → red → pink → violet → blue → mint
const SPECTRUM = ["#f5d742", "#ff9a3d", "#ff4d6d", "#ff70f3", "#a98bff", "#5cc8ff", "#38ffb3"].map(h => h.match(/\w\w/g).map(x => parseInt(x, 16)));
function spectrum(t, a = 1) {
  const x = Math.max(0, Math.min(.9999, t)) * (SPECTRUM.length - 1), i = Math.floor(x), f = x - i;
  const c = SPECTRUM[i].map((v, k) => Math.round(v + (SPECTRUM[i + 1][k] - v) * f));
  return `rgba(${c.join(",")},${a})`;
}
function drawBars(el, values, tips = []) {
  const max = Math.max(1, ...values);
  el.innerHTML = values.map((v, i) => {
    const t = i / Math.max(1, values.length - 1), h = v ? 12 + 88 * v / max : 4;
    return `<i style="height:${h}%;background:linear-gradient(to top, ${spectrum(t)}, ${spectrum(t, v ? .7 : .4)});opacity:${v ? 1 : .3}" ${tips[i] ? `data-tip="${esc(tips[i])}"` : ""}></i>`;
  }).join("");
}

/* ═══════════════════════════ navigation ═══════════════════════════ */
const VIEWS = ["home", "review", "library", "settings"];
const loaders = {};
function moveIndicator() {
  const a = $("#tabs a.active"), ind = $("#tabs-indicator");
  if (!a) { ind.style.width = "0"; return; }
  ind.style.width = a.offsetWidth + "px";
  ind.style.transform = `translateX(${a.offsetLeft}px)`;
}
function route() {
  const v = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  $$("#tabs a").forEach(a => a.classList.toggle("active", a.dataset.view === v));
  $("#settings-btn").classList.toggle("active", v === "settings");
  if (v === "review") $("#tabs a[data-view=review]").classList.remove("notify");
  $("#savebar").classList.remove("show");
  moveIndicator();
  loaders[v] && loaders[v]();
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", route);
window.addEventListener("resize", moveIndicator);
// the numbered step links on Review scroll within the page
document.addEventListener("click", e => {
  const a = e.target.closest('a[href^="#rv-"]');
  if (a) { e.preventDefault(); $(a.getAttribute("href")).scrollIntoView({ behavior: "smooth", block: "start" }); }
});

/* ═══════════════════════════ channel profiles ═══════════════════════════ */
let currentProfileId = "";
let profileList = [];

async function loadProfiles() {
  try {
    const data = await api("/api/profiles");
    profileList = data.profiles || [];
    currentProfileId = data.active || "";
    renderProfileSelector();
    if (typeof renderTrends === "function" && typeof trends !== "undefined" && trends) {
      renderTrends();
    }
  } catch (e) {
    console.error("Failed to load profiles:", e);
  }
}

function renderProfileSelector() {
  const activeObj = profileList.find(p => p.id === currentProfileId) || profileList[0];
  const pillName = $("#channel-pill-name");
  if (pillName && activeObj) {
    pillName.textContent = activeObj.name || "Channel";
  }
  const itemsContainer = $("#channel-menu-items");
  if (!itemsContainer) return;
  itemsContainer.innerHTML = profileList.map(p => `
    <button type="button" class="channel-menu-item ${p.id === currentProfileId ? "active" : ""}" data-pid="${esc(p.id)}">
      <div>
        <b>${esc(p.name)}</b>
        ${p.niche ? `<span class="ch-sub">${esc(p.niche)}</span>` : ""}
      </div>
      ${p.id === currentProfileId ? `<span class="check">✓</span>` : ""}
    </button>
  `).join("");

  $$("#channel-menu-items .channel-menu-item").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const pid = btn.dataset.pid;
      if (pid === currentProfileId) {
        $("#channel-menu").classList.remove("open");
        return;
      }
      await switchProfile(pid);
    };
  });
}

async function switchProfile(pid) {
  try {
    const res = await api("/api/profiles/active", { profile_id: pid });
    if (res.ok) {
      currentProfileId = pid;
      $("#channel-menu").classList.remove("open");
      toast(`Switched to ${res.channel_name}`, "ok");
      await loadProfiles();
      if (typeof loadSettings === "function") await loadSettings();
      if (typeof loadChannel === "function") await loadChannel();
      if (typeof loadHealth === "function") await loadHealth();
    } else {
      toast(res.error || "Failed to switch channel", "err");
    }
  } catch (e) {
    toast("Error switching channel", "err");
  }
}

document.addEventListener("click", e => {
  const wrap = $("#channel-dropdown-wrap");
  const menu = $("#channel-menu");
  if (!wrap || !menu) return;
  if (wrap.contains(e.target)) {
    if (e.target.closest("#channel-pill")) {
      menu.classList.toggle("open");
    }
  } else {
    menu.classList.remove("open");
  }
});

function initChannelModal() {
  const addBtn = $("#channel-menu-add-btn");
  const modal = $("#add-channel-modal");
  const closeBtn = $("#add-channel-modal-close");
  const cancelBtn = $("#add-channel-modal-cancel");
  const form = $("#add-channel-form");

  if (addBtn && modal) {
    addBtn.onclick = () => {
      $("#channel-menu").classList.remove("open");
      $("#new-channel-name-input").value = "";
      $("#new-channel-niche-input").value = "";
      modal.classList.add("open");
      setTimeout(() => $("#new-channel-name-input").focus(), 100);
    };
  }

  const closeModal = () => modal && modal.classList.remove("open");
  if (closeBtn) closeBtn.onclick = closeModal;
  if (cancelBtn) cancelBtn.onclick = closeModal;

  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      const name = $("#new-channel-name-input").value.trim();
      const niche = $("#new-channel-niche-input").value.trim();
      if (!name) return toast("Channel name is required", "err");
      try {
        const res = await api("/api/profiles/create", { name, niche });
        if (res.ok) {
          closeModal();
          toast(`Created channel "${name}"!`, "ok");
          currentProfileId = res.profile_id;
          await loadProfiles();
          if (typeof loadSettings === "function") await loadSettings();
          if (typeof loadChannel === "function") await loadChannel();
          location.hash = "#settings";
        } else {
          toast(res.error || "Failed to create channel", "err");
        }
      } catch (err) {
        toast("Error creating channel: " + err.message, "err");
      }
    };
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initChannelModal);
} else {
  initChannelModal();
}
