// src/CalibracionHanna.jsx — NOAH · Aprendizaje: tu percepción vs HANNA
// Autocontenido: fetchea /calibracion. Muestra qué tan alineada está la lectura
// de HANNA con cómo dice sentirse el atleta (check-in de 5 caras). Es la pata de
// aprendizaje: cuanto más registra, más se afina. Solo presentación premium.
import React, { useState, useEffect } from 'react'
import { Brain, Check } from 'lucide-react'
import { NOAH, FONT } from './noahTheme'

const F = FONT.base, M = FONT.mono

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { headers }).then(r => r.json().catch(() => ({})))
}

const TONO = { ok: NOAH.salvia, azul: NOAH.azul, warn: '#E8A24B', neutral: NOAH.ink45 }

const surface = (o = {}) => ({
  background: NOAH.surface, border: `1px solid ${NOAH.border}`, borderRadius: 16,
  boxShadow: '0 2px 4px rgba(41,45,41,0.04)', padding: 16, ...o,
})
const eyebrow = { fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: NOAH.ink45, textTransform: 'uppercase' }

export default function CalibracionHanna({ atletaId }) {
  const [d, setD] = useState(null)

  useEffect(() => {
    let vivo = true
    authFetch(`${API}/atletas/${atletaId}/calibracion`).then(j => {
      if (vivo) setD(j?.data || { disponible: false })
    }).catch(() => {})
    return () => { vivo = false }
  }, [atletaId])

  if (!d) return null
  const col = TONO[d.tono] || NOAH.ink45

  // Estado inicial (pocos datos): invitación a registrar
  if (!d.disponible) {
    return (
      <div style={surface({ marginBottom: 14, borderStyle: 'dashed' })}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <Brain size={13} color={NOAH.salvia} strokeWidth={2.3} />
          <span style={eyebrow}>HANNA aprende de vos</span>
        </div>
        <div style={{ fontFamily: F, fontSize: 12, color: NOAH.ink45, lineHeight: 1.5 }}>{d.msg}</div>
        {d.n > 0 && (
          <div style={{ fontFamily: M, fontSize: 10.5, color: NOAH.ink45, marginTop: 8 }}>{d.n} check-in{d.n === 1 ? '' : 's'} registrado{d.n === 1 ? '' : 's'}</div>
        )}
      </div>
    )
  }

  return (
    <div style={surface({ marginBottom: 14, borderColor: `${col}40` })}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Brain size={13} color={col} strokeWidth={2.3} />
          <span style={eyebrow}>Tu percepción vs HANNA</span>
        </div>
        <span style={{ fontFamily: M, fontSize: 10, color: NOAH.ink45 }}>{d.n} registros</span>
      </div>

      <div style={{ fontFamily: F, fontSize: 13.5, fontWeight: 700, color: col, marginBottom: 8 }}>{d.titulo}</div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
        <div style={{ flex: 1, padding: '10px 12px', borderRadius: 12, background: 'rgba(41,45,41,0.035)', border: `1px solid ${NOAH.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 5 }}><Check size={12} color={col} strokeWidth={2.6} /><span style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45 }}>Concordancia</span></div>
          <div style={{ fontFamily: M, fontSize: 24, fontWeight: 700, color: NOAH.ink, letterSpacing: -0.6, lineHeight: 1 }}>{d.concordancia}<span style={{ fontSize: 12, color: NOAH.ink45 }}>%</span></div>
        </div>
        <div style={{ flex: 1, padding: '10px 12px', borderRadius: 12, background: 'rgba(41,45,41,0.035)', border: `1px solid ${NOAH.border}` }}>
          <div style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, marginBottom: 5 }}>Tu sesgo vs HANNA</div>
          <div style={{ fontFamily: M, fontSize: 24, fontWeight: 700, color: Math.abs(d.sesgo) >= 15 ? col : NOAH.ink, letterSpacing: -0.6, lineHeight: 1 }}>{d.sesgo > 0 ? '+' : ''}{d.sesgo}</div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, padding: '9px 11px', borderRadius: 10, background: `${col}10`, border: `1px solid ${col}26` }}>
        <Brain size={12} color={col} strokeWidth={2.3} style={{ flex: '0 0 auto', marginTop: 1 }} />
        <span style={{ fontFamily: F, fontSize: 11.5, color: NOAH.ink70, lineHeight: 1.45 }}>{d.msg}</span>
      </div>
    </div>
  )
}
