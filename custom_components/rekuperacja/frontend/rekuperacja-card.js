// Karta Lovelace integracji Rekuperacja — dane z WebSocket rekuperacja/subscribe.
const SOURCES = {
  harmonogram: { name: "Harmonogram", icon: "mdi:calendar-clock" },
  prysznic: { name: "Prysznic", icon: "mdi:shower-head" },
  przycisk_boost: { name: "Boost", icon: "mdi:fan-plus" },
  reczne: { name: "Ręcznie", icon: "mdi:hand-back-right" },
  panel_wietrz: { name: "Wietrzenie", icon: "mdi:weather-windy" },
  panel_cicho: { name: "Cicho", icon: "mdi:volume-off" },
};
const src = (s) => SOURCES[s] || { name: s, icon: "mdi:account-arrow-right" };

const QUICK = [
  { id: "boost", label: "Boost", sub: (st) => `100% · ${st.settings.boost_minutes} min`, icon: "mdi:fan-plus", action: { action: "boost" } },
  { id: "wietrz", label: "Wietrz", sub: () => "80% · 1 h", icon: "mdi:weather-windy", action: { action: "request", source: "panel_wietrz", percentage: 80, minutes: 60 } },
  { id: "cicho", label: "Cicho", sub: () => "Sen · 2 h", icon: "mdi:volume-off", action: { action: "request", source: "panel_cicho", preset: "Sen", minutes: 120 } },
];

function remaining(until) {
  if (!until) return "";
  const ms = new Date(until) - Date.now();
  if (ms <= 0) return "kończy się";
  const m = Math.ceil(ms / 60000);
  return m >= 60 ? `jeszcze ${Math.floor(m / 60)} h ${m % 60} min` : `jeszcze ${m} min`;
}
const hhmm = (iso) => new Date(iso).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

class RekuperacjaCard extends HTMLElement {
  setConfig(config) {
    this._config = { title: "Rekuperacja", show_shower: true, show_schedule: true, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first || !this._unsub) this._subscribe();
  }

  connectedCallback() {
    if (this._hass && !this._unsub) this._subscribe();
    this._timer = setInterval(() => this._render(), 30000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    if (this._unsub) this._unsub.then((u) => u && u()).catch(() => {});
    this._unsub = null;
  }

  _subscribe() {
    if (!this._hass || this._unsub) return;
    this._unsub = this._hass.connection
      .subscribeMessage((st) => { this._state = st; this._error = null; this._render(); }, { type: "rekuperacja/subscribe" })
      .catch((e) => { this._error = e.message || "Brak integracji Rekuperacja"; this._unsub = null; this._render(); });
  }

  _ws(msg) {
    return this._hass.callWS(msg).catch((e) => { this._error = e.message; this._render(); });
  }

  getCardSize() { return 7; }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }
  static getStubConfig() { return {}; }

