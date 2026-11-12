// NoahFuel.jsx — NOAH NUTRITION (v5 — sesión 6, rediseño visual)
//
// Cambios pedidos sobre v4:
//  1) Fotos REALES del proyecto (noah_cloud/noah_coach/public/assets/comidas/
//     breakfast · lunch · dinner · pre_workout · post_workout · snack) en vez
//     de los íconos que puse yo. Se referencian directo como asset del
//     frontend (no dependen del backend) con fallback .png -> .jpg -> foto de
//     Unsplash que ya manda el motor -> emoji, en ese orden.
//  2) Estructura visual: en vez de una lista vertical larga, "ventanas" tipo
//     Garmin Connect -- grid de widgets centrados con título arriba y algo
//     visual en el medio (el mismo patrón que la captura de la app de
//     Garmin: Frec. cardíaca / Presión / Calorías / Sueño). Tocar un widget
//     abre el detalle (bottom sheet), igual que "Ver todo" en Garmin.
//  3) Paleta / tipografía alineada a la propia app (captura de /atleta/1):
//     números grandes en blanco, anillos de color por métrica, labels en
//     mayúscula chica gris, mismo acento violeta que el CTL de tu dashboard.
//  4) Sin Twin -- se conecta más adelante desde el panel de coach.

import React, { useState, useEffect, useRef } from 'react'
import {
  Flame, AlertTriangle, Send, X, Droplet, Pill, Info, Utensils, ChevronRight,
  Activity, HeartPulse, Zap, Brain, Trophy, Gauge,
} from 'lucide-react'

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'

function authFetch(url, options = {}) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) { try { localStorage.removeItem('noah_sesion') } catch {}; window.location.href = '/login' }
    return res
  })
}

// ── Paleta: la misma que ya usa el resto de la app (acento violeta del CTL, anillos CHO/PROT/GRASA que ya se ven en tu captura) ──
const C = {
  ink: '#292D29', ink2: 'rgba(41,45,41,0.72)', ink3: 'rgba(41,45,41,0.48)', ink4: 'rgba(41,45,41,0.32)',
  bg: '#F3F0E8',
  // paleta oficial NOAH
  marfil: '#F3F0E8', grafito: '#292D29', salvia: '#78866B', coral: '#E65B45', azul: '#4F8CC9',
  accent: '#78866B', accentDim: '#5C6952',
  success: '#35C07A', warning: '#E6B655', danger: '#E2726E', info: '#4F8CC9',
  cho: '#E6B655', prot: '#78866B', grasa: '#4F8CC9',
}
const FONT = "'Archivo', system-ui, -apple-system, sans-serif"
const MONO = "'IBM Plex Mono', ui-monospace, monospace"
const widgetStyle = {
  position: 'relative', overflow: 'hidden',
  background: 'linear-gradient(158deg, rgba(255,255,255,0.74) 0%, rgba(243,240,232,0.42) 100%)',
  backdropFilter: 'blur(18px)', WebkitBackdropFilter: 'blur(18px)',
  border: '1px solid rgba(255,255,255,0.72)', borderRadius: 22,
  boxShadow: '0 12px 34px -14px rgba(41,45,41,0.30), 0 2px 8px -4px rgba(41,45,41,0.12)',
  padding: '16px 14px', display: 'flex', flexDirection: 'column', alignItems: 'center',
  textAlign: 'center', cursor: 'pointer', minHeight: 148, justifyContent: 'space-between',
}

// ── Fotos reales del proyecto (public/assets/comidas). El backend manda
// foto_key en español (desayuno/almuerzo/cena/pre_entreno/post_entreno/snack/
// ventana); acá se mapea al nombre de archivo real en inglés. Fallback en
// cadena: .png -> .jpg -> foto que haya resuelto el backend (propia/Unsplash)
// -> emoji, nunca una imagen rota. ──
const ASSET_COMIDA = {
  desayuno: 'breakfast', almuerzo: 'lunch', cena: 'dinner',
  pre_entreno: 'pre_workout', post_entreno: 'post_workout',
  snack: 'snack', ventana: 'post_workout',
}
const EMOJI_COMIDA = { desayuno: '🥣', almuerzo: '🍗', cena: '🐟', snack: '🍌', pre_entreno: '🍞', post_entreno: '🥤', ventana: '🍚' }

