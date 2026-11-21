// src/noahTheme.js — Sistema visual NOAH (Opción 1)
// SOLO estilo: colores, tipografías y helpers. No toca datos, lógica ni funciones.
// Importá estos tokens en Inicio y en las pantallas interiores para unificar el look.

// ── Paleta oficial (única). No agregar colores por fuera de estas familias. ──
export const NOAH = {
  marfil:  '#F3F0E8',   // fondo principal
  grafito: '#292D29',   // textos, estructura y navegación
  salvia:  '#78866B',   // identidad, rendimiento y estados
  coral:   '#E65B45',   // acentos y actividad
  azul:    '#4F8CC9',   // datos y elementos de SWIM

  // superficies / líneas derivadas del marfil y el grafito (sin colores nuevos)
  surface:   '#FBFAF6',                 // tarjeta sobre marfil (apenas más clara)
  surfaceAlt:'#ECE8DE',                 // zona/sección sutil
  border:    'rgba(41,45,41,0.12)',     // bordes finos (grafito translúcido)
  borderSoft:'rgba(41,45,41,0.07)',
  shadow:    '0 1px 2px rgba(41,45,41,0.05), 0 6px 20px -12px rgba(41,45,41,0.18)',

  // texto (escala de grafito)
  ink:   '#292D29',                     // principal
  ink70: 'rgba(41,45,41,0.72)',         // secundario
  ink45: 'rgba(41,45,41,0.46)',         // terciario / leyendas
}

// Identidad por deporte (se mantiene la relación de colores acordada)
export const DEPORTE = {
  swim: NOAH.azul,
  bike: NOAH.salvia,
  run:  NOAH.coral,
}

// Variaciones CONTROLADAS para diferenciar series dentro de un gráfico
// (tintes de las familias oficiales, no colores nuevos)
export const SERIES = {
  salvia:  ['#78866B', '#97A287', '#5C6952'],
  coral:   ['#E65B45', '#EF8773', '#C8432F'],
  azul:    ['#4F8CC9', '#79A9D8', '#366FA6'],
  grafito: ['#292D29', '#565A56', '#8A8D8A'],
}

// ── Tipografías ──
// Archivo: títulos, nav, labels, indicadores principales.
// IBM Plex Mono: SOLO números, unidades, %, biomarcadores y referencias numéricas.
export const FONT = {
  base: "'Archivo', system-ui, -apple-system, sans-serif",
  mono: "'IBM Plex Mono', ui-monospace, monospace",
}

// Helpers de estilo listos para usar en cualquier componente
export const titulo   = (size = 20, weight = 700) => ({ fontFamily: FONT.base, fontWeight: weight, fontSize: size, color: NOAH.ink, letterSpacing: -0.2 })
export const texto    = (size = 14, weight = 400) => ({ fontFamily: FONT.base, fontWeight: weight, fontSize: size, color: NOAH.ink70, lineHeight: 1.5 })
export const dato     = (size = 28, weight = 600) => ({ fontFamily: FONT.mono, fontWeight: weight, fontSize: size, color: NOAH.ink, fontVariantNumeric: 'tabular-nums', letterSpacing: -0.5 })
export const unidad   = (size = 12) => ({ fontFamily: FONT.mono, fontWeight: 400, fontSize: size, color: NOAH.ink45 })

export const card = {
  background: NOAH.surface,
  border: `1px solid ${NOAH.border}`,
  borderRadius: 16,
  boxShadow: NOAH.shadow,
}

// Eje/grilla/tooltip base para los gráficos (líneas limpias, grilla discreta)
export const chart = {
  grid:    'rgba(41,45,41,0.08)',
  axis:    NOAH.ink45,
  axisFont:{ fill: NOAH.ink45, fontSize: 12, fontFamily: FONT.mono },
  tooltip: { background: NOAH.surface, border: `1px solid ${NOAH.border}`, borderRadius: 10, fontSize: 13, color: NOAH.ink, fontFamily: FONT.base },
}

export default NOAH
