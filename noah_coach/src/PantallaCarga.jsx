// PantallaCarga.jsx — Splash inicial de NOAH (identidad v2)
// Isologo de cubos + wordmark sobre marfil #F3F0E8, con barra de progreso.
// A juego con el Login en estilo NOAH. Isologo inlineado (nítido, sin asset).
import { useEffect, useState } from 'react'

const NOAH_ISO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 730 700" width="100%" height="100%" role="img" aria-label="NOAH"><g transform="translate(-380,-60)"><g id="isotipo"><polygon points="460,223 553,169 650,222 552,275" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="553,169 643,116 741,173 650,222" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="460,223 552,275 552,395 460,344" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="552,275 650,222 650,344 552,395" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="460,351 552,402 552,522 460,472" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="552,402 650,349 650,469 552,522" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="460,480 552,530 552,648 460,597" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="650,349 742,401 742,522 650,470" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="742,401 839,349 936,400 839,453" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="742,401 839,453 839,577 742,524" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="839,453 936,400 936,522 839,577" fill="#7054C7" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="650,224 741,173 830,224 738,275" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="650,224 738,275 738,395 650,344" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="738,275 830,224 830,345 738,395" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="552,529 650,475 650,597 552,648" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="650,475 742,528 742,650 650,597" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="742,528 839,580 936,527 839,474" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="742,528 839,580 839,704 742,650" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="839,580 936,527 936,650 839,704" fill="#F3F4F6" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="830,207 927,153 1032,207 935,261" fill="#399B7B" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="830,207 935,261 935,376 830,323" fill="#399B7B" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="935,261 1032,207 1032,324 935,376" fill="#399B7B" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="936,382 1032,331 1032,447 936,499" fill="#399B7B" stroke="#101522" stroke-width="3" stroke-linejoin="round"/><polygon points="936,507 1032,454 1032,574 936,626" fill="#399B7B" stroke="#101522" stroke-width="3" stroke-linejoin="round"/></g></g></svg>`

export default function PantallaCarga({ onTerminar, duracionMs = 5000 }) {
  const [progreso, setProgreso] = useState(0)

  useEffect(() => {
    const inicio = Date.now()
    const tick = setInterval(() => {
      const pct = Math.min(100, ((Date.now() - inicio) / duracionMs) * 100)
      setProgreso(pct)
      if (pct >= 100) {
        clearInterval(tick)
        setTimeout(() => onTerminar && onTerminar(), 150)
      }
    }, 30)
    return () => clearInterval(tick)
  }, [duracionMs, onTerminar])

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999, overflow: 'hidden',
      background: '#F3F0E8',
      fontFamily: "'Archivo', system-ui, -apple-system, sans-serif",
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    }}>
      <style>{`@keyframes noahFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}`}</style>

      {/* Glows de marca sutiles (salvia + coral) sobre marfil */}
      <div style={{ position: 'absolute', width: 500, height: 500, borderRadius: '50%', filter: 'blur(130px)', background: '#78866B', opacity: 0.14, left: -150, top: -130 }} />
      <div style={{ position: 'absolute', width: 420, height: 420, borderRadius: '50%', filter: 'blur(130px)', background: '#E65B45', opacity: 0.08, right: -130, bottom: -40 }} />

      {/* Marca */}
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{
          width: 110, height: 110, borderRadius: 26, background: '#101522',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'noahFloat 3.2s ease-in-out infinite',
          boxShadow: '0 20px 40px -18px rgba(41,45,41,0.5)',
        }}>
          <div style={{ width: '64%', height: '64%', lineHeight: 0 }}
            dangerouslySetInnerHTML={{ __html: NOAH_ISO_SVG }} />
        </div>
        <div style={{ display: 'flex', gap: 4, marginTop: 24 }}>
          {['N', 'O', 'A', 'H'].map((l, i) => (
            <span key={i} style={{ fontSize: 34, fontWeight: 800, letterSpacing: 7, color: '#292D29' }}>{l}</span>
          ))}
        </div>
        <div style={{ fontSize: 9.5, color: 'rgba(41,45,41,0.5)', letterSpacing: 2.6, textTransform: 'uppercase', fontWeight: 700, marginTop: 9 }}>
          Never Over, Always Higher
        </div>
      </div>

      {/* Barra de progreso */}
      <div style={{ position: 'absolute', bottom: '9%', width: '70%', maxWidth: 280, zIndex: 1 }}>
        <div style={{ height: 4, background: 'rgba(41,45,41,0.10)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${progreso}%`,
            background: 'linear-gradient(90deg, #78866B, #E65B45)',
            borderRadius: 99, transition: 'width 0.05s linear',
            boxShadow: '0 0 12px rgba(120,134,107,0.5)',
          }} />
        </div>
      </div>
    </div>
  )
}