// ── Render de markdown liviano para las respuestas del chat (negrita, viñetas,
// títulos y TABLAS estilo | a | b |). Sin dependencias; ante algo raro muestra
// el texto. Evita que NOAH devuelva "|", "*", "-" crudos en mobile. ──
function _mdInline(txt) {
  if (txt == null) return null
  const out = []; let rest = String(txt); let key = 0
  const re = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/
  let m
  while ((m = rest.match(re))) {
    const idx = m.index
    if (idx > 0) out.push(rest.slice(0, idx))
    if (m[2] != null) out.push(<strong key={key++} style={{ fontWeight: 700, color: C.ink }}>{m[2]}</strong>)
    else if (m[3] != null) out.push(<em key={key++}>{m[3]}</em>)
    else if (m[4] != null) out.push(<code key={key++} style={{ background: 'rgba(41,45,41,0.08)', padding: '1px 5px', borderRadius: 4 }}>{m[4]}</code>)
    rest = rest.slice(idx + m[0].length)
  }
  if (rest) out.push(rest)
  return out
}
function MarkdownLite({ texto }) {
  const lines = String(texto == null ? '' : texto).replace(/\r/g, '').split('\n')
  const isRow = (l) => l.trim().startsWith('|') && l.indexOf('|', 1) > 0
  const isSep = (l) => l.includes('-') && /^\s*\|?[\s:|-]+\|?\s*$/.test(l)
  const cells = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim())
  const blocks = []; let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (isRow(line) && i + 1 < lines.length && isSep(lines[i + 1])) {
      const head = cells(line); const rows = []; let j = i + 2
      while (j < lines.length && isRow(lines[j])) { rows.push(cells(lines[j])); j++ }
      blocks.push({ type: 'table', head, rows }); i = j; continue
    }
    if (line.match(/^\s*[-*•]\s+/) || line.match(/^\s*\d+\.\s+/)) {
      const items = []
      while (i < lines.length) {
        const b = lines[i].match(/^\s*[-*•]\s+(.*)$/); const n = lines[i].match(/^\s*(\d+)\.\s+(.*)$/)
        if (b) { items.push({ t: b[1] }); i++ } else if (n) { items.push({ t: n[2], n: n[1] }); i++ } else break
      }
      blocks.push({ type: 'list', items }); continue
    }
    const mh = line.match(/^\s*(#{1,4})\s+(.*)$/)
    if (mh) { blocks.push({ type: 'h', text: mh[2] }); i++; continue }
    if (/^\s*---+\s*$/.test(line)) { blocks.push({ type: 'hr' }); i++; continue }
    if (line.trim() === '') { i++; continue }
    const para = [line]; i++
    while (i < lines.length && lines[i].trim() !== '' && !isRow(lines[i]) &&
           !lines[i].match(/^\s*[-*•]\s+/) && !lines[i].match(/^\s*\d+\.\s+/) &&
           !lines[i].match(/^\s*#{1,4}\s+/) && !/^\s*---+\s*$/.test(lines[i])) { para.push(lines[i]); i++ }
    blocks.push({ type: 'p', text: para.join(' ') })
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {blocks.map((b, bi) => {
        if (b.type === 'table') return (
          <div key={bi} style={{ overflowX: 'auto', margin: '2px 0' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 11.5 }}>
              <thead><tr>{b.head.map((h, hi) => (
                <th key={hi} style={{ textAlign: 'left', padding: '5px 7px', color: C.accent, fontWeight: 700,
                  borderBottom: '1px solid rgba(41,45,41,0.18)', whiteSpace: 'nowrap' }}>{_mdInline(h)}</th>
              ))}</tr></thead>
              <tbody>{b.rows.map((r, ri) => (
                <tr key={ri}>{r.map((c, ci) => (
                  <td key={ci} style={{ padding: '5px 7px', borderBottom: '1px solid rgba(41,45,41,0.06)', color: C.ink2, verticalAlign: 'top' }}>{_mdInline(c)}</td>
                ))}</tr>
              ))}</tbody>
            </table>
          </div>
        )
        if (b.type === 'list') return (
          <div key={bi} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {b.items.map((it, ii) => (
              <div key={ii} style={{ display: 'flex', gap: 7, alignItems: 'flex-start' }}>
                <span style={{ color: C.accent, fontWeight: 700, flexShrink: 0, minWidth: it.n ? 15 : 7 }}>{it.n ? it.n + '.' : '•'}</span>
                <span style={{ flex: 1 }}>{_mdInline(it.t)}</span>
              </div>
            ))}
          </div>
        )
        if (b.type === 'h') return <div key={bi} style={{ fontWeight: 700, color: C.ink, fontSize: 13 }}>{_mdInline(b.text)}</div>
        if (b.type === 'hr') return <div key={bi} style={{ height: 1, background: 'rgba(41,45,41,0.12)' }}/>
        return <div key={bi} style={{ lineHeight: 1.5 }}>{_mdInline(b.text)}</div>
      })}
    </div>
  )
}

function FotoComida({ comida, size = 56, radius = 14 }) {
  const assetName = ASSET_COMIDA[comida.foto_key] || comida.foto_key
  const [intento, setIntento] = useState(0) // 0: .jpg (archivos reales), 1: .png, 2: foto_url backend, 3: emoji
  const fuentes = [`/assets/comidas/${assetName}.jpg`, `/assets/comidas/${assetName}.png`, comida.foto_url].filter(Boolean)
  const src = fuentes[intento]
  const emoji = EMOJI_COMIDA[comida.foto_key] || '🍽️'
  return (
    <div style={{ width: size, height: size, borderRadius: radius, flexShrink: 0, overflow: 'hidden',
      background: 'linear-gradient(160deg, rgba(120,134,107,0.20), rgba(79,140,201,0.10))',
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: size * 0.4 }}>
      {src
        ? <img src={src} alt={comida.nombre} style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={() => setIntento(i => i + 1)} />
        : emoji}
    </div>
  )
}

// ── Bottom sheet genérico (así se ve el detalle al "tocar y entrar") ──
function Sheet({ titulo, onClose, children }) {
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(41,45,41,0.42)', backdropFilter: 'blur(3px)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center', zIndex: 100,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 640, maxHeight: '82vh', overflowY: 'auto', color: C.ink, fontFamily: FONT,
        background: 'linear-gradient(180deg, #FBFAF6 0%, #F3F0E8 100%)', borderTop: '1px solid rgba(255,255,255,0.8)',
        borderRadius: '24px 24px 0 0', padding: '10px 20px 28px',
        boxShadow: '0 -20px 60px rgba(41,45,41,0.28)',
      }}>
        <div style={{ width: 36, height: 4, borderRadius: 4, background: 'rgba(41,45,41,0.18)', margin: '4px auto 16px' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span style={{ fontSize: 14, fontWeight: 800, color: C.ink, letterSpacing: 0.3 }}>{titulo}</span>
          <button onClick={onClose} style={{ background: 'rgba(41,45,41,0.06)', border: 'none', borderRadius: 10, width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
            <X size={15} color={C.ink3} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function WidgetTitulo({ children }) {
  return <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.1, textTransform: 'uppercase', color: C.ink3 }}>{children}</div>
}

// ── GlassCard: superficie translúcida con profundidad y reflejo de luz ──
function GlassCard({ accent, delay = 0, onClick, style = {}, children }) {
  return (
    <div className="fuel-w" onClick={onClick} style={{
      position: 'relative', overflow: 'hidden', borderRadius: 22, cursor: onClick ? 'pointer' : 'default',
      background: 'linear-gradient(158deg, rgba(255,255,255,0.74) 0%, rgba(243,240,232,0.42) 100%)',
      backdropFilter: 'blur(18px)', WebkitBackdropFilter: 'blur(18px)',
      border: '1px solid rgba(255,255,255,0.72)',
      boxShadow: '0 12px 34px -14px rgba(41,45,41,0.30), 0 2px 8px -4px rgba(41,45,41,0.12)',
      animation: 'fuelRise .55s both', animationDelay: `${delay}ms`, ...style,
    }}>
      <span style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.95), transparent)', pointerEvents: 'none' }} />
      {accent && <span style={{ position: 'absolute', top: 14, right: 16, width: 26, height: 3, borderRadius: 3, background: accent, opacity: 0.9, pointerEvents: 'none' }} />}
      {children}
    </div>
  )
}

// ── MacroRing: anillo SVG segmentado (CHO/PROT/GRASA por kcal), caps redondeados ──
function MacroRing({ macros, size = 120 }) {
  const items = [
    { g: macros.cho_g, kcal: (macros.cho_g || 0) * 4, c: C.cho },
    { g: macros.prot_g, kcal: (macros.prot_g || 0) * 4, c: C.prot },
    { g: macros.grasa_g, kcal: (macros.grasa_g || 0) * 9, c: C.grasa },
  ]
  const total = items.reduce((a, s) => a + s.kcal, 0) || 1
  const R = (size - 18) / 2, CX = size / 2, CY = size / 2, Circ = 2 * Math.PI * R, GAP = 0.03, SW = 11
  let off = 0
  return (
    <div style={{ position: 'relative', width: size, height: size, flex: '0 0 auto' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(41,45,41,0.07)" strokeWidth={SW} />
        {items.map((s, i) => {
          const f = s.kcal / total, draw = Math.max(0.001, f - GAP)
          const el = (
            <circle key={i} cx={CX} cy={CY} r={R} fill="none" stroke={s.c} strokeWidth={SW} strokeLinecap="round"
              strokeDasharray={`${draw * Circ} ${Circ}`} strokeDashoffset={-(off * Circ)}
              transform={`rotate(-90 ${CX} ${CY})`} style={{ transition: 'stroke-dasharray .8s cubic-bezier(.4,0,.2,1)' }} />
          )
          off += f
          return el
        })}
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <Flame size={16} color={C.coral} strokeWidth={2.2} />
        <span style={{ fontFamily: MONO, fontSize: 8.5, color: C.ink3, letterSpacing: 0.6, marginTop: 3 }}>MACROS</span>
      </div>
    </div>
  )
}

// ── HydrationRing: objetivo del día (azul natación) ──
function HydrationRing({ ml, size = 104 }) {
  const L = ml ? (ml / 1000).toFixed(1) : '—'
  const R = (size - 16) / 2, CX = size / 2, CY = size / 2, Circ = 2 * Math.PI * R, SW = 9
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <linearGradient id="hydg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={C.info} /><stop offset="100%" stopColor="#8FB9DE" />
          </linearGradient>
        </defs>
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(41,45,41,0.07)" strokeWidth={SW} />
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="url(#hydg)" strokeWidth={SW} strokeLinecap="round"
          strokeDasharray={`${Circ} ${Circ}`} transform={`rotate(-90 ${CX} ${CY})`} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <Droplet size={13} color={C.info} strokeWidth={2.2} style={{ marginBottom: 1 }} />
        <span style={{ fontFamily: MONO, fontSize: 24, fontWeight: 700, color: C.info, letterSpacing: -1, lineHeight: 1 }}>{L}</span>
        <span style={{ fontFamily: MONO, fontSize: 8.5, color: C.ink3, letterSpacing: 0.5 }}>LITROS</span>
      </div>
    </div>
  )
}

// ── Lista elegante de suplementos (cantidad + estado) ──
function SuplLista({ suplementos }) {
  if (!suplementos?.length) return <div style={{ fontSize: 11.5, color: C.ink3 }}>Sin sugerencias para hoy.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
      {suplementos.slice(0, 3).map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', borderRadius: 12,
          background: 'rgba(120,134,107,0.10)', border: '1px solid rgba(120,134,107,0.20)' }}>
          <span style={{ width: 7, height: 7, borderRadius: 999, background: C.accent, flex: '0 0 auto' }} />
          <span style={{ fontSize: 11.5, fontWeight: 600, color: C.ink, flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.item}</span>
          {s.dosis && <span style={{ fontFamily: MONO, fontSize: 10, color: C.ink3, flex: '0 0 auto' }}>{s.dosis}</span>}
        </div>
      ))}
    </div>
  )
}

