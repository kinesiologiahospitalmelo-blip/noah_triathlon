path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# 1. Agregar el import, justo despues de los imports existentes
viejo_import = "import GraficoActividadStreams from './GraficoActividadStreams'\n"
nuevo_import = viejo_import + "import PantallaCarga from './PantallaCarga'\n"
if viejo_import in contenido and "import PantallaCarga" not in contenido:
    contenido = contenido.replace(viejo_import, nuevo_import, 1)
    cambios += 1

# 2. Reemplazar el export default function App() para que muestre
#    la pantalla de carga 2 segundos antes del contenido normal.
viejo_app = """export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireCoach><CoachApp /></RequireCoach>} />
        <Route path="/coach" element={<RequireCoach><CoachApp /></RequireCoach>} />
        <Route path="/atleta/:id" element={<RequireAtleta><AtletaPage /></RequireAtleta>} />
      </Routes>
    </BrowserRouter>
  )
}"""

nuevo_app = """export default function App() {
  const [cargando, setCargando] = useState(true)

  if (cargando) {
    return <PantallaCarga duracionMs={2000} onTerminar={() => setCargando(false)} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireCoach><CoachApp /></RequireCoach>} />
        <Route path="/coach" element={<RequireCoach><CoachApp /></RequireCoach>} />
        <Route path="/atleta/:id" element={<RequireAtleta><AtletaPage /></RequireAtleta>} />
      </Routes>
    </BrowserRouter>
  )
}"""

if viejo_app in contenido:
    contenido = contenido.replace(viejo_app, nuevo_app, 1)
    cambios += 1
else:
    print("AVISO: no se encontro el bloque exacto de 'export default function App'. Revisar a mano.")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"Cambios aplicados: {cambios} (esperado: 2)")