  _render() {
    if (!this.shadowRoot) return;
    const st = this._state;
    const c = this._config || {};
    let body;
    if (this._error && !st) body = `<div class="empty">${esc(this._error)}</div>`;
    else if (!st) body = `<div class="empty">Ładowanie…</div>`;
    else body = this._main(st, c);
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${body}</ha-card>`;
    this._bind();
  }

  _main(st, c) {
    const auto = st.settings.automation;
    const fan = st.fan;
    const off = fan.state !== "on";
    const big = off ? "Wył." : fan.preset ? fan.preset : `${fan.percentage ?? "–"}%`;
    const pct = off ? 0 : fan.preset === "Boost" ? 100 : fan.preset === "Sen" ? 20 : fan.percentage || 40;
    const spin = off ? 0 : Math.max(0.4, 3 - pct / 40);
    const w = st.winner;
    const why = !auto ? "Automatyka wyłączona" : w ? `${src(w.source).name}${w.until ? " · " + remaining(w.until) : ""}` : "Brak żądań";
    const overridden = st.requests.some((r) => r.source === "reczne" || r.source === "przycisk_boost" || r.source.startsWith("panel_"));

    const quick = QUICK.map((q) => {
      const active = st.requests.some((r) => r.source === (q.action.source || "przycisk_boost"));
      return `<button class="q ${active ? "on" : ""}" data-quick="${q.id}" ${auto ? "" : "disabled"}>
        <ha-icon icon="${q.icon}"></ha-icon><span class="ql">${q.label}</span><span class="qs">${esc(q.sub(st))}</span></button>`;
    }).join("");

    const reqs = st.requests.map((r) => `
      <div class="req ${r.winner ? "win" : ""}">
        <ha-icon icon="${src(r.source).icon}"></ha-icon>
        <span class="rn">${esc(src(r.source).name)}</span>
        <span class="rc">${esc(r.command)}</span>
        <span class="rt">${r.until ? remaining(r.until) : "stałe"}</span>
        ${r.cancellable ? `<button class="x" data-cancel="${esc(r.source)}" title="Odwołaj"><ha-icon icon="mdi:close"></ha-icon></button>` : `<span class="x"></span>`}
      </div>`).join("");

    const sh = st.shower;
    const bar = (v, max) => `<div class="bar"><i style="width:${Math.min(100, Math.max(0, (v / max) * 100))}%"></i></div>`;
    const shower = !c.show_shower ? "" : `
      <div class="sec">
        <div class="sh">
          <ha-icon icon="mdi:shower-head"></ha-icon><span>Prysznic</span>
          <span class="chip ${sh.detected ? "hot" : ""}">${!sh.configured ? "nie skonfigurowany" : sh.detected ? "wykryty" : "brak"}</span>
          ${this._toggle("shower_enabled", st.settings.shower_enabled)}
        </div>
        ${sh.configured ? `
        <div class="meter"><span>Woda (3 min)</span>${bar(sh.water_l, sh.water_min_l)}<b>${sh.water_l} / ${sh.water_min_l} l</b></div>
        <div class="meter"><span>Spadek CWU (3 min)</span>${bar(-sh.cwu_change, sh.cwu_min_drop)}<b>${(-sh.cwu_change).toFixed(1)} / ${sh.cwu_min_drop} °C</b></div>
        <div class="hint">Po prysznicu wietrzy jeszcze ${st.settings.shower_after_minutes} min.</div>` : ""}
      </div>`;

    const sc = st.schedule;
    const schedule = !c.show_schedule ? "" : `
      <div class="sec">
        <div class="sh">
          <ha-icon icon="${sc.is_day ? "mdi:weather-sunny" : "mdi:weather-night"}"></ha-icon><span>Harmonogram</span>
          <span class="chip">${sc.is_day ? `dzień · ${st.settings.day_percentage}%` : "noc · Sen"}</span>
          ${this._toggle("schedule_enabled", st.settings.schedule_enabled)}
        </div>
        <div class="row2">
          <span>Wydajność w dzień</span>
          <span class="steps">${[20, 40, 60, 80, 100].map((p) => `<button class="step ${p === st.settings.day_percentage ? "on" : ""}" data-day="${p}">${p}</button>`).join("")}</span>
        </div>
        <div class="hint">${sc.is_day ? "Noc (Sen)" : "Dzień"} od ${hhmm(sc.next_switch)}.</div>
      </div>`;

    return `
      <div class="top">
        <div class="fan" style="--spin:${spin}s"><ha-icon icon="mdi:fan" class="${spin ? "spin" : ""}"></ha-icon></div>
        <div class="now">
          <div class="title">${esc(c.title)}</div>
          <div class="big">${esc(big)}</div>
          <div class="why">${esc(why)}</div>
        </div>
        <div class="auto"><span>Automatyka</span>${this._toggle("automation", auto)}</div>
      </div>
      ${overridden && auto ? `<button class="resume" data-resume><ha-icon icon="mdi:restore"></ha-icon>Powrót do automatyki</button>` : ""}
      <div class="quick">${quick}</div>
      <div class="sec"><div class="sh"><ha-icon icon="mdi:format-list-bulleted"></ha-icon><span>Żądania</span><span class="hint">wygrywa najwyższe</span></div>${reqs || '<div class="hint">brak</div>'}</div>
      ${shower}${schedule}
      ${this._error ? `<div class="err">${esc(this._error)}</div>` : ""}`;
  }

  _toggle(key, on) {
    return `<button class="tg ${on ? "on" : ""}" data-toggle="${key}" role="switch" aria-checked="${on}"><i></i></button>`;
  }

  _bind() {
    const r = this.shadowRoot;
    r.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", () =>
      this._ws({ type: "rekuperacja/set_setting", key: b.dataset.toggle, value: !b.classList.contains("on") })));
    r.querySelectorAll("[data-quick]").forEach((b) => b.addEventListener("click", () => {
      const q = QUICK.find((x) => x.id === b.dataset.quick);
      if (b.classList.contains("on")) this._ws({ type: "rekuperacja/action", action: "cancel", source: q.action.source || "przycisk_boost" });
      else this._ws({ type: "rekuperacja/action", ...q.action });
    }));
    r.querySelectorAll("[data-cancel]").forEach((b) => b.addEventListener("click", () =>
      this._ws({ type: "rekuperacja/action", action: "cancel", source: b.dataset.cancel })));
    r.querySelectorAll("[data-day]").forEach((b) => b.addEventListener("click", () =>
      this._ws({ type: "rekuperacja/set_setting", key: "day_percentage", value: Number(b.dataset.day) })));
    const res = r.querySelector("[data-resume]");
    if (res) res.addEventListener("click", () => this._ws({ type: "rekuperacja/action", action: "resume" }));
  }
}

const STYLE = `
ha-card { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
.empty { padding: 24px; text-align: center; color: var(--secondary-text-color); }
.top { display: flex; align-items: center; gap: 14px; }
.fan { width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center;
  background: color-mix(in srgb, var(--primary-color) 15%, transparent); color: var(--primary-color); flex: none; }
.fan ha-icon { --mdc-icon-size: 34px; }
.spin { animation: spin var(--spin) linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.now { flex: 1; min-width: 0; }
.title { font-size: 13px; color: var(--secondary-text-color); }
.big { font-size: 30px; font-weight: 600; line-height: 1.1; }
.why { font-size: 13px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.auto { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 11px; color: var(--secondary-text-color); }
.quick { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
button { font: inherit; color: inherit; cursor: pointer; border: none; background: none; }
button:disabled { opacity: .4; cursor: default; }
.q { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 10px 4px; border-radius: 12px;
  background: var(--secondary-background-color); }
.q.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
.ql { font-weight: 600; font-size: 14px; } .qs { font-size: 11px; opacity: .75; }
.resume { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 8px; border-radius: 10px;
  border: 1px solid var(--primary-color); color: var(--primary-color); font-weight: 500; }
.sec { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--divider-color); padding-top: 12px; }
.sh { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.sh ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
.sh .tg { margin-left: auto; } .sh .hint { margin-left: auto; font-weight: 400; }
.chip { font-size: 12px; font-weight: 400; padding: 2px 8px; border-radius: 10px; background: var(--secondary-background-color); }
.chip.hot { background: var(--info-color, #039be5); color: #fff; }
.req { display: grid; grid-template-columns: 24px 1fr auto auto 28px; align-items: center; gap: 8px; font-size: 14px;
  padding: 4px 6px; border-radius: 8px; }
.req.win { background: color-mix(in srgb, var(--primary-color) 12%, transparent); font-weight: 600; }
.req ha-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
.rt { font-size: 12px; color: var(--secondary-text-color); font-weight: 400; }
.x { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; }
.x ha-icon { --mdc-icon-size: 16px; } button.x:hover { background: var(--secondary-background-color); }
.meter { display: grid; grid-template-columns: 130px 1fr auto; gap: 8px; align-items: center; font-size: 13px; }
.meter b { font-weight: 500; font-variant-numeric: tabular-nums; }
.bar { height: 6px; border-radius: 3px; background: var(--secondary-background-color); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--primary-color); }
.hint { font-size: 12px; color: var(--secondary-text-color); }
.row2 { display: flex; justify-content: space-between; align-items: center; font-size: 13px; gap: 8px; }
.steps { display: flex; gap: 4px; }
.step { padding: 4px 8px; border-radius: 8px; background: var(--secondary-background-color); font-size: 12px; }
.step.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
.tg { width: 40px; height: 22px; border-radius: 11px; background: var(--disabled-color, #9e9e9e); position: relative; flex: none; }
.tg i { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: left .15s; }
.tg.on { background: var(--primary-color); } .tg.on i { left: 21px; }
.err { font-size: 12px; color: var(--error-color); }
`;

if (!customElements.get("rekuperacja-card")) {
  customElements.define("rekuperacja-card", RekuperacjaCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "rekuperacja-card", name: "Rekuperacja", description: "Stan, żądania, szybkie akcje, prysznic i harmonogram", preview: true });
}