// ── Foto de comida a lo ancho (cover), mismos fallbacks que FotoComida ──
function FotoBanner({ comida, height = 150, radius = 0 }) {
  const assetName = ASSET_COMIDA[comida.foto_key] || comida.foto_key
  const [intento, setIntento] = useState(0)
  const fuentes = [`/assets/comidas/${assetName}.jpg`, `/assets/comidas/${assetName}.png`, comida.foto_url].filter(Boolean)
  const src = fuentes[intento]
  const emoji = EMOJI_COMIDA[comida.foto_key] || '🍽️'
  return (
    <div style={{ width: '100%', height, borderRadius: radius, overflow: 'hidden',
      background: 'linear-gradient(155deg, rgba(120,134,107,0.28), rgba(79,140,201,0.16))',
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: height * 0.4 }}>
      {src
        ? <img src={src} alt={comida.nombre} onError={() => setIntento(i => i + 1)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : emoji}
    </div>
  )
}

// ── Hero de próxima comida: foto protagonista + overlay legible ──
function ComidaHero({ comida, onClick }) {
  if (!comida) return null
  return (
    <GlassCard accent={C.coral} delay={120} onClick={onClick} style={{ padding: 0, marginBottom: 12 }}>
      <div style={{ position: 'relative', height: 164 }}>
        <FotoBanner comida={comida} height={164} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(0deg, rgba(20,24,20,0.78) 0%, rgba(20,24,20,0.25) 42%, transparent 70%)' }} />
        <span style={{ position: 'absolute', top: 12, left: 14, fontFamily: FONT, fontSize: 9.5, fontWeight: 800, letterSpacing: 1, textTransform: 'uppercase', color: '#fff', background: 'rgba(230,91,69,0.85)', padding: '4px 10px', borderRadius: 999 }}>Próxima comida</span>
        <div style={{ position: 'absolute', left: 16, right: 16, bottom: 12 }}>
          <div style={{ fontFamily: FONT, fontSize: 19, fontWeight: 800, color: '#fff', letterSpacing: -0.3, textTransform: 'capitalize', textShadow: '0 1px 8px rgba(0,0,0,0.5)' }}>{comida.nombre.replace('-', ' ')}</div>
          <div style={{ fontFamily: MONO, fontSize: 11, color: 'rgba(255,255,255,0.9)', marginTop: 2 }}>{comida.hora} · {comida.kcal} kcal</div>
        </div>
      </div>
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {[['CHO', comida.cho_g, C.cho], ['PROT', comida.prot_g, C.prot], ['GRASA', comida.grasa_g, C.grasa]].map(([l, v, col]) => (
          <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 9px', borderRadius: 999, background: `${col}18` }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: col }} />
            <span style={{ fontFamily: FONT, fontSize: 9.5, fontWeight: 700, color: C.ink3 }}>{l}</span>
            <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: C.ink }}>{v}g</span>
          </span>
        ))}
        {comida.alimentos?.length > 0 && (
          <span style={{ flexBasis: '100%', fontSize: 11, color: C.ink3, marginTop: 2 }}>{comida.alimentos.map(a => a.medida || a.alimento).join(' · ')}</span>
        )}
      </div>
    </GlassCard>
  )
}

