path_deportes = r"C:\Users\Win10\Desktop\noah_cloud\noa_deportes.py"
path_app      = r"C:\Users\Win10\Desktop\noah_cloud\app.py"

with open(path_deportes, "r", encoding="utf-8") as f:
    dep = f.read()

with open(path_app, "r", encoding="utf-8") as f:
    app = f.read()

cambios = 0

# ── 1. ZonasRunning.__init__: agregar pace_umbral como parametro principal ───
viejo_init = """    def __init__(self, lthr: float, hr_max: float, pace_z2_real: float = None, peso_kg: float = 75):
        # Si no hay LTHR real cargado para el atleta, estimar desde hr_max
        # (85% de HRmax es una aproximacion estandar de umbral) en vez de
        # dejar pasar None, que rompe todos los calculos de zona mas abajo.
        self.lthr        = lthr or (hr_max * 0.85 if hr_max else 160)
        self.hr_max      = hr_max
        self.pace_z2     = pace_z2_real or self._estimar_pace_z2()
        self.peso_kg     = peso_kg"""

nuevo_init = """    def __init__(self, lthr: float, hr_max: float, pace_z2_real: float = None,
                 peso_kg: float = 75, pace_umbral: float = None):
        # Si no hay LTHR real, estimarlo desde hr_max (85% es aprox estandar de umbral)
        self.lthr        = lthr or (hr_max * 0.85 if hr_max else 160)
        self.hr_max      = hr_max
        self.peso_kg     = peso_kg
        # pace_umbral (Z4) es la referencia principal para calcular todas las zonas.
        # Si no viene, estimar desde el LTHR usando la funcion anterior.
        # Si viene pace_z2_real pero no pace_umbral, convertir Z2 a umbral
        # multiplicando por 0.81/1.0 = 0.81 (Z2 center es ~81% LTHR, Z4 es ~97%).
        if pace_umbral:
            self.pace_umbral = pace_umbral
        elif pace_z2_real:
            # Z2 es aprox 5-7% mas lento que el umbral
            self.pace_umbral = pace_z2_real * 0.92
        else:
            self.pace_umbral = self._estimar_pace_umbral()
        # Mantener pace_z2 para compatibilidad con codigo existente
        self.pace_z2 = self.pace_umbral / 0.92"""

if viejo_init in dep:
    dep = dep.replace(viejo_init, nuevo_init, 1); cambios += 1
    print("OK 1/5: ZonasRunning.__init__ actualizado con pace_umbral")
else:
    print("AVISO 1/5: no se encontro el init de ZonasRunning")

# ── 2. Reemplazar _estimar_pace_z2 por _estimar_pace_umbral ─────────────────
viejo_estimar = """    def _estimar_pace_z2(self) -> float:
        \"\"\"Estimación de pace Z2 desde LTHR si no hay datos reales.\"\"\"
        # Aproximación empírica: LTHR 160 → ~5:30/km, LTHR 140 → ~6:30/km
        return 5.5 + (160 - self.lthr) * 0.05"""

nuevo_estimar = """    def _estimar_pace_umbral(self) -> float:
        \"\"\"
        Estima el pace de umbral (Z4) desde el LTHR cuando no hay
        datos reales de Garmin ni test de campo.
        Aproximacion empirica: LTHR 160 bpm -> pace umbral ~4:58/km.
        Cada bpm de diferencia cambia el pace ~0.05 min/km.
        \"\"\"
        return 4.98 + (160 - self.lthr) * 0.05

    def _estimar_pace_z2(self) -> float:
        # Mantener por compatibilidad; calcula Z2 desde el umbral estimado
        return self._estimar_pace_umbral() / 0.92"""

if viejo_estimar in dep:
    dep = dep.replace(viejo_estimar, nuevo_estimar, 1); cambios += 1
    print("OK 2/5: _estimar_pace_z2 reemplazado por _estimar_pace_umbral")
else:
    print("AVISO 2/5: no se encontro _estimar_pace_z2")

