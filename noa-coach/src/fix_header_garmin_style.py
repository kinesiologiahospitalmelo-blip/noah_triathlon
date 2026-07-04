path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """      {/* HEADER — imagen de fondo + glassmorphism flotante */}
      <div style={{
        position: 'relative',
        overflow: 'hidden',
        minHeight: 90,
      }}>
        {/* Imagen de fondo según deporte */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: deporte === 'cycling'
            ? 'url(https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=1400&q=80)'
            : deporte === 'swimming'
            ? 'url(https://images.unsplash.com/photo-1560090995-01632a28895b?w=1400&q=80)'
            : deporte === 'triatlon'
            ? 'url(https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=1400&q=80)'
            : 'url(https://images.unsplash.com/photo-1502904550040-7534597429ae?w=1400&q=80)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 30%',
          opacity: 0.65,
          filter: 'saturate(1.3)',
        }}/>
        {/* Overlay gradiente */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(90deg, rgba(10,15,30,0.82) 0%, rgba(10,15,30,0.50) 60%, rgba(10,15,30,0.75) 100%)',
        }}/>
        {/* Contenido flotante */}
        <div style={{
          position: 'relative', zIndex: 1,
          backdropFilter: 'blur(2px)',
          WebkitBackdropFilter: 'blur(2px)',
          padding: '14px 16px',
          display: 'flex', flexDirection:'column', gap:10,
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}>
          {/* Fila 1 — logo + nombre/fecha, prolijo y simétrico */}
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:10 }}>
            <div>
              <div style={{ display:'flex', alignItems:'baseline', gap:1 }}>
                {['N','O','A','H'].map((l,i) => (
                  <span key={i} className="noah-logo-letter" style={{
                    fontSize: 22, fontWeight: 900, letterSpacing: 5,
                    color: i%2===1 ? NOAH_C.run : '#fff',
                    animationDelay: `${i*0.08}s`,
                  }}>{l}</span>
                ))}
              </div>
              <div style={{ fontSize:8, color:'rgba(255,255,255,0.3)', letterSpacing:2, marginTop:2, textTransform:'uppercase' }}>
                Never Over, Always Higher
              </div>
            </div>
            <div style={{ textAlign:'right', minWidth:0, display:'flex', alignItems:'flex-start', gap:8 }}>
              <div>
                <div className="noah-athlete-name" style={{ fontSize:13, fontWeight:700, color:'#fff',
                  letterSpacing:0.2, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', maxWidth:170 }}>
                  {atleta?.nombre||'...'} — {deporteLabel}
                </div>
                <div style={{ fontSize:10, color:'rgba(255,255,255,0.4)', marginTop:2 }}>{hoyStr}</div>
              </div>
              <button onClick={() => {
                try {
                  const raw = localStorage.getItem('noah_sesion')
                  const s = raw ? JSON.parse(raw) : null
                  if (s?.token) authFetch(`${API}/logout`, { method:'POST' }).catch(()=>{})
                } catch {}
                localStorage.removeItem('noah_sesion')
                window.location.href = '/login'
              }} title="Cerrar sesión" style={{
                width:24, height:24, borderRadius:'50%', flexShrink:0, marginTop:1,
                background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)',
                color:'rgba(255,255,255,0.4)', display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <LogOut size={12}/>
              </button>
            </div>
          </div>

          {/* Fila 2 — alerta de sync (si hay) en ancho completo, nunca cortada */}
          {syncStatus?.alerta && (
            <div style={{ fontSize:10, color:'#FCA5A5', background:'rgba(239,68,68,0.12)',
              padding:'4px 10px', borderRadius:7, border:'1px solid rgba(239,68,68,0.2)',
              display:'flex', alignItems:'center', gap:5, width:'fit-content' }}>
              <AlertTriangle size={11}/> Sin sync hace {syncStatus.dias_sin_sync}d
            </div>
          )}

          {/* Fila 3 — botones de sync, simétricos, mitad y mitad del ancho */}
          <div style={{display:'flex',gap:8}}>
            <button className="noah-sync-btn" onClick={async () => {
              setSyncBioLoad(true); setSyncResult(null)
              try {
                const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'bio'})
                const bio = r.data.data
                const detalles = [bio?.body_battery&&`BB:${bio.body_battery}`,bio?.hr_reposo&&`FC:${bio.hr_reposo}`,bio?.sleep_h&&`Sueño:${bio.sleep_h}h`,bio?.hrv_ms&&`HRV:${bio.hrv_ms}ms`].filter(Boolean).join(' · ')
                setSyncResult({tipo:'bio', ok:bio?.exito, msg: bio?.exito ? `Biomarcadores actualizados${detalles?' — '+detalles:''}` : 'Sin datos nuevos de Garmin'})
                axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
                axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
              } catch { setSyncResult({tipo:'bio', ok:false, msg:'Error al sincronizar'}) }
              setSyncBioLoad(false)
            }} disabled={syncBioLoading} style={{
              flex:1, padding:'7px 12px', borderRadius:9, fontSize:11, fontWeight:700,
              background:'rgba(255,255,255,0.1)', color:'rgba(255,255,255,0.8)',
              border:'1px solid rgba(255,255,255,0.18)', cursor:'pointer',
              display:'flex', alignItems:'center', justifyContent:'center', gap:5,
            }}>
              {syncBioLoading ? <RotateCw size={12} className="noah-spin"/> : <Moon size={12}/>} Bio
            </button>
            <button className="noah-sync-btn" onClick={async () => {
              setSyncLoading(true); setSyncResult(null)
              try {
                const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'actividad'})
                const out = r.data.data?.output || ''
                const nueva = out.includes('nueva') || out.includes('guardado')
                setSyncResult({tipo:'actividad', ok:r.data.data?.exito, nueva, msg: nueva ? 'Actividad descargada' : 'Sin actividades nuevas'})
                if (nueva) {
                  axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
                  axios.get(`${API}/atletas/${id}/ultima_actividad`).then(r2=>setActReal(r2.data.data?.actividad)).catch(()=>{})
                  axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
                }
              } catch { setSyncResult({tipo:'actividad', ok:false, msg:'Error al sincronizar'}) }
              setSyncLoading(false)
            }} disabled={syncLoading} style={{
              flex:1, padding:'7px 12px', borderRadius:9, fontSize:11, fontWeight:700,
              background:'rgba(255,255,255,0.1)', color:'rgba(255,255,255,0.8)',
              border:'1px solid rgba(255,255,255,0.18)', cursor:'pointer',
              display:'flex', alignItems:'center', justifyContent:'center', gap:5,
            }}>
              {syncLoading ? <RotateCw size={12} className="noah-spin"/> : <Footprints size={12}/>} Actividad
            </button>
          </div>
        </div>
      </div>"""

