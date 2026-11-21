// sesion.js — cerrar sesión (usado por las pantallas v2: Inicio y PantallaNoah)
const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'

export function cerrarSesion() {
  try {
    const raw = localStorage.getItem('noah_sesion')
    const s = raw ? JSON.parse(raw) : null
    if (s?.token) {
      fetch(`${API}/logout`, { method: 'POST', headers: { Authorization: `Bearer ${s.token}` }, keepalive: true }).catch(() => {})
    }
  } catch {}
  try { localStorage.removeItem('noah_sesion') } catch {}
  window.location.href = '/login'
}
