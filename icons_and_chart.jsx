// ============================================================
// ÍCONOS — equivalentes SVG inline a lucide-react (esa librería no
// tiene build UMD confiable para cargar en una página publicada, así
// que se reconstruyen acá mismo, con el mismo estilo minimalista de trazo)
// ============================================================
function Icon({ size = 20, color = "currentColor", strokeWidth = 2, style, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
         strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" style={style}>
      {children}
    </svg>
  );
}
const Home = (p) => <Icon {...p}><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/></Icon>;
const Sparkles = (p) => <Icon {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2 2M16 16l2 2M6 18l2-2M16 8l2-2"/><circle cx="12" cy="12" r="2.4"/></Icon>;
const Cpu = (p) => <Icon {...p}><rect x="6" y="6" width="12" height="12" rx="1.5"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/></Icon>;
const TrendingUp = (p) => <Icon {...p}><polyline points="3 17 9 11 13 15 21 6"/><polyline points="15 6 21 6 21 12"/></Icon>;
const BarChart3 = (p) => <Icon {...p}><line x1="5" y1="21" x2="5" y2="12"/><line x1="12" y1="21" x2="12" y2="6"/><line x1="19" y1="21" x2="19" y2="15"/></Icon>;
const Wallet = (p) => <Icon {...p}><path d="M4 7a2 2 0 0 1 2-2h11a1 1 0 0 1 1 1v2"/><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M16 13h3v3h-3a1.5 1.5 0 0 1 0-3Z"/></Icon>;
const Link2 = (p) => <Icon {...p}><path d="M9 15l6-6"/><path d="M14 5h3a4 4 0 0 1 0 8h-2"/><path d="M10 19H7a4 4 0 0 1 0-8h2"/></Icon>;
const ShieldCheck = (p) => <Icon {...p}><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z"/><path d="M9 12l2 2 4-4"/></Icon>;
const Mic = (p) => <Icon {...p}><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/></Icon>;
const Send = (p) => <Icon {...p}><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7Z"/></Icon>;
const Play = (p) => <Icon {...p}><polygon points="6 3 20 12 6 21 6 3"/></Icon>;
const Plus = (p) => <Icon {...p}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></Icon>;
const CheckCircle2 = (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 5-5"/></Icon>;
const Trophy = (p) => <Icon {...p}><path d="M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 5H4a3 3 0 0 0 3 5M17 5h3a3 3 0 0 1-3 5"/><path d="M12 14v3M9 21h6M9.5 21v-2.5a2.5 2.5 0 0 1 5 0V21"/></Icon>;
const Lock = (p) => <Icon {...p}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></Icon>;
const AlertTriangle = (p) => <Icon {...p}><path d="M12 3 2 20h20L12 3Z"/><line x1="12" y1="10" x2="12" y2="15"/><circle cx="12" cy="17.6" r="0.4" fill={p.color || "currentColor"}/></Icon>;
const X = (p) => <Icon {...p}><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></Icon>;
const Eye = (p) => <Icon {...p}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></Icon>;
const EyeOff = (p) => <Icon {...p}><path d="M3 3l18 18"/><path d="M10.6 5.2A9.7 9.7 0 0 1 12 5c6 0 10 7 10 7a15.4 15.4 0 0 1-4 4.4M6.5 7A15.7 15.7 0 0 0 2 12s4 7 10 7a9.6 9.6 0 0 0 4.2-.94"/><path d="M9.5 10a3 3 0 0 0 4.2 4.2"/></Icon>;
const Loader2 = (p) => <Icon {...p}><path d="M21 12a9 9 0 1 1-9-9"/></Icon>;
const ChevronLeft = (p) => <Icon {...p}><polyline points="15 18 9 12 15 6"/></Icon>;
const GripVertical = (p) => <Icon {...p}><circle cx="9" cy="6" r="1" fill={p.color || "currentColor"}/><circle cx="9" cy="12" r="1" fill={p.color || "currentColor"}/><circle cx="9" cy="18" r="1" fill={p.color || "currentColor"}/><circle cx="15" cy="6" r="1" fill={p.color || "currentColor"}/><circle cx="15" cy="12" r="1" fill={p.color || "currentColor"}/><circle cx="15" cy="18" r="1" fill={p.color || "currentColor"}/></Icon>;
const ArrowUp = (p) => <Icon {...p}><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></Icon>;
const ArrowDown = (p) => <Icon {...p}><line x1="12" y1="5" x2="12" y2="19"/><polyline points="5 12 12 19 19 12"/></Icon>;
const Trash2 = (p) => <Icon {...p}><polyline points="3 6 5 6 21 6"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-.8 13.2a2 2 0 0 1-2 1.8H7.8a2 2 0 0 1-2-1.8L5 6"/><line x1="10" y1="11" x2="10" y2="16"/><line x1="14" y1="11" x2="14" y2="16"/></Icon>;
const Download = (p) => <Icon {...p}><path d="M12 3v12"/><polyline points="7 11 12 16 17 11"/><path d="M5 19h14"/></Icon>;
const Video = (p) => <Icon {...p}><rect x="2" y="6" width="14" height="12" rx="2"/><path d="M16 10l6-3v10l-6-3Z"/></Icon>;
const Volume2 = (p) => <Icon {...p}><polygon points="4 9 8 9 12 5 12 19 8 15 4 15 4 9"/><path d="M16.5 9a4 4 0 0 1 0 6M19.5 6a8 8 0 0 1 0 12"/></Icon>;
const VolumeX = (p) => <Icon {...p}><polygon points="4 9 8 9 12 5 12 19 8 15 4 15 4 9"/><line x1="17" y1="9" x2="22" y2="14"/><line x1="22" y1="9" x2="17" y2="14"/></Icon>;
const Crown = (p) => <Icon {...p}><path d="M3 8l4 3 5-6 5 6 4-3-1.6 10H4.6L3 8Z"/><line x1="5" y1="21" x2="19" y2="21"/></Icon>;
const MessageCircle = (p) => <Icon {...p}><path d="M21 12a8.5 8.5 0 0 1-13 7.2L3 21l1.8-5A8.5 8.5 0 1 1 21 12Z"/></Icon>;

// ============================================================
// MINI GRÁFICO SVG PROPIO — reemplaza los 2 usos de recharts (que no
// tiene una forma confiable de cargarse en una página publicada) con
// SVG dibujado a mano. Sin librería externa, cero riesgo de que no
// cargue.
// ============================================================
function SimpleChart({ data, xKey, yKey, kind = "line", stroke, gridColor, textColor, fontMono, fillGradientId, height = 160 }) {
  const width = 320; // viewBox lógico; el SVG escala 100% del contenedor real
  const values = data.map((d) => d[yKey]);
  const min = Math.min(...values), max = Math.max(...values);
  const pad = (max - min) * 0.08 || 1;
  const yMin = min - pad, yMax = max + pad;
  const xStep = data.length > 1 ? width / (data.length - 1) : width;

  const points = data.map((d, i) => {
    const x = i * xStep;
    const y = height - ((d[yKey] - yMin) / (yMax - yMin)) * height;
    return [x, y];
  });
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1][0].toFixed(1)},${height} L0,${height} Z`;

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => height * f);
  const yLabels = [yMax, (yMax + yMin) / 2, yMin];

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <svg viewBox={`-42 -6 ${width + 48} ${height + 14}`} style={{ width: "100%", height: "100%", overflow: "visible" }}>
        {kind === "area" && (
          <defs>
            <linearGradient id={fillGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0" />
            </linearGradient>
          </defs>
        )}
        {gridLines.map((gy, i) => (
          <line key={i} x1={0} y1={gy} x2={width} y2={gy} stroke={gridColor} strokeWidth="1" />
        ))}
        {yLabels.map((v, i) => (
          <text key={i} x={-8} y={height * (i / 2) + 3} textAnchor="end"
                fontFamily={fontMono} fontSize="9" fill={textColor}>
            {Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : v.toFixed(v % 1 === 0 ? 0 : 2)}
          </text>
        ))}
        {kind === "area" && <path d={areaPath} fill={`url(#${fillGradientId})`} stroke="none" />}
        <path d={linePath} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {kind === "line" && points.map((p, i) => (
          <circle key={i} cx={p[0]} cy={p[1]} r="2.4" fill={stroke} />
        ))}
      </svg>
    </div>
  );
}
const HelpCircle = (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M9.5 9.3a2.6 2.6 0 0 1 5 .9c0 1.7-2.5 2.2-2.5 3.9"/><circle cx="12" cy="17.3" r="0.5" fill={p.color || "currentColor"}/></Icon>;
const LogOut = (p) => <Icon {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></Icon>;