// ── Tira de comidas del día (fotográficas, compactas) ──
function ComidasTira({ comidas, horaActual, onOpen }) {
  if (!comidas?.length) return null
  return (
    <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4, marginBottom: 12, scrollbarWidth: 'none' }}>
      {comidas.map((c, i) => {
        const [h, m] = (c.hora || '00:00').split(':').map(Number)
        const pasada = (h * 60 + m) < horaActual
        return (
          <div key={i} className="fuel-w" onClick={onOpen} style={{ flex: '0 0 auto', width: 120, cursor: 'pointer', opacity: pasada ? 0.6 : 1 }}>
            <div style={{ borderRadius: 14, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.6)', boxShadow: '0 8px 20px -12px rgba(41,45,41,0.4)' }}>
              <FotoBanner comida={c} height={82} />
            </div>
            <div style={{ padding: '6px 2px 0' }}>
              <div style={{ fontFamily: FONT, fontSize: 11.5, fontWeight: 700, color: C.ink, textTransform: 'capitalize', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.nombre.replace('-', ' ')} {pasada && '✓'}</div>
              <div style={{ fontFamily: MONO, fontSize: 9.5, color: C.ink3 }}>{c.hora} · {c.kcal} kcal</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Inteligencia nutricional NOAH: qué ajusta y por qué (datos de nivel2) ──
function InteligenciaNOAH({ nivel2, onPorque }) {
  const { ajustes_bio, ea, protocolo_cho, protocolo_prot, recuperacion_ayer, carrera_proxima } = nivel2 || {}
  const tiles = []
  if (ea?.disponible) tiles.push({ Icon: Gauge, label: 'Energy Availability', val: `${ea.valor}`, unit: 'kcal/kg', tag: ea.status?.toUpperCase(), col: C.info })
  if (protocolo_cho?.seleccionado_gkg != null) tiles.push({ Icon: Flame, label: 'Protocolo CHO', val: `${protocolo_cho.seleccionado_gkg}`, unit: 'g/kg', tag: protocolo_cho.clasificacion, col: C.cho })
  if (protocolo_prot?.seleccionado_gkg != null) tiles.push({ Icon: Activity, label: 'Proteína', val: `${protocolo_prot.seleccionado_gkg}`, unit: 'g/kg', col: C.prot })
  if (recuperacion_ayer) tiles.push({ Icon: HeartPulse, label: 'Recuperación', val: `+${recuperacion_ayer.ajuste_cho_pct}`, unit: '% CHO', col: C.salvia })
  const hayAlgo = tiles.length || ajustes_bio?.length || carrera_proxima
  return (
    <GlassCard delay={260} style={{ padding: '16px', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
        <Brain size={15} color={C.salvia} strokeWidth={2.2} />
        <span style={{ fontFamily: FONT, fontSize: 11, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase', color: C.salvia }}>Inteligencia NOAH</span>
      </div>
      {!hayAlgo && <div style={{ fontSize: 12, color: C.ink3, marginBottom: 12 }}>NOAH ajusta tu plan cuando haya más datos fisiológicos disponibles.</div>}
      {tiles.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: ajustes_bio?.length || carrera_proxima ? 12 : 0 }}>
          {tiles.map((t, i) => (
            <div key={i} style={{ position: 'relative', padding: '11px 12px', borderRadius: 14, background: 'rgba(255,255,255,0.5)', border: '1px solid rgba(255,255,255,0.65)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <t.Icon size={13} color={t.col} strokeWidth={2.2} />
                <span style={{ fontFamily: FONT, fontSize: 10, fontWeight: 600, color: C.ink3 }}>{t.label}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                <span style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color: C.ink, letterSpacing: -0.5 }}>{t.val}</span>
                <span style={{ fontFamily: MONO, fontSize: 9.5, color: C.ink4 }}>{t.unit}</span>
              </div>
              {t.tag && <span style={{ display: 'inline-block', marginTop: 6, fontFamily: FONT, fontSize: 9, fontWeight: 700, color: t.col, background: `${t.col}1c`, padding: '2px 7px', borderRadius: 999 }}>{t.tag}</span>}
            </div>
          ))}
        </div>
      )}
      {ajustes_bio?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: carrera_proxima ? 12 : 0 }}>
          {ajustes_bio.map((a, i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10.5, fontWeight: 600, padding: '5px 10px', borderRadius: 999, background: 'rgba(120,134,107,0.12)', color: C.ink2 }}>
              <Zap size={11} color={C.salvia} />{a.factor}{a.accion ? ` → ${a.accion}` : (a.interpretacion ? `: ${a.interpretacion}` : '')}
            </span>
          ))}
        </div>
      )}
      {carrera_proxima && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 12px', borderRadius: 12, background: 'rgba(79,140,201,0.10)', border: '1px solid rgba(79,140,201,0.22)', marginBottom: 12 }}>
          <Trophy size={15} color={C.info} strokeWidth={2.1} />
          <span style={{ fontSize: 11, color: C.ink2 }}><b>{carrera_proxima.nombre}</b> en {carrera_proxima.dias_restantes} día(s){carrera_proxima.prioridad ? ` · prioridad ${carrera_proxima.prioridad}` : ''}</span>
        </div>
      )}
      <button onClick={(e) => { e.stopPropagation(); onPorque() }} className="noah-press" style={{
        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
        padding: '11px 12px', borderRadius: 12, background: 'rgba(41,45,41,0.04)', border: '1px solid rgba(41,45,41,0.10)', color: C.ink }}>
        <span style={{ display: 'flex', gap: 9, alignItems: 'center' }}><Info size={15} color={C.salvia} /><span style={{ fontFamily: FONT, fontSize: 12.5, fontWeight: 700 }}>Por qué este plan</span></span>
        <ChevronRight size={16} color={C.ink4} />
      </button>
    </GlassCard>
  )
}

// ══════════════════════════ COMPONENTE PRINCIPAL ═══════════════════════════

export default function NoahFuel({ atletaId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sheet, setSheet] = useState(null) // 'energia' | 'comidas' | 'suplementos' | 'hidratacion' | 'porque' | null

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    const f = new Date().toISOString().split('T')[0]
    authFetch(`${API}/atletas/${atletaId}/nutricion/fuel?fecha=${f}`)
      .then(r => r.json()).then(r => { setData(r.data || r); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId])

  if (loading) return (
    <div style={{ padding: 60, textAlign: 'center' }}>
      <Flame size={24} color={C.warning} />
      <div style={{ fontSize: 12, color: C.ink3, marginTop: 10 }}>Analizando tu día...</div>
    </div>
  )
  if (!data?.disponible) return <div style={{ padding: 28, fontSize: 12, color: C.ink3 }}>{data?.error || 'Sin datos todavía.'}</div>

  const { nivel1, nivel2, onboarding } = data
  const ahora = new Date()
  const horaActual = ahora.getHours() * 60 + ahora.getMinutes()
  const proxima = (nivel1.comidas || []).find(c => {
    const [h, m] = (c.hora || '00:00').split(':').map(Number)
    return (h * 60 + m) >= horaActual
  }) || nivel1.comidas?.[nivel1.comidas.length - 1]

  const alertaAlta = (nivel1.alertas || []).find(a => a.severidad === 'alta')
  const colorEstado = alertaAlta ? C.danger : (nivel1.alertas || []).length ? C.warning : C.success

  return (
    <div style={{ position: 'relative', maxWidth: 640, margin: '0 auto', color: C.ink, fontFamily: FONT }}>
      <style>{`
        @keyframes fuelRise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
        .fuel-w{transition:transform .22s cubic-bezier(.22,.61,.36,1),box-shadow .22s ease}
        .fuel-w:hover{transform:translateY(-3px);box-shadow:0 18px 42px -16px rgba(41,45,41,0.34)}
        @media(prefers-reduced-motion:reduce){.fuel-w{transition:none;animation:none!important}}
      `}</style>

      {/* Fondo decorativo: da color para que el glass refracte */}
      <div style={{ position: 'absolute', inset: '-30px -14px 0', overflow: 'hidden', pointerEvents: 'none', zIndex: 0 }}>
        <div style={{ position: 'absolute', top: -20, right: -50, width: 240, height: 240, borderRadius: '50%', background: `radial-gradient(circle, ${C.coral}38, transparent 68%)` }} />
        <div style={{ position: 'absolute', top: 300, left: -70, width: 250, height: 250, borderRadius: '50%', background: `radial-gradient(circle, ${C.salvia}36, transparent 68%)` }} />
        <div style={{ position: 'absolute', top: 640, right: -60, width: 240, height: 240, borderRadius: '50%', background: `radial-gradient(circle, ${C.azul}30, transparent 68%)` }} />
        <div style={{ position: 'absolute', top: 980, left: -60, width: 230, height: 230, borderRadius: '50%', background: `radial-gradient(circle, ${C.coral}2a, transparent 68%)` }} />
      </div>

      <div style={{ position: 'relative', zIndex: 1 }}>

        {/* Header */}
        <div style={{ padding: '2px 4px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 28, fontWeight: 800, letterSpacing: -0.8, color: C.ink }}>Tu día</span>
            <span style={{ fontSize: 9.5, fontWeight: 800, padding: '4px 10px', borderRadius: 20, background: `${colorEstado}22`, color: colorEstado, letterSpacing: 0.6 }}>
              {alertaAlta ? 'REVISAR' : (nivel1.alertas || []).length ? 'ATENCIÓN' : 'READY'}
            </span>
            {nivel1.doble_turno && <Chip color={C.cho}>DOBLE TURNO</Chip>}
            {nivel1.dia_descanso && <Chip color={C.ink3}>DESCANSO</Chip>}
          </div>
          <div style={{ fontSize: 13, color: C.ink2, lineHeight: 1.5 }}>{nivel1.narrativa}</div>
          {!onboarding.onboarding_completo && (
            <div style={{ display: 'flex', gap: 6, marginTop: 8, fontSize: 10.5, color: C.warning }}>
              <AlertTriangle size={12} style={{ marginTop: 1, flexShrink: 0 }} />
              <span>Faltan datos: {onboarding.requeridos_faltantes.join(', ')}</span>
            </div>
          )}
        </div>

        {/* 2 · ENERGÍA + MACROS + GASTO */}
        <GlassCard accent={C.coral} delay={0} onClick={() => setSheet('energia')} style={{ padding: '18px', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            <MacroRing macros={nivel1.macros} size={120} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.1, textTransform: 'uppercase', color: C.ink3 }}>Energía</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginTop: 3 }}>
                <span style={{ fontFamily: MONO, fontSize: 38, fontWeight: 700, letterSpacing: -1.5, color: C.coral, lineHeight: 1 }}>{nivel1.kcal_dia}</span>
                <span style={{ fontFamily: MONO, fontSize: 11, color: C.ink3 }}>kcal</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 12 }}>
                {[['Carbos', nivel1.macros.cho_g, nivel1.macros.cho_gkg, C.cho], ['Proteína', nivel1.macros.prot_g, nivel1.macros.prot_gkg, C.prot], ['Grasa', nivel1.macros.grasa_g, nivel1.macros.grasa_gkg, C.grasa]].map(([l, g, gkg, col]) => (
                  <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 3, background: col, flex: '0 0 auto' }} />
                    <span style={{ fontSize: 11, color: C.ink2, flex: 1 }}>{l}</span>
                    <span style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 600, color: C.ink }}>{g}g</span>
                    {gkg != null && <span style={{ fontFamily: MONO, fontSize: 9.5, color: C.ink4, minWidth: 46, textAlign: 'right' }}>{gkg} g/kg</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
          {nivel2?.gasto_desglose && (() => {
            const g = nivel2.gasto_desglose
            const gasto = g.total_gasto_estimado ?? ((g.tmb || 0) + (g.neat || 0) + (g.entreno || 0) + (g.tef || 0))
            const obj = g.objetivo_kcal ?? nivel1.kcal_dia
            const bal = Math.round((obj || 0) - (gasto || 0))
            return (
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid rgba(41,45,41,0.08)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 9 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase', color: C.ink3 }}>Gasto energético</span>
                  <span style={{ fontFamily: MONO, fontSize: 11, color: C.ink3 }}>balance <b style={{ color: bal < 0 ? C.warning : bal > 0 ? C.info : C.success }}>{bal > 0 ? '+' : ''}{bal}</b></span>
                </div>
                <BarraGasto g={g} />
              </div>
            )
          })()}
        </GlassCard>

        {/* 3 · PLAN DE COMIDAS (fotográfico) */}
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '0 4px', margin: '4px 0 10px' }}>
          <span style={{ fontFamily: FONT, fontSize: 14, fontWeight: 800, letterSpacing: -0.2, color: C.ink }}>Plan de comidas</span>
          <button onClick={() => setSheet('comidas')} className="noah-press" style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: FONT, fontSize: 11, fontWeight: 700, color: C.salvia, display: 'flex', alignItems: 'center', gap: 2 }}>Ver todo <ChevronRight size={13} /></button>
        </div>
        <ComidaHero comida={proxima} onClick={() => setSheet('comidas')} />
        <ComidasTira comidas={nivel1.comidas} horaActual={horaActual} onOpen={() => setSheet('comidas')} />

        {/* 4 · SUPLEMENTACIÓN */}
        <GlassCard accent={C.salvia} delay={200} onClick={() => setSheet('suplementos')} style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <div style={{ textAlign: 'center', flex: '0 0 auto', paddingLeft: 4 }}>
            <div style={{ fontFamily: MONO, fontSize: 32, fontWeight: 700, color: C.salvia, lineHeight: 1 }}>{nivel1.suplementos?.length || 0}</div>
            <div style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase', color: C.ink3, marginTop: 4 }}>Suplementos</div>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}><SuplLista suplementos={nivel1.suplementos} /></div>
        </GlassCard>

        {/* 5 · HIDRATACIÓN */}
        <GlassCard accent={C.azul} delay={240} onClick={() => setSheet('hidratacion')} style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <HydrationRing ml={nivel1.hidratacion_ml} size={96} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase', color: C.ink3, marginBottom: 9 }}>Hidratación · objetivo</div>
            {nivel2?.hidratacion_detalle ? (<>
              {[['Base', nivel2.hidratacion_detalle.base_ml], ['Entrenamiento', nivel2.hidratacion_detalle.entreno_ml]].map(([l, ml]) => (
                <div key={l} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '3px 0' }}>
                  <span style={{ fontSize: 11.5, color: C.ink2 }}>{l}</span>
                  <span style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 600, color: C.ink }}>{ml != null ? (ml / 1000).toFixed(1) : '—'} L</span>
                </div>
              ))}
              {nivel2.hidratacion_detalle.sodio_nota && <div style={{ fontSize: 10, color: C.ink4, marginTop: 6, lineHeight: 1.35 }}>{nivel2.hidratacion_detalle.sodio_nota}</div>}
            </>) : <div style={{ fontSize: 11.5, color: C.ink3 }}>Objetivo total del día.</div>}
          </div>
        </GlassCard>

        {/* 6 · INTELIGENCIA NOAH */}
        <InteligenciaNOAH nivel2={nivel2} onPorque={() => setSheet('porque')} />

        {/* 7 · CHAT NOAH */}
        <ChatNoah atletaId={atletaId} quickActions={data.quick_actions} />
      </div>

      {sheet === 'energia' && (
        <Sheet titulo="Energía de hoy" onClose={() => setSheet(null)}>
          <EnergiaDetalle nivel1={nivel1} nivel2={nivel2} />
        </Sheet>
      )}
      {sheet === 'comidas' && (
        <Sheet titulo="Comidas de hoy" onClose={() => setSheet(null)}>
          <ComidasDetalle comidas={nivel1.comidas} horaActual={horaActual} />
        </Sheet>
      )}
      {sheet === 'suplementos' && (
        <Sheet titulo="Suplementos de hoy" onClose={() => setSheet(null)}>
          <SuplementosDetalle suplementos={nivel1.suplementos} />
        </Sheet>
      )}
      {sheet === 'hidratacion' && (
        <Sheet titulo="Hidratación" onClose={() => setSheet(null)}>
          <HidratacionDetalle ml={nivel1.hidratacion_ml} detalle={nivel2.hidratacion_detalle} />
        </Sheet>
      )}
      {sheet === 'porque' && (
        <Sheet titulo="Por qué este plan" onClose={() => setSheet(null)}>
          <PorQueDetalle nivel2={nivel2} />
        </Sheet>
      )}
    </div>
  )
}

