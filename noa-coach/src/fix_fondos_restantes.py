path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. STATUS BAR (la bandeja que envuelve HANNA LIFE + CTL/ATL/TSB) ────────
viejo_1 = "background:'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015))', backdropFilter:'blur(20px) saturate(150%)', WebkitBackdropFilter:'blur(20px) saturate(150%)', borderBottom:'1px solid rgba(255,255,255,0.07)', padding:'14px 16px'"
nuevo_1 = "background:'transparent', padding:'14px 16px'"

if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1)
    cambios += 1
    print("OK 1/2: STATUS BAR sin fondo gris")
else:
    print("AVISO 1/2: no encontrado STATUS BAR — buscando variante...")
    # Intentar variante con espacios distintos
    import re
    patron = r"background:'linear-gradient\(180deg, rgba\(255,255,255,0\.04\)[^']*'[^}]*backdropFilter[^,}]*"
    match = re.search(patron, contenido)
    if match:
        print(f"  Encontrado en posicion {match.start()}: {match.group()[:80]}...")
    else:
        print("  No encontrado con ninguna variante")

# ── 2. Leyenda global (bandeja con fondo que aparece en todas las pestañas) ──
viejo_2 = "background:'rgba(255,255,255,0.03)', borderBottom:`1px solid ${NOAH_C.border}`, padding:'7px 16px', display:'flex', gap:14, alignItems:'center', flexWrap:'wrap'"
nuevo_2 = "background:'transparent', padding:'7px 16px', display:'flex', gap:14, alignItems:'center', flexWrap:'wrap'"

if viejo_2 in contenido:
    contenido = contenido.replace(viejo_2, nuevo_2, 1)
    cambios += 1
    print("OK 2/2: Leyenda sin fondo gris")
else:
    print("AVISO 2/2: no encontrado Leyenda")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios}")
