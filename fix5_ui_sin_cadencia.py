path = r'C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js'

old = """            </Card>
          )}

          {/* Gráfico W'bal */}"""

new = """            </Card>
          )}

          {vista === 'torque' && scatterData.length === 0 && (
            <div style={{ padding:'16px', borderRadius:10,
              background:'rgba(248,81,73,0.08)', border:'1px solid rgba(248,81,73,0.25)',
              fontSize:13, color:'#FCA5A5', textAlign:'center', lineHeight:1.6 }}>
              ⚠ Sin datos de cadencia para esta actividad.<br/>
              El medidor de potencia no transmite RPM a Garmin — sin cadencia no se puede calcular Torque (N·m = P / RPM).<br/>
              <span style={{ fontSize:11, color:'rgba(252,165,165,0.6)' }}>
                Verificá en Garmin Connect si la actividad tiene cadencia de ciclismo.
              </span>
            </div>
          )}

          {/* Gráfico W'bal */}"""

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK Fix 5 - mensaje sin cadencia agregado")
else:
    print("ERROR - no matcheo el texto exacto")
