// PantallaCarga.jsx — Splash inicial de NOAH.
// Isotipo maestro (3D) sobre marfil, girando en 3D real (placa con espesor),
// wordmark + barra de progreso. A juego con el Login en estilo NOAH.
import { useEffect, useState } from 'react'

const NOAH_ISO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 580" width="100%" height="100%" role="img" aria-label="NOAH"><g stroke="#111827" stroke-width="1.1" stroke-linejoin="round" stroke-linecap="round"><path d="M 13 116 L 111 173 L 198 120 L 331 201 L 413 154 L 410 137 L 197 13 Z" fill="#8464D8"/><path d="M 13 118 L 12 456 L 98 513 L 107 514 L 111 521 L 112 176 L 121 169 L 111 174 Z" fill="#6449B9"/><path d="M 186 127 L 198 123 L 198 247 L 330 326 L 332 201 L 198 121 Z" fill="#6449B9"/><path d="M 197 123 L 113 176 L 111 522 L 112 298 L 198 248 Z" fill="#523CA1"/><path d="M 639 89 L 646 94 L 555 148 L 556 257 L 489 300 L 490 423 L 464 409 L 489 427 L 489 533 L 646 439 L 646 93 Z" fill="#288264"/><path d="M 336 203 L 335 330 L 489 423 L 491 297 L 486 299 Z" fill="#369474"/><path d="M 418 68 L 418 174 L 543 248 L 553 259 L 549 261 L 555 257 L 554 148 L 559 145 L 554 148 Z" fill="#369474"/><path d="M 418 67 L 554 147 L 644 94 L 511 16 Z" fill="#48B592"/><path d="M 336 204 L 486 298 L 554 257 L 418 175 L 417 158 Z" fill="#48B592"/><path d="M 116 300 L 120 297 L 116 300 L 116 525 L 212 476 L 215 437 L 424 569 L 486 534 L 485 425 L 400 476 Z" fill="#D6D7DC"/><path d="M 117 300 L 400 475 L 484 427 L 198 253 Z" fill="#F3F4F6"/></g></svg>`

const S = 120, T = 30   // lado de la placa y espesor (px)

function Logo3D() {
  const faceBase = { position: 'absolute', top: '50%', left: '50%', backfaceVisibility: 'hidden' }
  const tile = {
    ...faceBase, width: S, height: S, borderRadius: 8, background: '#0B1020',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.05)',
  }
  const lado = (tf, w, h) => ({
    ...faceBase, width: w, height: h,
    background: 'linear-gradient(#0A0E1A,#05070E)', transform: tf,
  })
  return (
    <div style={{ perspective: '900px', animation: 'noahFloat 3.6s ease-in-out infinite' }}>
      <div className="noah3d" style={{ position: 'relative', width: S, height: S, transformStyle: 'preserve-3d', animation: 'noahSpin 8s linear infinite' }}>
        {/* cara frontal */}
        <div style={{ ...tile, transform: `translate(-50%,-50%) translateZ(${T / 2}px)` }}>
          <div style={{ width: '74%', height: '74%', lineHeight: 0 }} dangerouslySetInnerHTML={{ __html: NOAH_ISO_SVG }} />
        </div>
        {/* cara trasera (logo espejado para que se lea bien) */}
        <div style={{ ...tile, transform: `translate(-50%,-50%) rotateY(180deg) translateZ(${T / 2}px)` }}>
          <div style={{ width: '74%', height: '74%', lineHeight: 0, transform: 'scaleX(-1)' }} dangerouslySetInnerHTML={{ __html: NOAH_ISO_SVG }} />
        </div>
        {/* cantos (espesor) */}
        <div style={lado(`translate(-50%,-50%) rotateY(90deg) translateZ(${S / 2}px)`, T, S)} />
        <div style={lado(`translate(-50%,-50%) rotateY(-90deg) translateZ(${S / 2}px)`, T, S)} />
        <div style={lado(`translate(-50%,-50%) rotateX(90deg) translateZ(${S / 2}px)`, S, T)} />
        <div style={lado(`translate(-50%,-50%) rotateX(-90deg) translateZ(${S / 2}px)`, S, T)} />
      </div>
    </div>
  )
}

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
      <style>{`
        @keyframes noahSpin{from{transform:rotateX(-14deg) rotateY(0deg)}to{transform:rotateX(-14deg) rotateY(360deg)}}
        @keyframes noahFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
        @media (prefers-reduced-motion: reduce){.noah3d{animation:none !important;transform:rotateX(-14deg) rotateY(-26deg)}}
      `}</style>

      {/* Glows de marca sutiles (salvia + coral) sobre marfil */}
      <div style={{ position: 'absolute', width: 500, height: 500, borderRadius: '50%', filter: 'blur(130px)', background: '#78866B', opacity: 0.14, left: -150, top: -130 }} />
      <div style={{ position: 'absolute', width: 420, height: 420, borderRadius: '50%', filter: 'blur(130px)', background: '#E65B45', opacity: 0.08, right: -130, bottom: -40 }} />

      {/* Marca */}
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ height: 150, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Logo3D />
        </div>
        {/* sombra de contacto */}
        <div style={{ width: 90, height: 14, borderRadius: '50%', background: 'rgba(41,45,41,0.16)', filter: 'blur(8px)', marginTop: -6 }} />
        <div style={{ display: 'flex', gap: 4, marginTop: 22 }}>
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