nuevo = """      {/* HEADER estilo Garmin — imagen hero grande (30% pantalla), nombre prominente,
          botones de sync en azul solido, logo pequeno arriba. Toda la logica de
          sync se mantiene identica — solo cambia la presentacion visual. */}
      <div style={{ position:'relative', overflow:'hidden', minHeight:200 }}>

        {/* Imagen hero — ocupa todo el bloque */}
        <div style={{
          position:'absolute', inset:0,
          backgroundImage:'url(/assets/hero_dashboard.png)',
          backgroundSize:'cover',
          backgroundPosition:'center 25%',
          filter:'brightness(0.75) saturate(1.1)',
        }}/>

        {/* Overlay — degradado de abajo hacia arriba, igual que Garmin */}
        <div style={{
          position:'absolute', inset:0,
          background:'linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.5) 50%, rgba(0,0,0,0.2) 100%)',
        }}/>

        {/* Contenido encima de la imagen */}
        <div style={{ position:'relative', zIndex:1, display:'flex', flexDirection:'column', height:'100%', minHeight:200 }}>

          {/* Fila superior — logo + logout */}
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'12px 16px' }}>
            <div style={{ display:'flex', alignItems:'baseline', gap:1 }}>
              {['N','O','A','H'].map((l,i) => (
                <span key={i} className="noah-logo-letter" style={{
                  fontSize:20, fontWeight:900, letterSpacing:4,
                  color: i%2===1 ? NOAH_C.run : '#fff',
                  animationDelay:`${i*0.08}s`,
                }}>{l}</span>
              ))}
            </div>
            <button onClick={() => {
              try {
                const raw = localStorage.getItem('noah_sesion')
                const s = raw ? JSON.parse(raw) : null
                if (s?.token) authFetch(`${API}/logout`, { method:'POST' }).catch(()=>{})
              } catch {}
              localStorage.removeItem('noah_sesion')
              window.location.href = '/login'
            }} title="Cerrar sesión" style={{
              width:28, height:28, borderRadius:'50%', flexShrink:0,
              background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.15)',
              color:'rgba(255,255,255,0.5)', display:'flex', alignItems:'center', justifyContent:'center',
              cursor:'pointer',
            }}>
              <LogOut size={13}/>
            </button>
          </div>

          {/* Espacio flexible — empuja el nombre hacia abajo como en Garmin */}
          <div style={{ flex:1 }}/>

          {/* Nombre del atleta + fecha + alerta */}
          <div style={{ padding:'0 16px 14px' }}>
            <div className="noah-athlete-name" style={{
              fontSize:22, fontWeight:800, color:'#fff',
              letterSpacing:0.2, textShadow:'0 2px 8px rgba(0,0,0,0.6)',
            }}>
              {atleta?.nombre||'...'}
            </div>
            <div style={{ fontSize:12, color:'rgba(255,255,255,0.55)', marginTop:2, marginBottom:10 }}>
              {deporteLabel} · {hoyStr}
            </div>

            {/* Alerta de sync */}
            {syncStatus?.alerta && (
              <div style={{ fontSize:10, color:'#FCA5A5', background:'rgba(239,68,68,0.12)',
                padding:'4px 10px', borderRadius:7, border:'1px solid rgba(239,68,68,0.2)',
                display:'flex', alignItems:'center', gap:5, width:'fit-content', marginBottom:10 }}>
                <AlertTriangle size={11}/> Sin sync hace {syncStatus.dias_sin_sync}d
              </div>
            )}

            {/* Botones de sync — azul solido estilo Garmin */}
            <div style={{ display:'flex', gap:10 }}>
              <button className="noah-sync-btn" onClick={async () => {
                setSyncBioLoad(true); setSyncResult(null)
                try {
                  const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'bio'})
                  const bio = r.data.data
                  const detalles = [bio?.body_battery&&`BB:${bio.body_battery}`,bio?.hr_reposo&&`FC:${bio.hr_reposo}`,bio?.sleep_h&&`Sueño:${bio.sleep_h}h`,bio?.hrv_ms&&`HRV:${bio.hrv_ms}ms`].filter(Boolean).join(' · ')
                  setSyncResult({tipo:'bio', ok:bio?.exito, msg: bio?.exito ? `Biomarcadores actualizados${detalles?' — '+detalles:''}` : 'Sin datos nuevos de Garmin'})
                  axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
                  axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
                } catch { setSyncResult({tipo:'bio', ok:false, msg:'Error al sincronizar'}) }
                setSyncBioLoad(false)
              }} disabled={syncBioLoading} style={{
                flex:1, padding:'10px 16px', borderRadius:10, fontSize:13, fontWeight:700,
                background:'#007AFF', color:'#fff',
                border:'none', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center', gap:6,
                boxShadow:'0 4px 12px rgba(0,122,255,0.4)',
              }}>
                {syncBioLoading ? <RotateCw size={13} className="noah-spin"/> : <Moon size={13}/>} Sincronizar Bio
              </button>
              <button className="noah-sync-btn" onClick={async () => {
                setSyncLoading(true); setSyncResult(null)
                try {
                  const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'actividad'})
                  const out = r.data.data?.output || ''
                  const nueva = out.includes('nueva') || out.includes('guardado')
                  setSyncResult({tipo:'actividad', ok:r.data.data?.exito, nueva, msg: nueva ? 'Actividad descargada' : 'Sin actividades nuevas'})
                  if (nueva) {
                    axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
                    axios.get(`${API}/atletas/${id}/ultima_actividad`).then(r2=>setActReal(r2.data.data?.actividad)).catch(()=>{})
                    axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
                  }
                } catch { setSyncResult({tipo:'actividad', ok:false, msg:'Error al sincronizar'}) }
                setSyncLoading(false)
              }} disabled={syncLoading} style={{
                flex:1, padding:'10px 16px', borderRadius:10, fontSize:13, fontWeight:700,
                background:'#007AFF', color:'#fff',
                border:'none', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center', gap:6,
                boxShadow:'0 4px 12px rgba(0,122,255,0.4)',
              }}>
                {syncLoading ? <RotateCw size={13} className="noah-spin"/> : <Footprints size={13}/>} Sincronizar Actividad
              </button>
            </div>
          </div>
        </div>
      </div>"""

if viejo in contenido:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: header rediseñado estilo Garmin")
else:
    print("ERROR: no se encontro el bloque exacto")
