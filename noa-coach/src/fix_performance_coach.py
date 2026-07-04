path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. ActividadRecienteCoach — 7 requests individuales → 1 de rango ───────
viejo_1 = """    let cancelado = false
    const dias = []
    for (let i = 6; i >= 0; i--)
      dias.push(new Date(Date.now() - i * 86400000).toISOString().slice(0, 10))

    Promise.all(dias.map(d =>
      authFetch(`${API}/atletas/${atletaId}/actividades_dia?fecha=${d}&exacto=true`)
        .then(r => r.json())
        .then(r => ({ dia: d, acts: r.data?.actividades || [] }))
        .catch(() => ({ dia: d, acts: [] }))
    )).then(results => {
      if (cancelado) return
      const acts7 = {}
      results.forEach(({ dia, acts }) => { acts7[dia] = acts })"""

nuevo_1 = """    let cancelado = false
    const desde = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    const hasta  = new Date().toISOString().slice(0, 10)

    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desde}&hasta=${hasta}`)
      .then(r => r.json())
      .then(r => {
        if (cancelado) return
        const acts7 = {}
        ;(r.data?.actividades || []).forEach(a => {
          const dia = a.fecha?.slice(0, 10)
          if (dia) { if (!acts7[dia]) acts7[dia] = []; acts7[dia].push(a) }
        })
        const results = Object.entries(acts7).map(([dia, acts]) => ({ dia, acts }))"""

if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1)
    cambios += 1
    print("OK 1/2: ActividadRecienteCoach ahora usa 1 request de rango (7 dias)")
else:
    print("AVISO 1/2: no se encontro el bloque de ActividadRecienteCoach")

# ── 2. CalendarioCoach (mes) — 30 requests individuales → 1 de rango ───────
viejo_2 = """    setCargando(true); setActsMes({})
    const dias = []
    for (let d = new Date(primerDia); d <= ultimoDia; d.setDate(d.getDate()+1))
      dias.push(d.toISOString().slice(0,10))
    Promise.all(dias.map(dia =>
      authFetch(`${API}/atletas/${atletaId}/actividades_dia?fecha=${dia}&exacto=true`)
        .then(r=>r.json()).then(r=>({ dia, acts: r.data?.actividades||[] }))
        .catch(()=>({ dia, acts:[] }))
    )).then(results => {
      const map = {}; results.forEach(({dia,acts})=>{ map[dia]=acts }); setActsMes(map); setCargando(false)
    })"""

nuevo_2 = """    setCargando(true); setActsMes({})
    const desde = primerDia.toISOString().slice(0, 10)
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
    print("OK 2/2: CalendarioCoach (mes) ahora usa 1 request de rango")
else:
    print("AVISO 2/2: no se encontro el bloque de CalendarioCoach")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 2)")
