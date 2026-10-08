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
  ink: 'rgba(255,255,255,0.94)', ink2: 'rgba(255,255,255,0.70)', ink3: 'rgba(255,255,255,0.45)', ink4: 'rgba(255,255,255,0.28)',
  bg: '#0B0B10',
  accent: '#8B5CF6', accentDim: '#6D28D9',
  success: '#34D399', warning: '#F59E0B', danger: '#F87171', info: '#60A5FA',
  cho: '#F5A623', prot: '#8B5CF6', grasa: '#38BDF8',
}
const widgetStyle = {
  background: 'linear-gradient(165deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.015) 100%)',
  border: '1px solid rgba(255,255,255,0.08)', borderRadius: 18,
  boxShadow: '0 10px 28px -10px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
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

function FotoComida({ comida, size = 56, radius = 14 }) {
  const assetName = ASSET_COMIDA[comida.foto_key] || comida.foto_key
  const [intento, setIntento] = useState(0) // 0: .png, 1: .jpg, 2: foto_url backend, 3: emoji
  const fuentes = [`/assets/comidas/${assetName}.png`, `/assets/comidas/${assetName}.jpg`, comida.foto_url].filter(Boolean)
  const src = fuentes[intento]
  const emoji = EMOJI_COMIDA[comida.foto_key] || '🍽️'
  return (
    <div style={{ width: size, height: size, borderRadius: radius, flexShrink: 0, overflow: 'hidden',
      background: 'linear-gradient(160deg, rgba(139,92,246,0.20), rgba(56,189,248,0.10))',
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
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(3px)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center', zIndex: 100,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 640, maxHeight: '82vh', overflowY: 'auto',
        background: '#14141C', borderTop: '1px solid rgba(255,255,255,0.10)',
        borderRadius: '22px 22px 0 0', padding: '10px 20px 28px',
        boxShadow: '0 -20px 60px rgba(0,0,0,0.5)',
      }}>
        <div style={{ width: 36, height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.18)', margin: '4px auto 16px' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span style={{ fontSize: 14, fontWeight: 800, color: C.ink, letterSpacing: 0.3 }}>{titulo}</span>
          <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.06)', border: 'none', borderRadius: 10, width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
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
    <div style={{ maxWidth: 640, margin: '0 auto', color: C.ink }}>

      {/* Header: "de un vistazo" */}
      <div style={{ padding: '4px 4px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.3 }}>Tu día</span>
          <span style={{ fontSize: 9, fontWeight: 700, padding: '3px 9px', borderRadius: 20, background: `${colorEstado}22`, color: colorEstado, letterSpacing: 0.4 }}>
            {alertaAlta ? 'REVISAR' : (nivel1.alertas || []).length ? 'ATENCIÓN' : 'READY'}
          </span>
          {nivel1.doble_turno && <Chip color={C.accent}>DOBLE TURNO</Chip>}
          {nivel1.dia_descanso && <Chip color={C.ink3}>DESCANSO</Chip>}
        </div>
        <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.5 }}>{nivel1.narrativa}</div>
        {!onboarding.onboarding_completo && (
          <div style={{ display: 'flex', gap: 6, marginTop: 8, fontSize: 10.5, color: C.warning }}>
            <AlertTriangle size={12} style={{ marginTop: 1, flexShrink: 0 }} />
            <span>Faltan datos: {onboarding.requeridos_faltantes.join(', ')}</span>
          </div>
        )}
      </div>

      {/* Grid de ventanas tipo Garmin */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>

        <div style={widgetStyle} onClick={() => setSheet('energia')}>
          <WidgetTitulo>Energía</WidgetTitulo>
          <div>
            <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: -0.5 }}>{nivel1.kcal_dia}</div>
            <div style={{ fontSize: 9, color: C.ink3, marginTop: -2 }}>kcal hoy</div>
          </div>
          <MiniAnillos macros={nivel1.macros} />
        </div>

        <div style={widgetStyle} onClick={() => setSheet('comidas')}>
          <WidgetTitulo>Próxima comida</WidgetTitulo>
          {proxima ? (
            <>
              <FotoComida comida={proxima} size={62} radius={16} />
              <div>
                <div style={{ fontSize: 12.5, fontWeight: 700 }}>{proxima.nombre.replace('-', ' ')}</div>
                <div style={{ fontSize: 10, color: C.ink3 }}>{proxima.hora} · {proxima.kcal} kcal</div>
              </div>
            </>
          ) : <div style={{ fontSize: 11, color: C.ink3 }}>Sin comidas hoy</div>}
        </div>

        <div style={widgetStyle} onClick={() => setSheet('suplementos')}>
          <WidgetTitulo>Suplementos</WidgetTitulo>
          <Pill size={30} color={C.accent} strokeWidth={1.6} />
          <div>
            <div style={{ fontSize: 20, fontWeight: 800 }}>{nivel1.suplementos?.length || 0}</div>
            <div style={{ fontSize: 9, color: C.ink3 }}>{nivel1.suplementos?.[0]?.item || 'sin sugerencias'}</div>
          </div>
        </div>

        <div style={widgetStyle} onClick={() => setSheet('hidratacion')}>
          <WidgetTitulo>Hidratación</WidgetTitulo>
          <Droplet size={30} color={C.info} strokeWidth={1.6} />
          <div>
            <div style={{ fontSize: 20, fontWeight: 800 }}>{nivel1.hidratacion_ml ? (nivel1.hidratacion_ml / 1000).toFixed(1) : '—'} L</div>
            <div style={{ fontSize: 9, color: C.ink3 }}>objetivo del día</div>
          </div>
        </div>

      </div>

      {/* Por qué este plan — ancho completo, abajo del grid */}
      <div style={{ ...widgetStyle, flexDirection: 'row', justifyContent: 'space-between', textAlign: 'left', marginTop: 12, minHeight: 'auto', padding: '14px 16px' }}
        onClick={() => setSheet('porque')}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Info size={16} color={C.ink3} />
          <span style={{ fontSize: 12, fontWeight: 700 }}>Por qué este plan</span>
        </div>
        <ChevronRight size={16} color={C.ink4} />
      </div>

      <div style={{ marginTop: 14 }}>
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

// ══════════════════════════ MINI ANILLOS (widget Energía) ═══════════════════

function MiniAnillos({ macros }) {
  if (!macros) return null
  return (
    <div style={{ display: 'flex', gap: 14 }}>
      {[['Carbos', macros.cho_g, C.cho], ['Proteína', macros.prot_g, C.prot], ['Grasa', macros.grasa_g, C.grasa]].map(([l, v, col]) => (
        <div key={l} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', border: `2.5px solid ${col}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 800, color: col }}>
            {v}
          </div>
          <div style={{ fontSize: 8, color: C.ink3, fontWeight: 600 }}>{l}</div>
        </div>
      ))}
    </div>
  )
}

// ══════════════════════════ DETALLE: ENERGÍA ════════════════════════════════

const FMT = n => (n == null || isNaN(n) ? '—' : Math.round(n).toLocaleString('es-AR'))

function AnilloGrande({ label, gramos, gkg, color }) {
  return (
    <div style={{ textAlign: 'center', flex: 1, minWidth: 0 }}>
      <div style={{ width: 64, height: 64, borderRadius: '50%', margin: '0 auto 8px', display: 'flex',
        alignItems: 'center', justifyContent: 'center', border: `3px solid ${color}`, background: `${color}14` }}>
        <span style={{ fontSize: 15, fontWeight: 800, color }}>{gramos}g</span>
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
      <div style={{ display: 'flex', height: 16, borderRadius: 8, overflow: 'hidden', background: 'rgba(255,255,255,0.05)' }}>
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
            background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.16)' }}>
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
        <div style={{ fontSize: 42, fontWeight: 800, letterSpacing: -1, lineHeight: 1 }}>{FMT(gasto)}</div>
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
                background: 'rgba(139,92,246,0.14)', color: C.ink2 }}>
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
          background: 'rgba(96,165,250,0.08)', border: '1px solid rgba(96,165,250,0.18)' }}>
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
            borderBottom: i < comidas.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
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
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)', color: C.ink2,
            }}>{a.label}</button>
          ))}
        </div>
      )}

      {msgs.length > 0 && (
        <div ref={scrollRef} style={{ maxHeight: 240, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
          {msgs.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.rol === 'usuario' ? 'flex-end' : 'flex-start', maxWidth: '85%',
              padding: '8px 12px', borderRadius: 12, fontSize: 12, lineHeight: 1.5,
              background: m.rol === 'usuario' ? 'rgba(139,92,246,0.20)' : 'rgba(255,255,255,0.04)', color: C.ink2,
            }}>{m.texto}</div>
          ))}
          {sending && <div style={{ fontSize: 11, color: C.ink3, alignSelf: 'flex-start' }}>NOAH está pensando…</div>}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <input value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && enviar()}
          placeholder="¿Qué debería comer antes del entrenamiento?"
          style={{ flex: 1, padding: '10px 14px', borderRadius: 12, fontSize: 12,
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: C.ink, outline: 'none' }} />
        <button onClick={() => enviar()} disabled={sending || !text.trim()} style={{
          width: 40, height: 40, borderRadius: 12, border: 'none', flexShrink: 0,
          background: (sending || !text.trim()) ? 'rgba(139,92,246,0.3)' : C.accent,
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}><Send size={15} /></button>
      </div>

      <div style={{ fontSize: 9, color: C.ink4, textAlign: 'center', marginTop: 12 }}>
        NOAH ofrece orientación nutricional deportiva — no reemplaza a un nutricionista o médico.
      </div>
    </div>
  )
}