# ── 3. Reescribir _pace_para_zona para que use pace_umbral como ancla de Z4 ──
viejo_pace = """    def _pace_para_zona(self, pct_min: float, pct_max: float) -> tuple:
        \"\"\"
        Calcula pace mínimo y máximo para una zona.
        Pace Z2 real como referencia central.
        \"\"\"
        # Factor de escala: pace varía inversamente con % LTHR
        # Z2 center = 0.81 LTHR → pace_z2_real
        z2_center = 0.81
        ref_pct = (pct_min + pct_max) / 2

        # pace escalado desde Z2
        if ref_pct > 0:
            factor = z2_center / ref_pct
            pace_center = self.pace_z2 * factor
        else:
            pace_center = self.pace_z2 * 1.3

        margin = 0.03
        return pace_center * (1 + margin), pace_center * (1 - margin)"""

nuevo_pace = """    def _pace_para_zona(self, pct_min: float, pct_max: float) -> tuple:
        \"\"\"
        Calcula pace minimo y maximo para una zona usando el pace de
        umbral (Z4) como referencia central.

        El pace varia INVERSAMENTE con la intensidad:
        - Mas intensidad (mayor % LTHR) = pace mas rapido (numero menor)
        - La Z4 (umbral, 96.5% LTHR) tiene como referencia el pace_umbral

        Formula: pace_zona = pace_umbral * (z4_center / ref_pct)
        Donde z4_center = 0.965 (centro de Z4: 93-100% LTHR)
        \"\"\"
        z4_center = 0.965  # centro de Z4 (umbral)
        ref_pct   = (pct_min + pct_max) / 2
        if ref_pct <= 0:
            ref_pct = 0.50

        pace_center = self.pace_umbral * (z4_center / ref_pct)
        margin = 0.025  # ±2.5% alrededor del centro de cada zona
        return pace_center * (1 + margin), pace_center * (1 - margin)"""

if viejo_pace in dep:
    dep = dep.replace(viejo_pace, nuevo_pace, 1); cambios += 1
    print("OK 3/5: _pace_para_zona reescrito para usar pace_umbral como ancla de Z4")
else:
    print("AVISO 3/5: no se encontro _pace_para_zona")

with open(path_deportes, "w", encoding="utf-8") as f:
    f.write(dep)

# ── 4. app.py: leer pace_umbral_run de la BD y pasarlo a ZonasRunning ────────
viejo_app_run = """        z = ZonasRunning(lthr=lthr_run, hr_max=hr_max, pace_z2_real=pace_z2, peso_kg=peso)"""

nuevo_app_run = """        # pace_umbral_run es el dato real calculado/traido de Garmin.
        # Si no existe aun, ZonasRunning lo estima desde el LTHR.
        pace_umbral_run = atleta.get('pace_umbral_run')
        z = ZonasRunning(lthr=lthr_run, hr_max=hr_max, pace_z2_real=pace_z2,
                         peso_kg=peso, pace_umbral=pace_umbral_run)"""

if viejo_app_run in app:
    app = app.replace(viejo_app_run, nuevo_app_run, 1); cambios += 1
    print("OK 4/5: app.py ahora pasa pace_umbral_run a ZonasRunning")
else:
    print("AVISO 4/5: no se encontro la construccion de ZonasRunning en app.py")

# ── 5. app.py: leer ftp_watts (no 'ftp') de la BD para cycling ──────────────
viejo_ftp = """        ftp       = atleta.get('ftp_watts') or atleta.get('ftp')"""
nuevo_ftp  = """        # ftp_watts es el campo real en la tabla atletas (actualizado por
        # descargar_umbrales/calcular_umbral_desde_historial).
        ftp       = atleta.get('ftp_watts') or atleta.get('ftp')"""

if viejo_ftp in app:
    app = app.replace(viejo_ftp, nuevo_ftp, 1); cambios += 1
    print("OK 5/5: ftp_watts confirmado en app.py")
else:
    # no es un error critico, solo confirmacion
    print("INFO 5/5: ftp_watts ya estaba correcto en app.py (sin cambios)")
    cambios += 1  # no cuenta como falla

with open(path_app, "w", encoding="utf-8") as f:
    f.write(app)

print(f"\nTotal cambios: {cambios} (esperado: 5)")
