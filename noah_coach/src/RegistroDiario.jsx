// src/RegistroDiario.jsx — NOAH · Check-in de 5 caras + toggle de fuerza
// Autocontenido: fetchea /registro y postea check-in y fuerza. Solo presentación
// premium (paleta v2, iconografía lucide, sin emojis). No toca la carga validada:
// la fuerza se guarda como sRPE complementario aparte.
import React, { useState, useEffect } from 'react'
import { Angry, Frown, Meh, Smile, Laugh, Dumbbell, Check, Sparkles } from 'lucide-react'
import { NOAH, FONT } from './noahTheme'

const F = FONT.base, M = FONT.mono

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url, options = {}) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers }).then(r => r.json().catch(() => ({})))
}

// 5 caras -> puntaje. Iconografía de línea, no emojis.
const CARAS = [
  { v: 1, Icon: Angry, col: NOAH.coral,  lbl: 'Muy mal' },
  { v: 2, Icon: Frown, col: '#E8A24B',   lbl: 'Flojo' },
  { v: 3, Icon: Meh,   col: NOAH.azul,   lbl: 'Normal' },
  { v: 4, Icon: Smile, col: NOAH.salvia, lbl: 'Bien' },
  { v: 5, Icon: Laugh, col: '#5C9A6B',   lbl: 'Muy bien' },
]

const INTENS = [
  { k: 'suave', lbl: 'Suave', rpe: 4 },
  { k: 'media', lbl: 'Media', rpe: 6 },
  { k: 'fuerte', lbl: 'Fuerte', rpe: 8 },
]

const card = (o = {}) => ({
  background: NOAH.surface, border: `1px solid ${NOAH.border}`, borderRadius: 20,
  boxShadow: '0 2px 4px rgba(41,45,41,0.04), 0 16px 36px -24px rgba(41,45,41,0.45)',
  padding: 16, ...o,
})
const eyebrow = { fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: NOAH.salvia }

// ¿HANNA pide confirmar? (divergencia grande, tendencia fuerte o meseta larga)
function hannaPide(puntos) {
  const pts = (puntos || []).filter(p => p.hanna_life != null).slice(-10)
  if (pts.length < 5) return false
  const last = pts[pts.length - 1]
  if (last.cuerpo != null && Math.abs(last.hanna_life - last.cuerpo) >= 8) return true
  const first = pts[pts.length - 5].hanna_life
  if (Math.abs(last.hanna_life - first) >= 12) return true   // tendencia marcada
  const ult = pts.slice(-6).map(p => p.hanna_life)
  if (ult.length >= 6 && Math.max(...ult) - Math.min(...ult) <= 3) return true  // meseta
  return false
}

