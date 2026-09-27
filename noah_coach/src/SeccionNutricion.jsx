// SeccionNutricion.jsx — 5 tabs internos
// Tab 1: Balance (gasto calculado real)
// Tab 2: 5 Comidas del día
// Tab 3: Durante sesión
// Tab 4: Post entreno
// Tab 5: NOAH Eat (IA parser)

import React, { useState, useEffect } from 'react'
import { Flame, Droplets, Zap, AlertTriangle, Send } from 'lucide-react'

const API = (window.location.hostname === 'localhost' || window.location.hostname.match(/^192\./))
  ? 'http://localhost:5000/api' : '/api'

function authFetch(url, opts = {}) {
  let token = null
  try { const r = localStorage.getItem('noah_sesion'); token = r ? JSON.parse(r)?.token : null } catch {}
  const h = { ...(opts.headers || {}) }
  if (token) h['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...opts, headers: h }).then(r => {
    if (r.status === 401) { localStorage.removeItem('noah_sesion'); window.location.href = '/login' }
    return r
  })
}

const C = {
  ink: 'rgba(255,255,255,0.92)', ink2: 'rgba(255,255,255,0.70)',
  ink3: 'rgba(255,255,255,0.45)', ink4: 'rgba(255,255,255,0.28)',
  accent: '#8B5CF6', cyan: '#06B6D4',
  ok: '#10B981', warn: '#F59E0B', bad: '#EF4444',
  cho: '#F59E0B', prot: '#A78BFA', grasa: '#38BDF8',
}

