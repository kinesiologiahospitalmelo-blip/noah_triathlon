path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. SesionDelDia — 7 requests individuales → 1 request de rango ──────────
viejo_1 = """    const dias = []
    for (let i = 6; i >= 0; i--)
      dias.push(new Date(Date.now() - i * 86400000).toISOString().slice(0, 10))
    Promise.all(dias.map(d =>
      authFetch(`${API}/atletas/${atletaId}/actividades_dia?fecha=${d}&exacto=true`)
        .then(r => r.json())
        .then(r => ({ dia: d, acts: r.data?.actividades || [] }))
        .catch(() => ({ dia: d, acts: [] }))
    )).then(results => {
      const map = {}
      results.forEach(({ dia, acts }) => { map[dia] = acts })
      setActs7(map)
      setActs(map[fechaSel] ?? map[hoy] ?? [])
    })"""

nuevo_1 = """    const desde = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    const hasta  = new Date().toISOString().slice(0, 10)
    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desde}&hasta=${hasta}`)
      .then(r => r.json())
      .then(r => {
        const map = {}
        ;(r.data?.actividades || []).forEach(a => {
          const dia = a.fecha?.slice(0, 10)
          if (dia) { if (!map[dia]) map[dia] = []; map[dia].push(a) }
        })
        setActs7(map)
        setActs(map[fechaSel] ?? map[hoy] ?? [])
      })
      .catch(() => { setActs7({}); setActs([]) })"""

if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1)
    cambios += 1
    print("OK 1/2: SesionDelDia ahora usa 1 request de rango (7 dias)")
else:
    print("AVISO 1/2: no se encontro el bloque de SesionDelDia")

# ── 2. CalendarioMensual — 30 requests individuales → 1 request de rango ────
viejo_2 = """    const dias = []
    for (let d = new Date(primerDia); d <= ultimoDia; d.setDate(d.getDate()+1))
      dias.push(d.toISOString().slice(0,10))
    Promise.all(dias.map(dia =>
      authFetch(`${API}/atletas/${atletaId}/actividades_dia?fecha=${dia}&exacto=true`)
        .then(r=>r.json()).then(r=>({ dia, acts: r.data?.actividades||[] }))
        .catch(()=>({ dia, acts:[] }))
    )).then(results => {
      const map = {}; results.forEach(({dia,acts})=>{ map[dia]=acts }); setActsMes(map); setCargando(false)
    })"""

nuevo_2 = """    const desde = primerDia.toISOString().slice(0, 10)
    const hasta  = ultimoDia.toISOString().slice(0, 10)
    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desde}&hasta=${hasta}`)
      .then(r => r.json())
      .then(r => {
        const map = {}
        ;(r.data?.actividades || []).forEach(a => {
          const dia = a.fecha?.slice(0, 10)
          if (dia) { if (!map[dia]) map[dia] = []; map[dia].push(a) }
        })
        setActsMes(map)
        setCargando(false)
      })
      .catch(() => { setActsMes({}); setCargando(false) })"""

if viejo_2 in contenido:
    contenido = contenido.replace(viejo_2, nuevo_2, 1)
    cambios += 1
    print("OK 2/2: CalendarioMensual ahora usa 1 request de rango (mes completo)")
else:
    print("AVISO 2/2: no se encontro el bloque de CalendarioMensual")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 2)")