function Chip({ children, color }) {
  return <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 9px', borderRadius: 20, background: `${color}22`, color }}>{children}</span>
}

// ══════════════════════════ DETALLE: ENERGÍA ════════════════════════════════

const FMT = n => (n == null || isNaN(n) ? '—' : Math.round(n).toLocaleString('es-AR'))

function AnilloGrande({ label, gramos, gkg, color }) {
  return (
    <div style={{ textAlign: 'center', flex: 1, minWidth: 0 }}>
      <div style={{ width: 64, height: 64, borderRadius: '50%', margin: '0 auto 8px', display: 'flex',
        alignItems: 'center', justifyContent: 'center', border: `3px solid ${color}`, background: `${color}14` }}>
        <span style={{ fontFamily: MONO, fontSize: 15, fontWeight: 700, color }}>{gramos}g</span>
      </div>
      <div style={{ fontSize: 9.5, color: C.ink3, letterSpacing: 0.5, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 9.5, color: C.ink4 }}>{gkg} g/kg</div>
    </div>
  )
}

// Barra horizontal apilada: de dónde sale el gasto (Basal/Actividad/Entreno/Digestión)
function BarraGasto({ g }) {
  const segs = [
    { k: 'Basal', v: g?.tmb || 0, col: C.info },
    { k: 'Actividad', v: g?.neat || 0, col: C.grasa },
    { k: 'Entreno', v: g?.entreno || 0, col: C.success },
    { k: 'Digestión', v: g?.tef || 0, col: C.accent },
  ]
  const total = segs.reduce((a, s) => a + s.v, 0) || 1
  return (
    <div>
      <div style={{ display: 'flex', height: 16, borderRadius: 8, overflow: 'hidden', background: 'rgba(41,45,41,0.05)' }}>
        {segs.filter(s => s.v > 0).map(s => (
          <div key={s.k} title={`${s.k} ${FMT(s.v)}`} style={{ width: `${s.v / total * 100}%`, background: s.col }} />
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', marginTop: 12 }}>
        {segs.map(s => (
          <div key={s.k} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10.5, color: C.ink3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: s.col, flexShrink: 0 }} />
            <span>{s.k}</span>
            <b style={{ color: C.ink2, fontWeight: 700 }}>{FMT(s.v)}</b>
          </div>
        ))}
      </div>
    </div>
  )
}

const INTERP_OBJ = {
  mantener: ['Balance energético', 'mantenimiento'],
  bajar: ['Déficit moderado', 'pérdida de grasa'],
  subir: ['Superávit controlado', 'ganancia muscular'],
}
const ICON_DEP = { running: '🏃', cycling: '🚴', swimming: '🏊' }

function EntrenoFila({ ent, kcal, dobleTurno }) {
  const sesiones = Array.isArray(ent) ? ent : ent ? [ent] : []
  if (!sesiones.length) return <Fila label="Entrenamiento del día" val={`≈ ${FMT(kcal)} kcal`} />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {dobleTurno && sesiones.length > 1 && (
        <div style={{ fontSize: 11, color: C.ink3 }}>{sesiones.length} sesiones · <b style={{ color: C.ink2 }}>{FMT(kcal)} kcal</b></div>
      )}
      {sesiones.map((s, i) => {
        const dep = s.deporte || s.sport || 'running'
        const dur = s.dur_min || s.duracion || s.duration_min
        const tss = s.tss || s.tss_total
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 12,
            background: 'rgba(53,192,122,0.08)', border: '1px solid rgba(53,192,122,0.16)' }}>
            <span style={{ fontSize: 18 }}>{ICON_DEP[dep] || '🏋️'}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'capitalize' }}>{dep}{dur ? ` · ${Math.round(dur)} min` : ''}</div>
              {tss ? <div style={{ fontSize: 10, color: C.ink3 }}>TSS {Math.round(tss)}</div> : null}
            </div>
            {!dobleTurno && <div style={{ fontSize: 13, fontWeight: 800, color: C.success }}>≈ {FMT(kcal)} kcal</div>}
          </div>
        )
      })}
    </div>
  )
}

