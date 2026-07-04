path = r'C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx'

old = """  const [vista,      setVista]   = React.useState(null) // null | 'torque' | 'wbal'
  const [data,       setData]    = React.useState(null)
  const [cargando,   setCargando] = React.useState(false)"""

new = """  const [vista,      setVista]   = useState(null) // null | 'torque' | 'wbal'
  const [data,       setData]    = useState(null)
  const [cargando,   setCargando] = useState(false)"""

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Bug 3 resuelto — React.useState reemplazado por useState")
else:
    print("❌ No matcheó el texto exacto — verificar manualmente")
