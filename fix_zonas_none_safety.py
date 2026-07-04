path = r"C:\Users\Win10\Desktop\noah_cloud\noa_deportes.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. ZonasRunning — lthr puede llegar None ────────────────────────────────
viejo_1 = """    def __init__(self, lthr: float, hr_max: float, pace_z2_real: float = None, peso_kg: float = 75):
        self.lthr        = lthr
        self.hr_max      = hr_max
        self.pace_z2     = pace_z2_real or self._estimar_pace_z2()
        self.peso_kg     = peso_kg"""

nuevo_1 = """    def __init__(self, lthr: float, hr_max: float, pace_z2_real: float = None, peso_kg: float = 75):
        # Si no hay LTHR real cargado para el atleta, estimar desde hr_max
        # (85% de HRmax es una aproximacion estandar de umbral) en vez de
        # dejar pasar None, que rompe todos los calculos de zona mas abajo.
        self.lthr        = lthr or (hr_max * 0.85 if hr_max else 160)
        self.hr_max      = hr_max
        self.pace_z2     = pace_z2_real or self._estimar_pace_z2()
        self.peso_kg     = peso_kg"""

if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1); cambios += 1
    print("OK 1/3: ZonasRunning blindado contra lthr=None")
else:
    print("AVISO 1/3: no encontrado ZonasRunning init")

# ── 2. ZonasCycling — ftp puede llegar None ─────────────────────────────────
viejo_2 = """    def __init__(self, ftp: float, lthr_bike: float = None, hr_max: float = 185,
                 peso_kg: float = 75, w_prime: float = W_PRIME_DEFAULT):
        self.ftp        = ftp
        self.lthr_bike  = lthr_bike or (hr_max * 0.85)
        self.hr_max     = hr_max
        self.peso_kg    = peso_kg
        self.w_prime    = w_prime
        self.w_kg       = round(ftp / peso_kg, 2) if peso_kg else None"""

nuevo_2 = """    def __init__(self, ftp: float, lthr_bike: float = None, hr_max: float = 185,
                 peso_kg: float = 75, w_prime: float = W_PRIME_DEFAULT):
        # Si no hay FTP real cargado, estimar conservador desde LTHR/peso
        # (mismo criterio que desde_lthr() mas abajo) en vez de dejar None.
        lthr_bike_efectivo = lthr_bike or (hr_max * 0.85 if hr_max else 150)
        self.ftp        = ftp or round((lthr_bike_efectivo / (hr_max or 185)) * (peso_kg or 75) * 2.8)
        self.lthr_bike  = lthr_bike_efectivo
        self.hr_max     = hr_max
        self.peso_kg    = peso_kg
        self.w_prime    = w_prime
        self.w_kg       = round(self.ftp / peso_kg, 2) if peso_kg else None"""

if viejo_2 in contenido:
    contenido = contenido.replace(viejo_2, nuevo_2, 1); cambios += 1
    print("OK 2/3: ZonasCycling blindado contra ftp=None")
else:
    print("AVISO 2/3: no encontrado ZonasCycling init")

# ── 3. ZonasSwimming — css puede llegar None (el bug original reportado) ───
viejo_3 = """        self.css      = css_100m   # pace cada 100m en formato decimal (ej: 1.75 = 1:45/100m)
        self.lthr     = lthr_swim or (hr_max * 0.82)
        self.hr_max   = hr_max"""

nuevo_3 = """        # Si el atleta no tiene CSS cargado (ej: no es nadador / sin test de
        # natacion), usar un valor de referencia generico en vez de None,
        # que rompia la division en calcular() con TypeError.
        self.css      = css_100m or 1.75   # 1:45/100m como referencia generica
        self.lthr     = lthr_swim or (hr_max * 0.82 if hr_max else 150)
        self.hr_max   = hr_max"""

if viejo_3 in contenido:
    contenido = contenido.replace(viejo_3, nuevo_3, 1); cambios += 1
    print("OK 3/3: ZonasSwimming blindado contra css=None (bug original)")
else:
    print("AVISO 3/3: no encontrado ZonasSwimming init")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 3)")