function EnergiaDetalle({ nivel1, nivel2 }) {
  const g = nivel2?.gasto_desglose
  const macros = nivel1?.macros
  if (!g || !macros) return <div style={{ fontSize: 12, color: C.ink3 }}>Falta información del atleta para calcular esto.</div>

  const gasto = g.total_gasto_estimado ?? ((g.tmb || 0) + (g.neat || 0) + (g.entreno || 0) + (g.tef || 0))
  const objetivo = g.objetivo_kcal ?? nivel1.kcal_dia
  const balance = Math.round((objetivo || 0) - (gasto || 0))
  const [titulo, sub] = INTERP_OBJ[g.objetivo_tipo] || INTERP_OBJ.mantener
  const ajustes = nivel2?.ajustes_bio || []
  const carrera = nivel2?.carrera_proxima

  const T = ({ children }) => <div style={{ fontSize: 11.5, fontWeight: 700, color: C.ink2, marginBottom: 11 }}>{children}</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {/* HEADER */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: MONO, fontSize: 42, fontWeight: 700, letterSpacing: -1, lineHeight: 1 }}>{FMT(gasto)}</div>
        <div style={{ fontSize: 9.5, color: C.ink3, letterSpacing: 0.7, textTransform: 'uppercase', marginTop: 5 }}>Gasto total estimado · kcal</div>
      </div>

      {/* 1 — de dónde sale */}
      <div>
        <T>¿De dónde sale tu gasto?</T>
        <BarraGasto g={g} />
      </div>

      {/* 2 — cuánto comer */}
      <div>
        <T>¿Cuánto deberías comer?</T>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          {[['Gasto', FMT(gasto), C.ink], ['→', '', null], ['Objetivo', FMT(objetivo), C.accent],
            ['Balance', `${balance > 0 ? '+' : ''}${FMT(balance)}`, balance < 0 ? C.warning : balance > 0 ? C.info : C.success]]
            .map(([lab, val, col], i) => col === null
              ? <div key={i} style={{ color: C.ink4, fontSize: 16 }}>→</div>
              : (
                <div key={i} style={{ textAlign: 'center', flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 9, color: C.ink4, textTransform: 'uppercase', letterSpacing: 0.5 }}>{lab}</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: col }}>{val}</div>
                </div>
              ))}
        </div>
        <div style={{ textAlign: 'center', fontSize: 11, color: C.ink3, marginTop: 11 }}>
          <b style={{ color: C.ink2 }}>{titulo}</b> · {sub}
        </div>
      </div>

      {/* 3 — macros */}
      <div>
        <T>Macros del día</T>
        <div style={{ display: 'flex', gap: 10 }}>
          <AnilloGrande label="Carbos" gramos={macros.cho_g} gkg={macros.cho_gkg} color={C.cho} />
          <AnilloGrande label="Proteína" gramos={macros.prot_g} gkg={macros.prot_gkg} color={C.prot} />
          <AnilloGrande label="Grasa" gramos={macros.grasa_g} gkg={macros.grasa_gkg} color={C.grasa} />
        </div>
      </div>

      {/* 4 — entrenamiento */}
      {g.entreno > 0 && (
        <div>
          <T>Entrenamiento</T>
          <EntrenoFila ent={nivel1.entreno_hoy} kcal={g.entreno} dobleTurno={nivel1.doble_turno} />
        </div>
      )}

      {/* 5 — ajuste NOAH */}
      {ajustes.length > 0 && (
        <div>
          <T>Ajuste NOAH</T>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            {ajustes.map((a, i) => (
              <span key={i} style={{ fontSize: 10.5, fontWeight: 600, padding: '4px 10px', borderRadius: 16,
                background: 'rgba(120,134,107,0.14)', color: C.ink2 }}>
                {a.factor}{a.interpretacion ? `: ${a.interpretacion}` : ''}
              </span>
            ))}
          </div>
          {ajustes.filter(a => a.accion).map((a, i) => (
            <div key={i} style={{ fontSize: 11, color: C.ink3, marginTop: 2 }}>→ {a.accion}</div>
          ))}
        </div>
      )}

      {/* Competencia próxima */}
      {carrera && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '10px 12px', borderRadius: 12,
          background: 'rgba(79,140,201,0.08)', border: '1px solid rgba(79,140,201,0.18)' }}>
          <span style={{ fontSize: 15 }}>🏁</span>
          <div style={{ fontSize: 11, color: C.ink2 }}>
            <b>{carrera.nombre}</b> en {carrera.dias_restantes} día(s) · ↑ disponibilidad de carbohidratos
          </div>
        </div>
      )}
    </div>
  )
}

