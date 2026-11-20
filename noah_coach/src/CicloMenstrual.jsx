// src/CicloMenstrual.jsx — NOAH · Ciclo menstrual (atletas femeninas)
// Autocontenido: fetchea /ciclo_menstrual y permite registrar el inicio de un
// período. Solo presentación premium (paleta v2, sin emojis). Informativo:
// contextualiza el entrenamiento por fase, no da indicación médica.
import React, { useState, useEffect, useCallback } from 'react'
import { Droplet, Plus, Check, Calendar } from 'lucide-react'
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

const FASE_COL = {
  menstrual:  NOAH.coral,
  folicular:  NOAH.salvia,
  ovulatoria: NOAH.azul,
  lutea:      '#E8A24B',
}

const card = (o = {}) => ({
  background: NOAH.surface, border: `1px solid ${NOAH.border}`, borderRadius: 20,
  boxShadow: '0 2px 4px rgba(41,45,41,0.04), 0 16px 36px -24px rgba(41,45,41,0.45)',
  padding: 16, ...o,
})
const eyebrow = { fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: NOAH.coral }

// Anillo de progreso del ciclo (día actual sobre largo del ciclo)
function AnilloCiclo({ dia, largo, col }) {
  const R = 30, C = 2 * Math.PI * R
  const pct = Math.max(0, Math.min(1, (dia || 0) / (largo || 28)))
  return (
    <svg width="76" height="76" viewBox="0 0 76 76" style={{ flex: '0 0 auto' }}>
      <circle cx="38" cy="38" r={R} fill="none" stroke="rgba(41,45,41,0.08)" strokeWidth="6" />
      <circle cx="38" cy="38" r={R} fill="none" stroke={col} strokeWidth="6" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - pct)} transform="rotate(-90 38 38)" />
      <text x="38" y="35" textAnchor="middle" fontFamily={M} fontSize="20" fontWeight="700" fill={NOAH.ink}>{dia ?? '—'}</text>
      <text x="38" y="49" textAnchor="middle" fontFamily={F} fontSize="8" fill={NOAH.ink45}>día</text>
    </svg>
  )
}

export default function CicloMenstrual({ atletaId }) {
  const [c, setC] = useState(null)
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10))
  const [abrir, setAbrir] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [okMsg, setOkMsg] = useState(false)

  const cargar = useCallback(() => {
    authFetch(`${API}/atletas/${atletaId}/ciclo_menstrual`).then(j => setC(j?.data || { disponible: false }))
  }, [atletaId])

  useEffect(() => { cargar() }, [cargar])

  const registrar = () => {
    setGuardando(true)
    authFetch(`${API}/atletas/${atletaId}/ciclo_menstrual`, {
      method: 'POST', body: JSON.stringify({ fecha_inicio: fecha }),
    }).then(() => {
      setOkMsg(true); setAbrir(false)
      setTimeout(() => setOkMsg(false), 2500)
      cargar()
    }).finally(() => setGuardando(false))
  }

  if (!c) return null
  const col = FASE_COL[c.fase] || NOAH.coral

  return (
    <div style={card({ borderColor: c.disponible ? `${col}44` : NOAH.border })}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Droplet size={13} color={NOAH.coral} strokeWidth={2.3} />
          <span style={eyebrow}>Ciclo menstrual</span>
        </div>
        {!abrir && (
          <button onClick={() => setAbrir(true)} style={{
            display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 10px', borderRadius: 999,
            border: `1px solid ${NOAH.border}`, background: 'transparent', cursor: 'pointer',
            fontFamily: F, fontSize: 10.5, fontWeight: 700, color: NOAH.ink70,
          }}><Plus size={12} /> Registrar inicio</button>
        )}
      </div>

      {c.disponible ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <AnilloCiclo dia={c.dia_ciclo} largo={c.largo_ciclo} col={col} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 11px', borderRadius: 999, background: `${col}18`, border: `1px solid ${col}33`, marginBottom: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: col }} />
              <span style={{ fontFamily: F, fontSize: 12, fontWeight: 700, color: col }}>Fase {c.fase_label}</span>
            </div>
            <div style={{ fontFamily: F, fontSize: 11, color: NOAH.ink70, lineHeight: 1.45 }}>{c.fase_nota}</div>
            <div style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, marginTop: 7 }}>
              Próximo período estimado en {c.dias_para_proximo} día{c.dias_para_proximo === 1 ? '' : 's'} · ciclo ~{c.largo_ciclo}d
            </div>
          </div>
        </div>
      ) : (
        <div style={{ fontFamily: F, fontSize: 11.5, color: NOAH.ink45, lineHeight: 1.5 }}>
          Registrá el inicio de tu período para seguir tu ciclo y leer el entrenamiento por fase. Los datos son privados y ayudan a interpretar tu HANNA.
        </div>
      )}

      {abrir && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${NOAH.border}` }}>
          <div style={{ fontFamily: F, fontSize: 10.5, color: NOAH.ink45, marginBottom: 7 }}>¿Qué día empezó tu período?</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, flex: 1, padding: '9px 11px', borderRadius: 12, border: `1px solid ${NOAH.border}`, background: 'rgba(41,45,41,0.03)' }}>
              <Calendar size={14} color={NOAH.ink45} />
              <input type="date" value={fecha} max={new Date().toISOString().slice(0, 10)}
                onChange={e => setFecha(e.target.value)}
                style={{ border: 'none', background: 'transparent', fontFamily: M, fontSize: 13, color: NOAH.ink, outline: 'none', width: '100%' }} />
            </div>
            <button onClick={registrar} disabled={guardando} style={{
              padding: '0 16px', borderRadius: 12, border: 'none', cursor: 'pointer',
              background: NOAH.coral, color: '#fff', fontFamily: F, fontSize: 12, fontWeight: 700,
            }}>{guardando ? '…' : 'Guardar'}</button>
          </div>
        </div>
      )}

      {okMsg && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, fontFamily: F, fontSize: 11, color: NOAH.salvia }}>
          <Check size={12} color={NOAH.salvia} /> Inicio registrado.
        </div>
      )}
    </div>
  )
}
