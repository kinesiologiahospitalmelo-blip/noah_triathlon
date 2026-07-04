path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Cycling: watts_min/watts_max → w_min/w_max y w_kg_min → wkg_min ──────
viejo_bike = """            <div style={{textAlign:'right'}}>
              {z.watts_min && (
                <div style={{fontSize:12,fontWeight:700,color:zColor}}>
                  {z.watts_min}–{z.watts_max}W
                </div>
              )}
              {z.hr_min && (
                <div style={{fontSize:11,color:NOAH_C.ink3}}>
                  HR {z.hr_min}–{z.hr_max}
                </div>
              )}
              {z.w_kg_min && (
                <div style={{fontSize:10,color:NOAH_C.ink4}}>
                  {z.w_kg_min}–{z.w_kg_max} w/kg
                </div>
              )}
            </div>"""

nuevo_bike = """            <div style={{textAlign:'right'}}>
              {(z.w_min != null) && (
                <div style={{fontSize:12,fontWeight:700,color:zColor}}>
                  {z.w_min}–{z.w_max ? z.w_max+'W' : '∞'}
                </div>
              )}
              {z.pct_ftp && (
                <div style={{fontSize:11,color:NOAH_C.ink3}}>{z.pct_ftp} FTP</div>
              )}
              {z.hr_min && (
                <div style={{fontSize:11,color:NOAH_C.ink3}}>
                  HR {z.hr_min}–{z.hr_max}
                </div>
              )}
              {z.wkg_min && (
                <div style={{fontSize:10,color:NOAH_C.ink4}}>
                  {z.wkg_min}–{z.wkg_max||'∞'} w/kg
                </div>
              )}
            </div>"""

if viejo_bike in contenido:
    contenido = contenido.replace(viejo_bike, nuevo_bike, 1)
    cambios += 1
    print("OK 1/2: ZonasCyclingTable corregido (w_min/w_max/wkg_min)")
else:
    print("AVISO 1/2: no se encontro el bloque de cycling")

# ── 2. Swimming: pace_min/pace_max → pace_100m_min/pace_100m_max ────────────
viejo_swim = """            <td style={{padding:'8px 10px',color:NOAH_C.ink3,fontVariantNumeric:'tabular-nums'}}>
              {z.pace_min}–{z.pace_max}
            </td>
            <td style={{padding:'8px 10px',color:NOAH_C.ink3}}>{z.hr_min}–{z.hr_max}</td>"""

nuevo_swim = """            <td style={{padding:'8px 10px',color:NOAH_C.ink3,fontVariantNumeric:'tabular-nums'}}>
              {z.pace_100m_min || z.pace_min || '--'} – {z.pace_100m_max || z.pace_max || '--'}
            </td>
            <td style={{padding:'8px 10px',color:NOAH_C.ink3}}>{z.hr_min||'--'}–{z.hr_max||'--'}</td>"""

if viejo_swim in contenido:
    contenido = contenido.replace(viejo_swim, nuevo_swim, 1)
    cambios += 1
    print("OK 2/2: ZonasSwimTable corregido (pace_100m_min/max)")
else:
    print("AVISO 2/2: no se encontro el bloque de swimming")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 2)")
