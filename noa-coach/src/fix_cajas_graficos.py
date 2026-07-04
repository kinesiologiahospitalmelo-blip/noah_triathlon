path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Cuadro "Analisis NOAH" — agrandar tipografia y padding ──────────────
viejo_narrativa = """      {narrativa.length>0&&(
        <div style={{
          padding:'12px 16px',borderRadius:10,
          background:isDark?'rgba(99,102,241,0.08)':'#F0F0FF',
          border:`1px solid ${isDark?'rgba(99,102,241,0.2)':'#C7D2FE'}`,
          backdropFilter:'blur(8px)',
        }}>
          <div style={{fontSize:10,fontWeight:700,color:isDark?'#A5B4FC':'#4F46E5',
            textTransform:'uppercase',letterSpacing:0.8,marginBottom:8,display:'flex',alignItems:'center',gap:5}}>
            <Brain size={12}/> Análisis NOAH
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:4}}>
            {narrativa.map((f,i)=>(
              <div key={i} style={{fontSize:11,color:isDark?'rgba(255,255,255,0.75)':'#374151',
                lineHeight:1.5,paddingLeft:10,borderLeft:`2px solid ${isDark?'rgba(99,102,241,0.4)':'#818CF8'}`}}>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}"""

nuevo_narrativa = """      {narrativa.length>0&&(
        <div style={{
          padding:'18px 20px',borderRadius:14,
          background:isDark?'rgba(99,102,241,0.08)':'#F0F0FF',
          border:`1px solid ${isDark?'rgba(99,102,241,0.2)':'#C7D2FE'}`,
          backdropFilter:'blur(8px)',
        }}>
          <div style={{fontSize:13,fontWeight:700,color:isDark?'#A5B4FC':'#4F46E5',
            textTransform:'uppercase',letterSpacing:0.8,marginBottom:12,display:'flex',alignItems:'center',gap:6}}>
            <Brain size={16}/> Análisis NOAH
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:10}}>
            {narrativa.map((f,i)=>(
              <div key={i} style={{fontSize:14,color:isDark?'rgba(255,255,255,0.85)':'#374151',
                lineHeight:1.6,paddingLeft:12,borderLeft:`2px solid ${isDark?'rgba(99,102,241,0.4)':'#818CF8'}`}}>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}"""

if viejo_narrativa in contenido:
    contenido = contenido.replace(viejo_narrativa, nuevo_narrativa, 1)
    cambios += 1
    print("OK 1/3: cuadro Analisis NOAH agrandado")
else:
    print("AVISO 1/3: no se encontro el bloque exacto de Analisis NOAH")

# ── 2. Grafico HRV/riesgo viral — quitar marco propio ───────────────────────
viejo_grafico_hrv = """      <div style={{
        background:bg,borderRadius:12,padding:'10px 6px',
        border:`1px solid ${brdr}`,overflowX:'auto',
        backdropFilter:isDark?'blur(16px)':'none',
        boxShadow:isDark?'0 8px 32px rgba(0,0,0,0.4)':'0 2px 8px rgba(0,0,0,0.06)',
      }}>"""

nuevo_grafico_hrv = """      <div style={{
        background:'transparent',padding:'10px 0',
        overflowX:'auto',
      }}>"""

if viejo_grafico_hrv in contenido:
    contenido = contenido.replace(viejo_grafico_hrv, nuevo_grafico_hrv, 1)
    cambios += 1
    print("OK 2/3: marco del grafico HRV removido")
else:
    print("AVISO 2/3: no se encontro el bloque exacto del grafico HRV")

# ── 3. PMC Chart — quitar marco propio ──────────────────────────────────────
viejo_pmc = """    <div style={{
      borderRadius:20, overflow:'hidden',
      background:'linear-gradient(160deg,rgba(8,9,20,0.99),rgba(12,13,28,0.97))',
      boxShadow:'0 24px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)',
      border:'1px solid rgba(255,255,255,0.07)',
    }}>"""

nuevo_pmc = """    <div style={{
      borderRadius:0, overflow:'visible',
      background:'transparent',
    }}>"""

if viejo_pmc in contenido:
    contenido = contenido.replace(viejo_pmc, nuevo_pmc, 1)
    cambios += 1
    print("OK 3/3: marco del PMC chart removido")
else:
    print("AVISO 3/3: no se encontro el bloque exacto del PMC chart")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\\nTotal cambios aplicados: {cambios} (esperado: 3)")
