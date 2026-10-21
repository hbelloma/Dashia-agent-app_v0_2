#!/usr/bin/env python3
"""
build_html.py — convierte dashia_app_prototype.jsx (vista previa del chat) en
dashia_app.html (página publicable). Reutiliza el bloque de íconos y el
gráfico SVG ya presentes en el HTML anterior. Cada reemplazo VERIFICA que el
texto exista: si el .jsx cambia de forma, falla en voz alta en vez de publicar
algo a medias.
Uso: python3 build_html.py <jsx_fuente> <icons_and_chart.jsx> <html_plantilla> <html_salida>
(<html_plantilla> es cualquier HTML ya generado: solo se reutiliza su cabecera/cola.)
"""
import sys

jsx_path, prefix_path, old_html_path, out_path = sys.argv[1:5]
src = open(jsx_path, encoding="utf-8").read()
old_html = open(old_html_path, encoding="utf-8").read()

def rep(text, old, new, label):
    assert old in text, f"[{label}] no se encontró el texto a reemplazar: {old[:80]!r}"
    return text.replace(old, new, 1)

def replace_between(text, start_marker, end_marker, new, label, keep_end=True):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    assert i < j, f"[{label}] marcadores en orden inválido"
    return text[:i] + new + (text[j:] if keep_end else text[j + len(end_marker):])

# 1) imports -> globals de React
cut = src.index('} from "recharts";') + len('} from "recharts";')
body = "const { useState, useEffect, useMemo, useRef } = React;" + src[cut:]

# 2) store -> localStorage (una sola pieza, protegida con try/catch)
body = replace_between(body, "// STORE-BEGIN", "// STORE-END", '''// STORE (versión publicada): localStorage del visitante, protegido con try/catch
const store = {
  async get(key) { try { return localStorage.getItem("dashia_" + key); } catch (e) { return null; } },
  async set(key, value) { try { localStorage.setItem("dashia_" + key, value); } catch (e) { /* bloqueado: queda en memoria */ } },
};
''', "store", keep_end=False)

# 3) prompt: sin búsqueda web (no existe en este runtime)
body = rep(body,
    "Podés: responder sobre noticias/contexto de mercado (usá búsqueda web si hace falta info actual), dar tu perspectiva general sobre un activo aclarando siempre que es educativa, no asesoría financiera ni recomendación de inversión, y ayudar con dudas de funcionalidad de la app.",
    "Podés: dar tu perspectiva general sobre un activo o el mercado aclarando siempre que es educativa, no asesoría financiera ni recomendación de inversión, y ayudar con dudas de funcionalidad de la app. Esta vista previa NO tiene acceso a búsqueda web en tiempo real — si preguntan algo que necesita datos de último momento, decilo con honestidad en vez de inventar un número.",
    "prompt")

# 4) askDashiaAI -> capacidad sample
body = replace_between(body, "async function askDashiaAI(", "function ExperienceSelector(", '''async function askDashiaAI(history, userText, lang) {
  // Publicada: fetch a api.anthropic.com lo bloquea la CSP. El equivalente es la capacidad "sample".
  if (!window.claude || typeof window.claude.use !== "function") throw new Error("sample-no-disponible");
  const sample = await window.claude.use("sample");
  if (!sample) throw new Error("sample-no-disponible");
  const turns = [
    { role: "user", content: dashiaSystemPrompt(lang) },
    { role: "assistant", content: lang === "es" ? "Entendido, lista para ayudar." : "Got it, ready to help." },
    ...history.map((m) => ({ role: m.from === "user" ? "user" : "assistant", content: m.text })),
    { role: "user", content: userText },
  ];
  const result = await sample(turns, { cache: false });
  const text = (result && result.text ? result.text : "").trim();
  return text || "…";
}

''', "askDashiaAI")