// ══════════════════════════ DETALLE: COMIDAS ════════════════════════════════

function ComidasDetalle({ comidas, horaActual }) {
  const [abierta, setAbierta] = useState(null)
  if (!comidas?.length) return <div style={{ fontSize: 12, color: C.ink3 }}>Sin comidas planificadas hoy.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {comidas.map((c, i) => {
        const [h, m] = (c.hora || '00:00').split(':').map(Number)
        const pasada = (h * 60 + m) < horaActual
        const abre = abierta === i
        return (
          <div key={i} style={{ padding: '10px 4px', opacity: pasada ? 0.5 : 1,
            borderBottom: i < comidas.length - 1 ? '1px solid rgba(41,45,41,0.06)' : 'none' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer' }} onClick={() => setAbierta(abre ? null : i)}>
              <FotoComida comida={c} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 700 }}>{c.nombre.replace('-', ' ')} {pasada && '✓'}</span>
                  <span style={{ fontSize: 10, color: C.ink3 }}>{c.hora}</span>
                </div>
                <div style={{ fontSize: 10, color: C.ink3, margin: '2px 0 3px' }}>
                  {c.alimentos.map(a => a.medida || a.alimento).join(' · ')}
                </div>
                <div style={{ fontSize: 10.5, color: C.ink2 }}>
                  <b style={{ color: C.ink }}>{c.kcal}</b> kcal · {c.cho_g}C · {c.prot_g}P · {c.grasa_g}F
                </div>
              </div>
              <ChevronRight size={13} color={C.ink4} style={{ transform: abre ? 'rotate(90deg)' : 'none', flexShrink: 0 }} />
            </div>
            {abre && (
              <div style={{ marginLeft: 68, marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {c.alimentos.map((a, j) => (
                  <div key={j} style={{ fontSize: 10.5, color: C.ink3, display: 'flex', gap: 6 }}>
                    <Utensils size={10} color={C.ink4} style={{ flexShrink: 0, marginTop: 1 }} />
                    <span>{a.alimento}{a.medida ? ` — ${a.medida}` : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ══════════════════════════ DETALLE: SUPLEMENTOS ════════════════════════════

function SuplementosDetalle({ suplementos }) {
  if (!suplementos?.length) return <div style={{ fontSize: 12, color: C.ink3 }}>Sin suplementos sugeridos hoy.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {suplementos.map((s, i) => (
        <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <Pill size={14} color={C.accent} style={{ marginTop: 2, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 700 }}>{s.item} {s.dosis && <span style={{ color: C.ink3, fontWeight: 500 }}>· {s.dosis}</span>}</div>
            <div style={{ fontSize: 10.5, color: C.ink3 }}>{[s.timing, s.motivo].filter(Boolean).join(' — ')}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ══════════════════════════ DETALLE: HIDRATACIÓN ════════════════════════════

function HidratacionDetalle({ ml, detalle }) {
  if (!ml) return <div style={{ fontSize: 12, color: C.ink3 }}>Sin datos suficientes para calcular esto.</div>
  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <Droplet size={26} color={C.info} />
        <div style={{ fontSize: 32, fontWeight: 800, marginTop: 6 }}>{(ml / 1000).toFixed(1)} L</div>
      </div>
      {detalle && (
        <>
          <Fila label="Base (35ml/kg)" val={`${(detalle.base_ml / 1000).toFixed(1)} L`} />
          <Fila label="Por entrenamiento" val={`${(detalle.entreno_ml / 1000).toFixed(1)} L`} />
          <div style={{ fontSize: 10, color: C.ink4, marginTop: 10, lineHeight: 1.4 }}>{detalle.sodio_nota}</div>
        </>
      )}
    </div>
  )
}

// ══════════════════════════ DETALLE: POR QUÉ ════════════════════════════════

function PorQueDetalle({ nivel2 }) {
  const { gasto_desglose: g, protocolo_cho, protocolo_prot, ea, ajustes_bio, recuperacion_ayer, carrera_proxima } = nivel2 || {}
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <Seccion>Gasto</Seccion>
        <Fila label="Basal (Mifflin-St Jeor)" val={g?.tmb ? `${g.tmb} kcal` : 'No disponible'} />
        <Fila label="Actividad no estructurada (estimado)" val={g?.neat ? `${g.neat} kcal` : 'No disponible'} />
        <Fila label="Entrenamiento" val={g?.entreno ? `${g.entreno} kcal` : '0 kcal'} />
      </div>
      <div>
        <Seccion>Protocolo</Seccion>
        <Fila label={`CHO — ${protocolo_cho?.fuente}`} val={`${protocolo_cho?.clasificacion} → ${protocolo_cho?.seleccionado_gkg} g/kg`} />
        <Fila label={`Proteína — ${protocolo_prot?.fuente}`} val={`${protocolo_prot?.rango?.[0]}-${protocolo_prot?.rango?.[1]} g/kg → ${protocolo_prot?.seleccionado_gkg} g/kg`} />
      </div>
      {ea?.disponible && (
        <div>
          <Seccion>Energy Availability</Seccion>
          <Fila label={ea.fuente} val={`${ea.valor} kcal/kg FFM ${ea.ffm_estimado ? '(estimada)' : ''} — ${ea.status.toUpperCase()}`} />
          {ea.nota_sexo && <div style={{ fontSize: 9.5, color: C.ink4, marginTop: 6, lineHeight: 1.4 }}>{ea.nota_sexo}</div>}
        </div>
      )}
      {ajustes_bio?.length > 0 && (
        <div>
          <Seccion>Ajustes por biomarcadores</Seccion>
          {ajustes_bio.map((a, i) => <Fila key={i} label={`${a.factor}: ${a.interpretacion}`} val={a.accion} />)}
        </div>
      )}
      {recuperacion_ayer && (
        <div>
          <Seccion>Recuperación de ayer</Seccion>
          <Fila label={recuperacion_ayer.sesion} val={`+${recuperacion_ayer.ajuste_cho_pct}% CHO hoy`} />
        </div>
      )}
      {carrera_proxima && (
        <div>
          <Seccion>Carrera próxima</Seccion>
          <Fila label={carrera_proxima.nombre} val={`en ${carrera_proxima.dias_restantes} día(s) — prioridad ${carrera_proxima.prioridad}`} />
        </div>
      )}
      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
        <Info size={11} color={C.ink4} style={{ marginTop: 1, flexShrink: 0 }} />
        <span style={{ fontSize: 10, color: C.ink4, lineHeight: 1.4 }}>
          Estimaciones basadas en tus datos reales. No reemplazan una evaluación de un nutricionista o médico.
        </span>
      </div>
    </div>
  )
}
function Seccion({ children }) {
  return <div style={{ fontSize: 10, color: C.ink4, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 700 }}>{children}</div>
}
function Fila({ label, val }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '4px 0' }}>
      <span style={{ fontSize: 11.5, color: C.ink3 }}>{label}</span>
      <span style={{ fontSize: 11.5, color: C.ink2, fontWeight: 600, textAlign: 'right' }}>{val}</span>
    </div>
  )
}

// ══════════════════════════ CHAT NOAH ═══════════════════════════════════════

function ChatNoah({ atletaId, quickActions }) {
  const [msgs, setMsgs] = useState([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [msgs])

  const enviar = (texto) => {
    const t = (texto ?? text).trim()
    if (!t || sending) return
    setMsgs(m => [...m, { rol: 'usuario', texto: t }])
    setText(''); setSending(true)
    authFetch(`${API}/atletas/${atletaId}/nutricion/fuel/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto: t }),
    }).then(r => r.json())
      .then(r => setMsgs(m => [...m, { rol: 'noah', texto: (r.data || r).texto || (r.data || r).error || 'No pude responder.' }]))
      .catch(() => setMsgs(m => [...m, { rol: 'noah', texto: 'No pude conectar. Probá de nuevo.' }]))
      .finally(() => setSending(false))
  }

  return (
    <div style={{ ...widgetStyle, alignItems: 'stretch', textAlign: 'left', cursor: 'default', minHeight: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <img src="/assets/noah_avatar_m.png" alt="NOAH" onError={e => { e.currentTarget.style.display = 'none' }}
          style={{ width: 26, height: 26, borderRadius: '50%', objectFit: 'cover', border: `2px solid ${C.accent}80` }} />
        <span style={{ fontSize: 12, fontWeight: 700 }}>Preguntale a NOAH</span>
      </div>

      {msgs.length === 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {(quickActions || []).map(a => (
            <button key={a.id} onClick={() => enviar(a.label)} style={{
              padding: '7px 12px', borderRadius: 20, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              background: 'rgba(41,45,41,0.04)', border: '1px solid rgba(41,45,41,0.09)', color: C.ink2,
            }}>{a.label}</button>
          ))}
        </div>
      )}

      {msgs.length > 0 && (
        <div ref={scrollRef} style={{ maxHeight: 240, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
          {msgs.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.rol === 'usuario' ? 'flex-end' : 'flex-start',
              maxWidth: m.rol === 'usuario' ? '85%' : '100%',
              width: m.rol === 'usuario' ? 'auto' : '100%',
              padding: '8px 12px', borderRadius: 12, fontSize: 12, lineHeight: 1.5,
              background: m.rol === 'usuario' ? 'rgba(120,134,107,0.20)' : 'rgba(41,45,41,0.04)', color: C.ink2,
              whiteSpace: m.rol === 'usuario' ? 'pre-wrap' : 'normal', overflowWrap: 'anywhere',
            }}>{m.rol === 'usuario' ? m.texto : <MarkdownLite texto={m.texto} />}</div>
          ))}
          {sending && <div style={{ fontSize: 11, color: C.ink3, alignSelf: 'flex-start' }}>NOAH está pensando…</div>}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <input value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && enviar()}
          placeholder="¿Qué debería comer antes del entrenamiento?"
          style={{ flex: 1, padding: '10px 14px', borderRadius: 12, fontSize: 12,
            background: 'rgba(41,45,41,0.05)', border: '1px solid rgba(41,45,41,0.12)', color: C.ink, outline: 'none' }} />
        <button onClick={() => enviar()} disabled={sending || !text.trim()} style={{
          width: 40, height: 40, borderRadius: 12, border: 'none', flexShrink: 0,
          background: (sending || !text.trim()) ? 'rgba(120,134,107,0.3)' : C.accent,
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}><Send size={15} /></button>
      </div>

      <div style={{ fontSize: 9, color: C.ink4, textAlign: 'center', marginTop: 12 }}>
        NOAH ofrece orientación nutricional deportiva — no reemplaza a un nutricionista o médico.
      </div>
    </div>
  )
}
