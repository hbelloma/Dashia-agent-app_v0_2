const fs = require("fs");
const code = fs.readFileSync("/tmp/smoke_out.js", "utf8");
const React = {
  createElement: (type, props, ...ch) => ({ type, props: { ...(props || {}), children: ch.length === 1 ? ch[0] : ch } }),
  Fragment: Symbol("Fragment"),
  useState: (i) => [typeof i === "function" ? i() : i, () => {}],
  useEffect: () => {}, useMemo: (f) => f(), useRef: (v) => ({ current: v ?? null }),
};
const api = new Function("React", "window", "localStorage", "document", "navigator", code)(
  React, {}, { getItem: () => null, setItem() {} }, {}, {});

let rendered = 0;
function expand(n) {
  if (n == null || typeof n === "boolean" || typeof n === "string" || typeof n === "number") return;
  if (Array.isArray(n)) return n.forEach(expand);
  if (typeof n.type === "function") { rendered++; return expand(n.type(n.props)); }
  if (n.props && n.props.children !== undefined) expand(n.props.children);
}
const noop = () => {};
const exchanges = { connections: [], loaded: true, addConnection: noop, removeConnection: noop };
const phantom = { available: false, connecting: false, publicKey: null, error: null, connect: noop, disconnect: noop };
let fail = 0;
function check(name, make) {
  for (const lang of ["es", "en"]) {
    const t = api.STR[lang];
    try { expand(make(t, lang)); }
    catch (e) { fail++; console.log(`  FALLA  ${name} [${lang}]: ${String(e.stack).split("\n").slice(0, 2).join(" | ")}`); return; }
  }
  console.log(`  ok     ${name}`);
}
const E = React.createElement;
const session = { email: "a@b.co", profileId: "a_40_b_2e_co" };
check("Shell + LoginScreen", (t, l) => E(api.Shell, null, E(api.LoginScreen, { t, lang: l, setLang: noop, onLogin: noop })));
check("MainApp (pestaña Inicio)", (t, l) => E(api.MainApp, { lang: l, setLang: noop, t, session, onLogout: noop }));
check("DashboardScreen", (t, l) => E(api.DashboardScreen, { t, lang: l, conn: { cex: false, wallet: null }, agents: api.AGENTS_SEED, market: api.MARKET_SEED, phantom, exchanges }));
check("StatsScreen", (t, l) => E(api.StatsScreen, { t, lang: l }));
check("BacktestScreen", (t) => E(api.BacktestScreen, { t }));
check("AgentsScreen", (t, l) => E(api.AgentsScreen, { t, lang: l, agents: api.AGENTS_SEED, setAgents: noop }));
check("VisualAgentBuilder", (t, l) => E(api.VisualAgentBuilder, { rules: api.RULE_TEMPLATES.oversold(), setRules: noop, t, lang: l }));
for (const ex of [null, "binance", "bybit", "weex"]) check(`ApiHelpModal(${ex})`, (t, l) => E(api.ApiHelpModal, { t, lang: l, exchangeId: ex, onClose: noop }));
check("ExchangeConnectFlow", (t, l) => E(api.ExchangeConnectFlow, { t, lang: l, exchanges, onClose: noop }));
check("ConnectedExchangesPanel", (t, l) => E(api.ConnectedExchangesPanel, { t, lang: l, exchanges }));
check("PhantomPanel", (t) => E(api.PhantomPanel, { t, phantom }));
check("ExperienceSelector", (t) => E(api.ExperienceSelector, { t, onSelect: noop }));
check("DashiaAvatarArea premium", (t) => E(api.DashiaAvatarArea, { experience: "premium", speaking: true, size: 84, t }));
check("SimpleChart", () => E(api.SimpleChart, { data: [{ v: 1 }, { v: 3 }, { v: 2 }], yKey: "v", kind: "area", stroke: "#fff", gridColor: "#111", textColor: "#222", fontMono: "m", fillGradientId: "g", height: 100 }));
console.log(`  (${rendered} componentes ejecutados, ${fail} fallas)`);

// paridad de traducciones
const keysEs = new Set(Object.keys(api.STR.es)), keysEn = new Set(Object.keys(api.STR.en));
console.log("== traducciones ==");
console.log("  solo en ES:", [...keysEs].filter((k) => !keysEn.has(k)));
console.log("  solo en EN:", [...keysEn].filter((k) => !keysEs.has(k)));
const used = new Set([...code.matchAll(/\bt\.([A-Za-z_]\w*)/g)].map((m) => m[1]));
console.log("  usadas pero ausentes en ES:", [...used].filter((k) => !keysEs.has(k) && k !== "tabs"));
console.log("== perfiles: a.b@x.com vs a_b@x.com distintos:", api.profileIdFromEmail("a.b@x.com") !== api.profileIdFromEmail("a_b@x.com"));
