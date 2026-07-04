// PantallaCarga.jsx — Pantalla de carga inicial de NOAH
// Usa la imagen real (assets/pantalla_carga.png) de fondo, tal cual.
// Solo se anima la barra de progreso de carga encima.
import { useEffect, useState } from 'react'
import imagenCarga from './assets/pantalla_carga.png'

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
      position: 'fixed', inset: 0, zIndex: 9999,
      background: '#DCEBFA',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `url(${imagenCarga})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
      }} />
      <div style={{ position: 'absolute', bottom: '6%', width: '70%', maxWidth: 280 }}>
        <div style={{ height: 4, background: 'rgba(15,39,71,0.15)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${progreso}%`,
            background: 'linear-gradient(90deg, #1F6FEB, #0EA5A0)',
            borderRadius: 99, transition: 'width 0.05s linear',
          }} />
        </div>
      </div>
    </div>
  )
}