function Ring({ pct, color, size = 56, stroke = 4, children }) {
  const r = (size - stroke) / 2, circ = 2 * Math.PI * r
  const dash = circ * Math.min(Math.max(pct, 0), 1)
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color}88)`, transition: 'stroke-dasharray 0.8s ease' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        {children}
      </div>
    </div>
  )
}

function Card({ children, style }) {
  return <div style={{
    background: 'linear-gradient(165deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
    borderRadius: 14, padding: '16px 18px', border: '1px solid rgba(255,255,255,0.09)',
    boxShadow: '0 8px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.06)', ...style
  }}>{children}</div>
}

function Label({ children }) {
  return <div style={{ fontSize: 10, color: C.cyan, fontWeight: 700, letterSpacing: 1.5,
    textTransform: 'uppercase', marginBottom: 14 }}>{children}</div>
}

export default function SeccionNutricion({ atletaId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('balance')
  const [eatText, setEatText] = useState('')
  const [eatResult, setEatResult] = useState(null)
  const [eatLoading, setEatLoading] = useState(false)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    const f = new Date().toISOString().split('T')[0]
    authFetch(`${API}/atletas/${atletaId}/nutricion?fecha=${f}`)
      .then(r => r.json())
      .then(r => { setData(r.data || r); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId])

  const enviarEat = () => {
    if (!eatText.trim()) return
    setEatLoading(true)
    authFetch(`${API}/atletas/${atletaId}/nutricion/eat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto: eatText }),
    }).then(r => r.json())
      .then(r => { setEatResult(r.data || r); setEatLoading(false) })
      .catch(() => setEatLoading(false))
  }

  if (loading) return (
    <div style={{ padding: 50, textAlign: 'center' }}>
      <Flame size={28} color={C.warn} style={{ animation: 'pulse 2s infinite' }} />
      <div style={{ fontSize: 12, color: C.ink3, marginTop: 10 }}>Calculando plan nutricional...</div>
      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}`}</style>
    </div>
  )

  if (!data?.disponible) return (
    <div style={{ padding: 32, fontSize: 12, color: C.ink3 }}>{data?.error || 'Sin datos'}</div>
  )

  const gasto = data.gasto || {}
  const macros = data.macros || {}
  const tabs = [
    { id: 'balance', label: 'Balance' },
    { id: 'comidas', label: '5 Comidas' },
    { id: 'durante', label: 'Durante' },
    { id: 'post', label: 'Post' },
    { id: 'eat', label: 'NOAH Eat' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Tabs internos */}
      <div style={{ display: 'flex', gap: 0, borderRadius: 10, overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.08)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            flex: 1, padding: '10px 4px', border: 'none', cursor: 'pointer',
            background: tab === t.id ? 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(56,189,248,0.10))' : 'rgba(255,255,255,0.02)',
            borderBottom: tab === t.id ? `2px solid ${C.accent}` : '2px solid transparent',
            fontSize: 10, fontWeight: tab === t.id ? 700 : 500,
            color: tab === t.id ? C.ink : C.ink3, transition: 'all 0.2s',
          }}>{t.label}</button>
        ))}
      </div>

      {/* Alertas bio */}
      {(data.alertas || []).map((a, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', borderRadius: 10,
          background: a.tipo === 'critico' ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)',
          border: `1px solid ${a.tipo === 'critico' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)'}`,
        }}>
          <AlertTriangle size={13} color={a.tipo === 'critico' ? C.bad : C.warn} style={{ marginTop: 1, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 11, color: C.ink2 }}>{a.texto}</div>
            <div style={{ fontSize: 10, color: C.ink3, marginTop: 2 }}>{a.ajuste}</div>
          </div>
        </div>
      ))}

      {/* TAB: BALANCE */}
      {tab === 'balance' && (
        <Card>
          <Label>Balance energético del día</Label>
          <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: 16 }}>
            {[
              { label: 'CHO', val: macros.cho_g, sub: `${macros.cho_gkg}g/kg`, color: C.cho, max: 800 },
              { label: 'Proteína', val: macros.prot_g, sub: `${macros.prot_gkg}g/kg`, color: C.prot, max: 200 },
              { label: 'Grasa', val: macros.grasa_g, sub: `${macros.grasa_gkg}g/kg`, color: C.grasa, max: 150 },
            ].map(m => (
              <div key={m.label} style={{ textAlign: 'center' }}>
                <Ring pct={m.val ? m.val / m.max : 0} color={m.color} size={58} stroke={4}>
                  <span style={{ fontSize: 14, fontWeight: 800, color: m.color }}>{m.val || '?'}</span>
                </Ring>
                <div style={{ fontSize: 9, color: C.ink3, marginTop: 4, fontWeight: 600 }}>{m.label}</div>
                <div style={{ fontSize: 8, color: C.ink4 }}>{m.sub}</div>
              </div>
            ))}
          </div>
          {/* Desglose gasto */}
          {gasto.explicacion && Object.entries(gasto.explicacion).map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0',
              borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: 11 }}>
              <span style={{ color: C.ink3 }}>{v}</span>
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8, fontSize: 13, fontWeight: 700, color: C.accent }}>
            Total: {gasto.gasto_total} kcal
          </div>
        </Card>
      )}

      {/* TAB: 5 COMIDAS */}
      {tab === 'comidas' && (
        <Card>
          <Label>5 comidas del día</Label>
          {(data.comidas || []).map((c, i) => (
            <div key={i} style={{ padding: '12px 0', borderBottom: i < 4 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>{c.nombre}</span>
                <span style={{ fontSize: 10, color: C.ink4 }}>{c.kcal} kcal</span>
              </div>
              <div style={{ fontSize: 10, color: C.ink4, marginBottom: 6 }}>
                {c.cho_g}g CHO · {c.prot_g}g prot · {c.grasa_g}g grasa
              </div>
              {(c.alimentos || []).map((a, j) => (
                <div key={j} style={{ fontSize: 11, color: C.ink2, paddingLeft: 10, lineHeight: 1.6 }}>
                  • {a}
                </div>
              ))}
              {c.extras_bio && c.extras_bio.map((e, j) => (
                <div key={j} style={{ fontSize: 10, color: C.warn, paddingLeft: 10, marginTop: 4, fontStyle: 'italic' }}>
                  {e}
                </div>
              ))}
            </div>
          ))}
        </Card>
      )}

      {/* TAB: DURANTE */}
      {tab === 'durante' && (
        <Card>
          <Label>Durante la sesión</Label>
          {(data.durante || []).length === 0 ? (
            <div style={{ fontSize: 12, color: C.ink3, textAlign: 'center', padding: 20 }}>
              Sin sesiones hoy
            </div>
          ) : (data.durante || []).map((d, i) => (
            <div key={i} style={{ padding: '12px 0', borderBottom: i < (data.durante||[]).length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.ink, marginBottom: 8 }}>
                {d.deporte?.charAt(0).toUpperCase() + d.deporte?.slice(1)} — {d.duracion}'
              </div>
              {d.necesita_cho ? (
                <>
                  <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: C.cho }}>{d.cho_g_hora}</div>
                      <div style={{ fontSize: 9, color: C.ink4 }}>g CHO/h</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: C.grasa }}>{d.liquido_ml_hora}</div>
                      <div style={{ fontSize: 9, color: C.ink4 }}>ml/h</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: C.ink2 }}>{d.sodio_mg_hora}</div>
                      <div style={{ fontSize: 9, color: C.ink4 }}>mg Na/h</div>
                    </div>
                  </div>
                  {(d.productos || []).map((p, j) => (
                    <div key={j} style={{ fontSize: 11, color: C.ink2, paddingLeft: 10, lineHeight: 1.6 }}>• {p}</div>
                  ))}
                </>
              ) : (
                <div style={{ fontSize: 11, color: C.ink3 }}>
                  {(d.productos || [])[0] || 'Solo hidratación'}
                </div>
              )}
            </div>
          ))}
          {/* Hidratación total */}
          {data.hidratacion && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, padding: '10px 12px',
              borderRadius: 8, background: 'rgba(56,189,248,0.08)' }}>
              <Droplets size={14} color={C.grasa} />
              <span style={{ fontSize: 11, color: C.ink2 }}>
                Hidratación día: <strong>{data.hidratacion.ml_dia}ml</strong>
                {' '}({data.hidratacion.ml_base} base + {data.hidratacion.ml_entreno} entreno)
              </span>
            </div>
          )}
        </Card>
      )}

      {/* TAB: POST */}
      {tab === 'post' && (
        <Card>
          <Label>Recuperación post entreno</Label>
          {(data.post || []).length === 0 ? (
            <div style={{ fontSize: 12, color: C.ink3, textAlign: 'center', padding: 20 }}>
              Sin sesiones hoy
            </div>
          ) : (data.post || []).map((p, i) => (
            <div key={i} style={{ padding: '12px 0', borderBottom: i < (data.post||[]).length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>
                  Post {p.deporte}
                </span>
                {p.urgencia === 'alta' && (
                  <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                    background: 'rgba(239,68,68,0.15)', color: C.bad }}>Urgente (doble turno)</span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: C.prot }}>{p.proteina_g}</div>
                  <div style={{ fontSize: 9, color: C.ink4 }}>g proteína</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: C.cho }}>{p.cho_g}</div>
                  <div style={{ fontSize: 9, color: C.ink4 }}>g CHO</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: C.grasa }}>{p.ml_rehidratacion}</div>
                  <div style={{ fontSize: 9, color: C.ink4 }}>ml líquido</div>
                </div>
              </div>
              <div style={{ fontSize: 10, fontWeight: 600, color: C.ink3, marginBottom: 4 }}>Inmediato (30min):</div>
              {(p.inmediato || []).map((a, j) => (
                <div key={j} style={{ fontSize: 11, color: C.ink2, paddingLeft: 10, lineHeight: 1.6 }}>• {a}</div>
              ))}
              <div style={{ fontSize: 10, fontWeight: 600, color: C.ink3, marginTop: 6, marginBottom: 4 }}>Comida (1-2h):</div>
              {(p.comida || []).map((a, j) => (
                <div key={j} style={{ fontSize: 11, color: C.ink2, paddingLeft: 10, lineHeight: 1.6 }}>• {a}</div>
              ))}
            </div>
          ))}
        </Card>
      )}

      {/* TAB: NOAH EAT */}
      {tab === 'eat' && (
        <Card>
          <Label>NOAH Eat — Registrá lo que comiste</Label>
          <div style={{ fontSize: 11, color: C.ink3, marginBottom: 12, lineHeight: 1.5 }}>
            Escribí en lenguaje natural qué comiste y NOAH calcula los macros
            y te dice qué te falta para cerrar el balance del día.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={eatText} onChange={e => setEatText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && enviarEat()}
              placeholder="Ej: pechuga con ensalada y 200g fideos"
              style={{
                flex: 1, padding: '10px 14px', borderRadius: 10, fontSize: 12,
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                color: C.ink, outline: 'none',
              }} />
            <button onClick={enviarEat} disabled={eatLoading} style={{
              padding: '10px 16px', borderRadius: 10, border: 'none', cursor: 'pointer',
              background: eatLoading ? C.ink4 : `linear-gradient(135deg, ${C.accent}, #6D28D9)`,
              color: '#fff', fontSize: 12, fontWeight: 700,
            }}>
              {eatLoading ? '...' : <Send size={14} />}
            </button>
          </div>

          {eatResult?.comido?.ok && (
            <div style={{ marginTop: 16 }}>
              {/* Alimentos parseados */}
              <div style={{ fontSize: 10, fontWeight: 600, color: C.ink3, marginBottom: 6 }}>Lo que comiste:</div>
              {(eatResult.comido.alimentos || []).map((a, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: 11 }}>
                  <span style={{ color: C.ink2 }}>{a.nombre} ({a.cantidad_g}g)</span>
                  <span style={{ color: C.ink4 }}>{a.kcal} kcal</span>
                </div>
              ))}

              {/* Balance */}
              {eatResult.balance && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: C.ink3, marginBottom: 8 }}>Balance vs objetivo:</div>
                  <div style={{ display: 'flex', gap: 12 }}>
                    {[
                      { label: 'CHO', pct: eatResult.balance.pct?.cho, color: C.cho },
                      { label: 'Prot', pct: eatResult.balance.pct?.prot, color: C.prot },
                      { label: 'Grasa', pct: eatResult.balance.pct?.grasa, color: C.grasa },
                    ].map(m => (
                      <div key={m.label} style={{ flex: 1, textAlign: 'center' }}>
                        <Ring pct={(m.pct || 0) / 100} color={m.color} size={48} stroke={3.5}>
                          <span style={{ fontSize: 12, fontWeight: 800, color: m.color }}>{m.pct}%</span>
                        </Ring>
                        <div style={{ fontSize: 9, color: C.ink4, marginTop: 3 }}>{m.label}</div>
                      </div>
                    ))}
                  </div>
                  {/* Sugerencias */}
                  {(eatResult.balance.sugerencias || []).map((s, i) => (
                    <div key={i} style={{ fontSize: 11, color: C.warn, marginTop: 8, paddingLeft: 8,
                      borderLeft: `2px solid ${C.warn}` }}>{s}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {eatResult?.comido && !eatResult.comido.ok && (
            <div style={{ marginTop: 12, fontSize: 11, color: C.bad }}>
              {eatResult.comido.error || 'No se pudo parsear'}
            </div>
          )}
        </Card>
      )}

      <div style={{ fontSize: 9, color: C.ink4, textAlign: 'center' }}>
        NOAH Nutrition — no reemplaza consulta con nutricionista profesional
      </div>
    </div>
  )
}
