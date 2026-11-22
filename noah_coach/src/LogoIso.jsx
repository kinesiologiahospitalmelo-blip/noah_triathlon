// LogoIso.jsx — Isotipo NOAH (maestro). SVG inline, nítido a cualquier tamaño.
// Por defecto va dentro de un tile azul noche (#0B1020) para que el símbolo
// resalte también sobre fondos claros (marfil).
const NOAH_ISO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 580" width="100%" height="100%" role="img" aria-label="NOAH"><g stroke="#111827" stroke-width="1.1" stroke-linejoin="round" stroke-linecap="round"><path d="M 13 116 L 111 173 L 198 120 L 331 201 L 413 154 L 410 137 L 197 13 Z" fill="#8464D8"/><path d="M 13 118 L 12 456 L 98 513 L 107 514 L 111 521 L 112 176 L 121 169 L 111 174 Z" fill="#6449B9"/><path d="M 186 127 L 198 123 L 198 247 L 330 326 L 332 201 L 198 121 Z" fill="#6449B9"/><path d="M 197 123 L 113 176 L 111 522 L 112 298 L 198 248 Z" fill="#523CA1"/><path d="M 639 89 L 646 94 L 555 148 L 556 257 L 489 300 L 490 423 L 464 409 L 489 427 L 489 533 L 646 439 L 646 93 Z" fill="#288264"/><path d="M 336 203 L 335 330 L 489 423 L 491 297 L 486 299 Z" fill="#369474"/><path d="M 418 68 L 418 174 L 543 248 L 553 259 L 549 261 L 555 257 L 554 148 L 559 145 L 554 148 Z" fill="#369474"/><path d="M 418 67 L 554 147 L 644 94 L 511 16 Z" fill="#48B592"/><path d="M 336 204 L 486 298 L 554 257 L 418 175 L 417 158 Z" fill="#48B592"/><path d="M 116 300 L 120 297 L 116 300 L 116 525 L 212 476 L 215 437 L 424 569 L 486 534 L 485 425 L 400 476 Z" fill="#D6D7DC"/><path d="M 117 300 L 400 475 L 484 427 L 198 253 Z" fill="#F3F4F6"/></g></svg>`

export default function LogoIso({ size = 34, radius = 10, tile = true, bg = '#0B1020', style = {} }) {
  if (!tile) {
    return <div style={{ width: size, height: size * 580 / 660, lineHeight: 0, flex: '0 0 auto', ...style }}
      dangerouslySetInnerHTML={{ __html: NOAH_ISO_SVG }} />
  }
  return (
    <div style={{
      width: size, height: size, borderRadius: radius, background: bg, flex: '0 0 auto',
      display: 'flex', alignItems: 'center', justifyContent: 'center', ...style,
    }}>
      <div style={{ width: '74%', height: '74%', lineHeight: 0 }}
        dangerouslySetInnerHTML={{ __html: NOAH_ISO_SVG }} />
    </div>
  )
}
