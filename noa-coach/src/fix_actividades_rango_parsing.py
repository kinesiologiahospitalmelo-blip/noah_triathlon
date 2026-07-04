import re

archivos = [
    r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx",
    r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js",
]

# El backend (/actividades_rango) devuelve data.actividades como un OBJETO
# { "2026-06-01": [...], "2026-06-02": [...] }, no como un array plano.
# Los 4 fixes anteriores asumieron mal que era un array y le hacian
# .forEach() directo -> "forEach is not a function". La correccion: usar
# el objeto tal cual viene (ya esta agrupado por fecha), sin reconstruirlo
# a mano con un forEach.

cambios_totales = 0

for path in archivos:
    with open(path, "r", encoding="utf-8") as f:
        contenido = f.read()

    cambios_archivo = 0

    # Patron A: el que arma 'map' a partir de un forEach sobre actividades
    patron_a = re.compile(
        r"const map = \{\}\s*\n\s*;\(r\.data\?\.actividades \|\| \[\]\)\.forEach\(a => \{\s*\n"
        r"\s*const dia = a\.fecha\?\.slice\(0, 10\)\s*\n"
        r"\s*if \(dia\) \{ if \(!map\[dia\]\) map\[dia\] = \[\]; map\[dia\]\.push\(a\) \}\s*\n"
        r"\s*\}\)",
        re.MULTILINE
    )
    nuevo_a = "const map = r.data?.actividades || {}"
    contenido_nuevo, n = patron_a.subn(nuevo_a, contenido)
    cambios_archivo += n
    contenido = contenido_nuevo

    # Patron B: variante con 'acts7' en vez de 'map' (ActividadRecienteCoach / SesionDelDia)
    patron_b = re.compile(
        r"const acts7 = \{\}\s*\n\s*;\(r\.data\?\.actividades \|\| \[\]\)\.forEach\(a => \{\s*\n"
        r"\s*const dia = a\.fecha\?\.slice\(0, 10\)\s*\n"
        r"\s*if \(dia\) \{ if \(!acts7\[dia\]\) acts7\[dia\] = \[\]; acts7\[dia\]\.push\(a\) \}\s*\n"
        r"\s*\}\)",
        re.MULTILINE
    )
    nuevo_b = "const acts7 = r.data?.actividades || {}"
    contenido_nuevo, n = patron_b.subn(nuevo_b, contenido)
    cambios_archivo += n
    contenido = contenido_nuevo

    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"{path}: {cambios_archivo} reemplazo(s)")
    cambios_totales += cambios_archivo

print(f"\nTotal cambios: {cambios_totales} (esperado: 4)")
