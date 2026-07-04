path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """function PerfilDisponibilidad({ atletaId, atleta }) {
  const dep = atleta?.deporte_ppal || atleta?.deporte || 'running'"""

nuevo = """function PerfilFisiologico({ atletaId, atleta }) {
  const [lthrRun,  setLthrRun]  = useState(atleta?.lthr_run  || '')
  const [lthrBike, setLthrBike] = useState(atleta?.lthr_bike || '')
  const [lthrSwim, setLthrSwim] = useState(atleta?.lthr_swim || '')
  const [ftp,      setFtp]      = useState(atleta?.ftp_watts || '')
  const [css,      setCss]      = useState(atleta?.css_100m  || '')
  const [hrMax,    setHrMax]    = useState(atleta?.hr_max    || '')
  const [pesoKg,   setPesoKg]   = useState(atleta?.peso_kg   || '')
  const [saving,   setSaving]   = useState(false)
  const [saved,    setSaved]    = useState(false)

  // Si cambia el atleta seleccionado, recargar los valores mostrados
  useEffect(() => {
    setLthrRun(atleta?.lthr_run  || '')
    setLthrBike(atleta?.lthr_bike || '')
    setLthrSwim(atleta?.lthr_swim || '')
    setFtp(atleta?.ftp_watts || '')
    setCss(atleta?.css_100m  || '')
    setHrMax(atleta?.hr_max    || '')
    setPesoKg(atleta?.peso_kg   || '')
  }, [atletaId])

  const guardar = async () => {
    setSaving(true)
    try {
      const body = {
        lthr_run:  lthrRun  ? Number(lthrRun)  : null,
        lthr_bike: lthrBike ? Number(lthrBike) : null,
        lthr_swim: lthrSwim ? Number(lthrSwim) : null,
        ftp_watts: ftp      ? Number(ftp)      : null,
        css_100m:  css      ? Number(css)      : null,
        hr_max:    hrMax    ? Number(hrMax)    : null,
        peso_kg:   pesoKg   ? Number(pesoKg)   : null,
      }
      await axios.put(`${API}/atletas/${atletaId}`, body, { headers: { 'Content-Type': 'application/json' } })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      alert('Error guardando: ' + (e?.response?.data?.error || e.message))
    }
    setSaving(false)
  }

  const Campo = ({ label, value, setValue, unit, placeholder }) => (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, color: C.text2, marginBottom: 4 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input type="number" value={value} placeholder={placeholder}
          onChange={e => setValue(e.target.value)}
          style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${C.border}`,
            background: C.bg2, color: C.text, fontSize: 14 }} />
        <span style={{ fontSize: 12, color: C.text2, minWidth: 50 }}>{unit}</span>
      </div>
    </div>
  )

  return (
    <div style={{ marginBottom: 28, paddingBottom: 24, borderBottom: `1px solid ${C.border}` }}>
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Perfil fisiologico</div>
      <div style={{ fontSize: 12, color: C.text2, marginBottom: 16 }}>
        Estos valores son la base real de las zonas de entrenamiento de este atleta.
        Si quedan vacios, NOAH usa un valor generico de referencia (no personalizado).
      </div>
      <Campo label="LTHR Running"  value={lthrRun}  setValue={setLthrRun}  unit="bpm" placeholder="ej: 165" />
      <Campo label="LTHR Ciclismo" value={lthrBike} setValue={setLthrBike} unit="bpm" placeholder="ej: 158" />
      <Campo label="LTHR Natacion" value={lthrSwim} setValue={setLthrSwim} unit="bpm" placeholder="ej: 150" />
      <Campo label="FTP (potencia umbral)" value={ftp} setValue={setFtp} unit="W" placeholder="ej: 220" />
      <Campo label="CSS (ritmo critico natacion)" value={css} setValue={setCss} unit="min/100m" placeholder="ej: 1.75" />
      <Campo label="FC Maxima" value={hrMax} setValue={setHrMax} unit="bpm" placeholder="ej: 190" />
      <Campo label="Peso" value={pesoKg} setValue={setPesoKg} unit="kg" placeholder="ej: 72" />
      <button onClick={guardar} disabled={saving}
        style={{ padding: '10px 20px', borderRadius: 8, border: 'none',
          background: saved ? C.success : C.purple, color: '#fff', fontWeight: 700,
          cursor: saving ? 'wait' : 'pointer', fontSize: 13 }}>
        {saving ? 'Guardando...' : saved ? '✓ Guardado' : 'Guardar perfil fisiologico'}
      </button>
    </div>
  )
}

function PerfilDisponibilidad({ atletaId, atleta }) {
  const dep = atleta?.deporte_ppal || atleta?.deporte || 'running'"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto de PerfilDisponibilidad. No se modifico el archivo.")
elif "function PerfilFisiologico" in contenido:
    print("AVISO: PerfilFisiologico ya existe, no se duplico.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK 1/2: componente PerfilFisiologico agregado a App.js")

# ── Insertar <PerfilFisiologico /> antes de <PerfilDisponibilidad /> en el tab 'perfil' ──
viejo_render = "{tab==='perfil'&&atletaId&&<PerfilDisponibilidad atletaId={atletaId} atleta={atleta} />}"
nuevo_render = "{tab==='perfil'&&atletaId&&(<><PerfilFisiologico atletaId={atletaId} atleta={atleta} /><PerfilDisponibilidad atletaId={atletaId} atleta={atleta} /></>)}"

if viejo_render in contenido:
    contenido = contenido.replace(viejo_render, nuevo_render, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK 2/2: PerfilFisiologico insertado en la pestaña Perfil, antes de Disponibilidad")
else:
    print("AVISO 2/2: no se encontro el render de PerfilDisponibilidad para insertar antes")
