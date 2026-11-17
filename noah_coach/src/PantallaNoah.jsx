// src/PantallaNoah.jsx — Cáscara de pantalla interior (Opción 1) · terminación editorial premium
// Barra superior (volver + título) + sub-tabs + contenido + chat flotante + nav inferior.
// Cada sección se siente INDEPENDIENTE, luminosa y en identidad NOAH. Solo presentación.
// Props existentes preservadas; se agregan opcionales (foto, eyebrow) sin cambiar comportamiento.
import { ArrowLeft, Home, Dumbbell, BarChart3, User, MessageCircle } from 'lucide-react'
import { NOAH, FONT } from './noahTheme'

const NAV_DEFAULT = [
  { id: 'inicio', label: 'Inicio', Icon: Home },
  { id: 'entreno', label: 'Entreno', Icon: Dumbbell },
  { id: 'analisis', label: 'Análisis', Icon: BarChart3 },
  { id: 'perfil', label: 'Perfil', Icon: User },
]

// Glifo del FAB: ícono de chat claro (no el logo — el logo confundía).
function AsistenteGlyph() {
  return <MessageCircle size={24} color="#fff" strokeWidth={2.3} />
}

export default function PantallaNoah({
  title = '', onBack = () => {}, children, action = null,
  nav = NAV_DEFAULT, navActivo = '', onNav = () => {}, onAsistente = () => {},
  subtabs = null, subActivo = '', onSub = () => {},
  // ── opcionales (no alteran el comportamiento si no se pasan) ──
  eyebrow = '', foto = null, heroEyebrow = '', heroTitulo = '',
}) {
  // Más ancho en escritorio (aprovecha la pantalla y escala el gráfico SVG, que
  // crece con su contenedor → letra más grande). En móvil = 100% como antes.
  const MAXW = 'min(1040px, 100%)'
  return (
    <div style={{
      minHeight: '100vh',
      paddingBottom: 'calc(90px + env(safe-area-inset-bottom))',
      color: NOAH.ink, fontFamily: FONT.base,
      // Fondo con capas de color VISIBLES (salvia/coral/azul) para que el vidrio
      // esmerilado de las tarjetas tenga algo que difuminar y el efecto se note.
      // Tonos en paleta, más marcados que antes, sobre una base marfil apenas más profunda.
      background: `
        radial-gradient(120% 55% at 50% -12%, rgba(255,255,255,0.6) 0%, transparent 44%),
        radial-gradient(70% 48% at 88% 4%, rgba(230,91,69,0.14) 0%, transparent 52%),
        radial-gradient(64% 44% at 6% 16%, rgba(120,134,107,0.16) 0%, transparent 52%),
        radial-gradient(80% 50% at 94% 78%, rgba(79,140,201,0.13) 0%, transparent 56%),
        radial-gradient(72% 46% at 2% 96%, rgba(120,134,107,0.12) 0%, transparent 54%),
        linear-gradient(180deg, #EFEBE1 0%, #E9E4D8 100%)`,
      backgroundAttachment: 'fixed',
    }}>
      <style>{`.noah-scroll::-webkit-scrollbar{display:none}`}</style>

      {/* ── Barra superior editorial ── */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 40,
        background: 'rgba(243,240,232,0.72)',
        backdropFilter: 'blur(18px) saturate(1.3)', WebkitBackdropFilter: 'blur(18px) saturate(1.3)',
        borderBottom: `1px solid ${NOAH.borderSoft}`,
      }}>
        <div style={{ maxWidth: MAXW, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 12, padding: '12px clamp(14px,4vw,24px)' }}>
          <button onClick={onBack} aria-label="Volver" style={{
            width: 40, height: 40, borderRadius: 13, flex: '0 0 auto', display: 'grid', placeItems: 'center', cursor: 'pointer',
            background: 'rgba(251,250,246,0.75)', border: `1px solid ${NOAH.border}`, color: NOAH.grafito,
          }}>
            <ArrowLeft size={18} strokeWidth={2.2} />
          </button>
          <div style={{ flex: 1, minWidth: 0 }}>
            {eyebrow && (
              <div style={{ fontFamily: FONT.base, fontSize: 10, fontWeight: 700, letterSpacing: 1.6, textTransform: 'uppercase', color: NOAH.salvia, marginBottom: 1 }}>{eyebrow}</div>
            )}
            <h1 style={{ margin: 0, fontFamily: FONT.base, fontSize: 19, fontWeight: 800, letterSpacing: -0.5, color: NOAH.grafito, lineHeight: 1.12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{title}</h1>
          </div>
          {action}
          <img src="/assets/noah_logo_icono_negro.png" alt="" aria-hidden="true"
            onError={e => { e.currentTarget.style.display = 'none' }}
            style={{ width: 22, height: 22, objectFit: 'contain', opacity: 0.45, flex: '0 0 auto' }} />
        </div>
      </header>

      {/* ── Sub-tabs editoriales (subrayado, sin píldoras genéricas) ── */}
      {subtabs && subtabs.length > 0 && (
        <div style={{
          position: 'sticky', top: 65, zIndex: 35,
          background: 'rgba(243,240,232,0.72)',
          backdropFilter: 'blur(16px) saturate(1.3)', WebkitBackdropFilter: 'blur(16px) saturate(1.3)',
          borderBottom: `1px solid ${NOAH.borderSoft}`,
        }}>
          <div className="noah-scroll" style={{ maxWidth: MAXW, margin: '0 auto', display: 'flex', gap: 2, overflowX: 'auto', padding: '0 clamp(10px,4vw,22px)', scrollbarWidth: 'none' }}>
            {subtabs.map(st => {
              const on = subActivo === st.id
              return (
                <button key={st.id} onClick={() => onSub(st.id)} aria-current={on ? 'true' : undefined} style={{
                  flex: '0 0 auto', position: 'relative', padding: '13px 12px 12px', cursor: 'pointer', background: 'none', border: 'none',
                  fontFamily: FONT.base, fontSize: 13, fontWeight: on ? 800 : 600, letterSpacing: -0.1,
                  color: on ? NOAH.grafito : NOAH.ink45, whiteSpace: 'nowrap', transition: 'color .18s',
                }}>
                  {st.label}
                  <span style={{ position: 'absolute', left: 12, right: 12, bottom: 0, height: 2.5, borderRadius: 3, background: on ? NOAH.coral : 'transparent', transition: 'background .18s' }} />
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Foto de marca (opcional, solo donde se pasa) — tratamiento editorial,
            velo de MARFIL (nunca negro), iluminación natural conservada ── */}
      {foto && (
        <div style={{ maxWidth: MAXW, margin: '0 auto', padding: '16px clamp(12px,4vw,20px) 0' }}>
          <div style={{ position: 'relative', borderRadius: 22, overflow: 'hidden', border: `1px solid ${NOAH.border}`, boxShadow: NOAH.shadow, aspectRatio: '16 / 7', background: NOAH.surfaceAlt }}>
            <img src={foto} alt="" onError={e => { e.currentTarget.style.display = 'none' }}
              style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 26%', display: 'block' }} />
            {/* Velo de marfil anclado abajo (nunca negro): deja ver la foto con su
                iluminación natural y asienta el texto con buen contraste. */}
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(0deg, rgba(243,240,232,0.92) 0%, rgba(243,240,232,0.30) 30%, rgba(243,240,232,0) 58%)' }} />
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(243,240,232,0.42) 0%, rgba(243,240,232,0) 48%)' }} />
            {(heroEyebrow || heroTitulo) && (
              <div style={{ position: 'absolute', left: 20, bottom: 16, right: 20 }}>
                {heroEyebrow && <div style={{ fontFamily: FONT.base, fontSize: 10.5, fontWeight: 800, letterSpacing: 1.6, textTransform: 'uppercase', color: NOAH.coral, marginBottom: 2 }}>{heroEyebrow}</div>}
                {heroTitulo && <div style={{ fontFamily: FONT.base, fontSize: 23, fontWeight: 800, letterSpacing: -0.6, color: NOAH.grafito, lineHeight: 1.04, maxWidth: '72%' }}>{heroTitulo}</div>}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Contenido ── */}
      <main style={{ maxWidth: MAXW, margin: '0 auto', padding: '18px clamp(12px,4vw,20px) 0' }}>
        {children}
      </main>

      {/* ── Asistente NOAH (chat flotante, presente en toda pantalla) ── */}
      <button onClick={onAsistente} aria-label="Asistente NOAH" style={{
        position: 'fixed', right: 'max(18px, env(safe-area-inset-right))',
        bottom: 'calc(80px + env(safe-area-inset-bottom))',
        width: 56, height: 56, borderRadius: 999, zIndex: 60, cursor: 'pointer', border: 'none',
        background: `radial-gradient(130% 130% at 30% 22%, #F2806C 0%, ${NOAH.coral} 54%, #D44B37 100%)`,
        display: 'grid', placeItems: 'center',
        boxShadow: '0 2px 6px rgba(230,91,69,0.35), 0 16px 32px -10px rgba(230,91,69,0.6), inset 0 1px 1.5px rgba(255,255,255,0.45)',
        transition: 'transform .18s',
      }}
        onMouseDown={e => { e.currentTarget.style.transform = 'scale(0.94)' }}
        onMouseUp={e => { e.currentTarget.style.transform = 'scale(1)' }}
        onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)' }}>
        <AsistenteGlyph />
      </button>

      {/* ── Nav inferior premium ── */}
      <nav style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50,
        paddingBottom: 'env(safe-area-inset-bottom)',
        background: 'rgba(251,250,246,0.82)',
        backdropFilter: 'blur(18px) saturate(1.3)', WebkitBackdropFilter: 'blur(18px) saturate(1.3)',
        borderTop: `1px solid ${NOAH.borderSoft}`,
        boxShadow: '0 -8px 26px -18px rgba(41,45,41,0.3)',
      }}>
        <div style={{ maxWidth: 480, margin: '0 auto', height: 66, display: 'flex', padding: '0 8px' }}>
          {nav.map(n => {
            const on = navActivo === n.id
            return (
              <button key={n.id} onClick={() => onNav(n.id)} aria-current={on ? 'page' : undefined} style={{
                flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
                background: 'none', border: 'none', cursor: 'pointer',
              }}>
                <span style={{ display: 'grid', placeItems: 'center', width: 48, height: 30, borderRadius: 12, background: on ? 'rgba(230,91,69,0.1)' : 'transparent', transition: 'background .18s' }}>
                  <n.Icon size={20} color={on ? NOAH.coral : NOAH.ink45} strokeWidth={on ? 2.5 : 2} />
                </span>
                <span style={{ fontFamily: FONT.base, fontSize: 10, fontWeight: on ? 800 : 600, letterSpacing: 0.1, color: on ? NOAH.coral : NOAH.ink45 }}>{n.label}</span>
              </button>
            )
          })}
        </div>
      </nav>
    </div>
  )
}
