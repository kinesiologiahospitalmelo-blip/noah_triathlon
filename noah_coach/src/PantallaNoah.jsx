// src/PantallaNoah.jsx — Cáscara de pantalla interior (Opción 1)
// Barra superior (volver + título) + contenido + chat flotante + nav inferior.
// Hace que cada sección se sienta INDEPENDIENTE y en el estilo nuevo,
// sin el marco oscuro del dashboard viejo. Solo presentación.
import { ArrowLeft, Home, Dumbbell, BarChart3, User, MessageCircle } from 'lucide-react'
import { NOAH, FONT } from './noahTheme'

const NAV_DEFAULT = [
  { id: 'inicio', label: 'Inicio', Icon: Home },
  { id: 'entreno', label: 'Entreno', Icon: Dumbbell },
  { id: 'analisis', label: 'Análisis', Icon: BarChart3 },
  { id: 'perfil', label: 'Perfil', Icon: User },
]

export default function PantallaNoah({
  title = '', onBack = () => {}, children, action = null,
  nav = NAV_DEFAULT, navActivo = '', onNav = () => {}, onAsistente = () => {},
}) {
  return (
    <div style={{
      minHeight: '100vh', paddingBottom: 92, color: NOAH.ink, fontFamily: FONT.base,
      background: `radial-gradient(120% 55% at 88% -6%, rgba(230,91,69,0.07) 0%, transparent 44%),
        radial-gradient(90% 48% at 8% 104%, rgba(120,134,107,0.08) 0%, transparent 50%),
        ${NOAH.marfil}`,
    }}>
      {/* Barra superior */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 40, display: 'flex', alignItems: 'center', gap: 10,
        padding: '12px 14px', background: 'rgba(243,240,232,0.86)', backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)', borderBottom: `1px solid ${NOAH.border}`,
      }}>
        <button onClick={onBack} aria-label="Volver" style={{
          width: 38, height: 38, borderRadius: 12, display: 'grid', placeItems: 'center', cursor: 'pointer',
          background: NOAH.surface, border: `1px solid ${NOAH.border}`, boxShadow: NOAH.shadow,
        }}>
          <ArrowLeft size={18} color={NOAH.grafito} strokeWidth={2.2} />
        </button>
        <span style={{ flex: 1, fontFamily: FONT.base, fontSize: 18, fontWeight: 800, letterSpacing: -0.4, color: NOAH.grafito }}>{title}</span>
        {action}
      </header>

      {/* Contenido de la sección */}
      <main style={{ maxWidth: 640, margin: '0 auto', padding: '14px 12px 0' }}>
        {children}
      </main>

      {/* Asistente (chat flotante, presente en toda pantalla) */}
      <button onClick={onAsistente} aria-label="Asistente NOAH" style={{
        position: 'fixed', right: 18, bottom: 80, width: 54, height: 54, borderRadius: 999, zIndex: 60,
        background: `linear-gradient(145deg, #EF6B57, ${NOAH.coral})`, border: 'none', cursor: 'pointer',
        display: 'grid', placeItems: 'center', boxShadow: '0 10px 26px -8px rgba(230,91,69,0.65)',
      }}>
        <MessageCircle size={24} color="#fff" />
      </button>

      {/* Nav inferior */}
      <nav style={{ position: 'fixed', bottom: 0, left: 0, right: 0, height: 64, background: 'rgba(251,250,246,0.92)', borderTop: `1px solid ${NOAH.border}`, backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)', zIndex: 50 }}>
        <div style={{ maxWidth: 440, margin: '0 auto', height: '100%', display: 'flex' }}>
          {nav.map(n => {
            const on = navActivo === n.id
            return (
              <button key={n.id} onClick={() => onNav(n.id)} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, background: 'none', border: 'none', cursor: 'pointer' }}>
                <n.Icon size={20} color={on ? NOAH.coral : NOAH.ink45} strokeWidth={on ? 2.4 : 2} />
                <span style={{ fontFamily: FONT.base, fontSize: 10.5, fontWeight: on ? 700 : 500, color: on ? NOAH.coral : NOAH.ink45 }}>{n.label}</span>
              </button>
            )
          })}
        </div>
      </nav>
    </div>
  )
}