export default function RegistroDiario({ atletaId, hannaPuntos = null }) {
  const [reg, setReg] = useState(null)
  const [cara, setCara] = useState(null)
  const [fuerza, setFuerza] = useState(null)       // true/false/null
  const [intens, setIntens] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [serie, setSerie] = useState(hannaPuntos)

  useEffect(() => {
    let vivo = true
    authFetch(`${API}/atletas/${atletaId}/registro`).then(j => {
      if (!vivo) return
      const d = j?.data || {}
      setReg(d)
      setCara(d.checkin_cara ?? null)
      setFuerza(d.fuerza ?? null)
    })
    if (!hannaPuntos) {
      authFetch(`${API}/atletas/${atletaId}/hanna_life?dias=14`).then(j => {
        if (vivo) setSerie(j?.data?.puntos || [])
      })
    }
    return () => { vivo = false }
  }, [atletaId, hannaPuntos])

  const pide = hannaPide(serie)

  const elegirCara = (v) => {
    setCara(v)
    authFetch(`${API}/atletas/${atletaId}/registro/checkin`, {
      method: 'POST', body: JSON.stringify({ cara: v }),
    })
  }

  const postFuerza = (f, inten = null) => {
    setGuardando(true)
    const rpe = inten ? INTENS.find(i => i.k === inten)?.rpe : null
    authFetch(`${API}/atletas/${atletaId}/registro/fuerza`, {
      method: 'POST',
      body: JSON.stringify({ fuerza: f, cross_tipo: f ? 'fuerza' : null, rpe, minutos: rpe ? 45 : null }),
    }).finally(() => setGuardando(false))
  }

  const elegirFuerza = (f) => {
    setFuerza(f)
    if (!f) { setIntens(null); postFuerza(false) }
    // si es Sí, esperamos a que elija intensidad (o la deja sin intensidad)
    else postFuerza(true, null)
  }
  const elegirIntens = (k) => { setIntens(k); postFuerza(true, k) }

  const caraSel = CARAS.find(c => c.v === cara)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* ── Check-in de 5 caras ── */}
      <div style={card({ borderColor: pide ? `${NOAH.salvia}55` : NOAH.border })}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={13} color={NOAH.salvia} strokeWidth={2.3} />
            <span style={eyebrow}>¿Cómo te sentís hoy?</span>
          </div>
          {pide && (
            <span style={{ fontFamily: F, fontSize: 9.5, fontWeight: 700, color: NOAH.salvia, padding: '3px 9px', borderRadius: 999, background: `${NOAH.salvia}16`, border: `1px solid ${NOAH.salvia}33` }}>HANNA quiere confirmar</span>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
          {CARAS.map(c => {
            const sel = cara === c.v
            return (
              <button key={c.v} onClick={() => elegirCara(c.v)} aria-label={c.lbl}
                style={{
                  flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5,
                  padding: '10px 0', borderRadius: 14, cursor: 'pointer',
                  border: `1px solid ${sel ? c.col : NOAH.border}`,
                  background: sel ? `${c.col}16` : 'transparent',
                  transform: sel ? 'translateY(-2px)' : 'none',
                  transition: 'all .16s ease',
                }}>
                <c.Icon size={26} color={sel ? c.col : NOAH.ink45} strokeWidth={sel ? 2.4 : 1.9} />
                <span style={{ fontFamily: F, fontSize: 9, fontWeight: sel ? 700 : 500, color: sel ? c.col : NOAH.ink45 }}>{c.lbl}</span>
              </button>
            )
          })}
        </div>
        {caraSel && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, fontFamily: F, fontSize: 11, color: NOAH.ink45 }}>
            <Check size={12} color={caraSel.col} /> Registrado — gracias, esto ayuda a afinar HANNA.
          </div>
        )}
      </div>

      {/* ── Toggle de fuerza / cross-training ── */}
      <div style={card()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <Dumbbell size={13} color={NOAH.coral} strokeWidth={2.3} />
          <span style={{ ...eyebrow, color: NOAH.coral }}>¿Entrenaste fuerza hoy?</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[['Sí', true], ['No', false]].map(([lbl, val]) => {
            const sel = fuerza === val
            const col = val ? NOAH.salvia : NOAH.ink45
            return (
              <button key={lbl} onClick={() => elegirFuerza(val)} disabled={guardando}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 14, cursor: 'pointer',
                  fontFamily: F, fontSize: 13, fontWeight: 700,
                  border: `1px solid ${sel ? col : NOAH.border}`,
                  background: sel ? (val ? NOAH.grafito : 'rgba(41,45,41,0.05)') : 'transparent',
                  color: sel ? (val ? '#F3F0E8' : NOAH.ink70) : NOAH.ink70,
                  transition: 'all .16s ease',
                }}>{lbl}</button>
            )
          })}
        </div>
        {fuerza === true && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontFamily: F, fontSize: 10.5, color: NOAH.ink45, marginBottom: 7 }}>Intensidad (opcional)</div>
            <div style={{ display: 'flex', gap: 7 }}>
              {INTENS.map(i => {
                const sel = intens === i.k
                return (
                  <button key={i.k} onClick={() => elegirIntens(i.k)}
                    style={{
                      flex: 1, padding: '8px 0', borderRadius: 999, cursor: 'pointer',
                      fontFamily: F, fontSize: 11.5, fontWeight: 700,
                      border: `1px solid ${sel ? NOAH.coral : NOAH.border}`,
                      background: sel ? `${NOAH.coral}16` : 'transparent',
                      color: sel ? NOAH.coral : NOAH.ink70,
                      transition: 'all .16s ease',
                    }}>{i.lbl}</button>
                )
              })}
            </div>
          </div>
        )}
        {reg?.sesiones_fuerza_semana > 0 && (
          <div style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, marginTop: 10 }}>
            {reg.sesiones_fuerza_semana} sesión{reg.sesiones_fuerza_semana > 1 ? 'es' : ''} de fuerza esta semana · carga complementaria aparte de la de Garmin
          </div>
        )}
      </div>
    </div>
  )
}