# 5) descarga CSV -> capacidad downloads
body = replace_between(body, "function downloadCsv(", "function StatsScreen(", '''async function downloadCsv(filename, csvText) {
  const withBom = "\\uFEFF" + csvText; // BOM para que Excel respete tildes/ñ
  try {
    if (window.claude && typeof window.claude.use === "function") {
      const downloads = await window.claude.use("downloads");
      if (downloads && typeof downloads.save === "function") {
        await downloads.save({ filename, data: withBom, mimeType: "text/csv" });
        return true;
      }
    }
  } catch (e) { /* cae al aviso */ }
  return false;
}

''', "downloadCsv")
body = rep(body, '''  function handleDownload() {
    const csvText = tradesToCsv(TRADE_HISTORY, lang, t);
    downloadCsv(`dashia_operaciones_${new Date().toISOString().slice(0, 10)}.csv`, csvText);
  }''', '''  const [downloadNote, setDownloadNote] = useState("");
  async function handleDownload() {
    const csvText = tradesToCsv(TRADE_HISTORY, lang, t);
    const ok = await downloadCsv(`dashia_operaciones_${new Date().toISOString().slice(0, 10)}.csv`, csvText);
    setDownloadNote(ok ? t.downloadOk : t.downloadUnavailable);
  }''', "handleDownload")
body = rep(body, '''          {t.csvNote}
        </div>''', '''          {t.csvNote}
        </div>
        {downloadNote && (
          <div style={{ fontFamily: FONT_UI, fontSize: 11, color: C.violet, textAlign: "center", marginTop: 4 }}>{downloadNote}</div>
        )}''', "downloadNote")
body = rep(body, 'csvNote: "CSV de ejemplo con los datos de esta demo — el backend real conectaría esto a tus operaciones reales.",',
    'csvNote: "CSV de ejemplo con los datos de esta demo — el backend real conectaría esto a tus operaciones reales.",\n    downloadOk: "¡Listo! Revisa tus descargas.", downloadUnavailable: "La descarga no está disponible en esta vista previa — en la app real sí funcionaría.",', "i18n es")
body = rep(body, 'csvNote: "Sample CSV from this demo\'s data — the real backend would connect this to your actual trades.",',
    'csvNote: "Sample CSV from this demo\'s data — the real backend would connect this to your actual trades.",\n    downloadOk: "Done! Check your downloads.", downloadUnavailable: "Download isn\'t available in this preview — it would work in the real app.",', "i18n en")

# 6) recharts -> SimpleChart
a = body.index('            <div style={{ height: 170 }}>\n              <ResponsiveContainer')
a_end = body.index("</ResponsiveContainer>\n            </div>", a) + len("</ResponsiveContainer>\n            </div>")
body = body[:a] + '''            <SimpleChart data={result.curve} yKey="equity" kind="area" height={170}
                         stroke={C.amber} gridColor={C.borderSoft} textColor={C.textFaint}
                         fontMono={FONT_MONO} fillGradientId="eqFill" />''' + body[a_end:]
b = body.index('        <div style={{ height: 130 }}>\n          <ResponsiveContainer')
b_end = body.index("</ResponsiveContainer>\n        </div>", b) + len("</ResponsiveContainer>\n        </div>")
body = body[:b] + '''        <SimpleChart data={PNL_CURVE} yKey="pnl" kind="line" height={130}
                     stroke={C.violet} gridColor={C.borderSoft} textColor={C.textFaint} fontMono={FONT_MONO} />''' + body[b_end:]

# 7) export default
body = rep(body, "export default function App() {", "function App() {", "export default")

# 8) prefijo (íconos + gráfico + HelpCircle/LogOut) desde su propio archivo
prefix = open(prefix_path, encoding="utf-8").read()
assert "const HelpCircle" in prefix and "function SimpleChart" in prefix and "const { useState" not in prefix

script = prefix.rstrip() + "\n\n" + body + '''

const __root = ReactDOM.createRoot(document.getElementById("root"));
__root.render(<App />);
'''

# 9) HTML: cabecera y cola reutilizadas del HTML anterior
head_end = old_html.index('<script type="text/babel" data-presets="react">') + len('<script type="text/babel" data-presets="react">')
html = old_html[:head_end] + "\n" + script + "\n</script>\n</body>\n</html>\n"
open(out_path, "w", encoding="utf-8").write(html)
print(f"OK: {out_path} ({len(html)} bytes)")
