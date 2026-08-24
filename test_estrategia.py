"""
test_estrategia.py — Genera estrategia de carrera desde datos reales de la DB
================================================================================
Correr:  cd C:\\Users\\Win10\\Desktop\\noah_cloud
         python test_estrategia.py --atleta_id 4 --carrera 70.3
         python test_estrategia.py --atleta_id 3 --carrera 10K
         python test_estrategia.py --atleta_id 1 --carrera olimpico
         python test_estrategia.py --atleta_id 3 --carrera 21K --temp 30

Lee umbrales REALES del atleta y calcula RANGOS (no numeros fijos).
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import psycopg2, psycopg2.extras
except ImportError:
    print("pip install psycopg2-binary"); sys.exit(1)

from noah_estrategia_carrera import generar_estrategia, calcular_bmr, CARRERAS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atleta_id', type=int, required=True)
    ap.add_argument('--carrera', required=True, help='5K, 10K, 21K, maraton, sprint, olimpico, 70.3, ironman, mtb, crono')
    ap.add_argument('--temp', type=float, default=20)
    ap.add_argument('--humedad', type=float, default=50)
    ap.add_argument('--altitud', type=float, default=0)
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: Falta DATABASE_URL"); sys.exit(1)

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT nombre, peso_kg, altura_cm, edad, sexo, deporte_ppal,
               pace_umbral_run, ftp_watts, css_100m,
               lthr_run, lthr_bike, lthr_swim
        FROM atletas WHERE id=%s
    """, (args.atleta_id,))
    row = cur.fetchone()
    if not row:
        print(f"Atleta {args.atleta_id} no encontrado"); sys.exit(1)

    atleta = {k: row[k] for k in row.keys()}
    nombre = atleta['nombre']
    deporte = atleta['deporte_ppal'] or 'running'

    print(f"\n{'='*70}")
    print(f"  ESTRATEGIA DE CARRERA")
    print(f"  Atleta: {nombre} ({deporte})")
    print(f"  Carrera: {args.carrera.upper()} ({CARRERAS.get(args.carrera,{}).get('dist_km','?')}km)")
    print(f"  Temp: {args.temp}°C | Humedad: {args.humedad}%")
    print(f"{'='*70}")

    # Mostrar umbrales actuales
    pace_u = float(atleta['pace_umbral_run']) if atleta['pace_umbral_run'] else None
    ftp = int(atleta['ftp_watts']) if atleta['ftp_watts'] else None
    css = float(atleta['css_100m']) if atleta['css_100m'] else None

    print(f"\n  UMBRALES ACTUALES (de la DB):")
    if pace_u:
        print(f"    Pace umbral run: {int(pace_u)}:{int((pace_u%1)*60):02d}/km")
    else:
        print(f"    Pace umbral run: NO TIENE — no puede calcular run")
    if ftp:
        print(f"    FTP bike: {ftp}W")
    else:
        print(f"    FTP bike: NO TIENE")
    if css:
        print(f"    CSS swim: {int(css)}:{int((css%1)*60):02d}/100m")

    # Generar estrategia
    cond = {'temperatura': args.temp, 'humedad': args.humedad, 'altitud': args.altitud}
    est = generar_estrategia(atleta, args.carrera, cond)

    if 'error' in est:
        print(f"\n  ERROR: {est['error']}")
        conn.close()
        return

    print(f"\n  TIEMPO ESTIMADO: {est['tiempo_estimado']['total_hms']}")
    print(f"  BMR: {est['bmr']} kcal/dia")

    # Segmentos con RANGOS
    print(f"\n  {'='*66}")
    print(f"  PLAN DE CARRERA POR SEGMENTO")
    print(f"  {'='*66}")

    for s in est['segmentos']:
        d = s['deporte'][:4]
        if d == 'tran':
            print(f"\n  🔄 {s['nombre']} ({s['tiempo_min']}min)")
            continue

        # Calcular RANGOS (±3% del valor calculado)
        if d == 'runn':
            p = s['pace_decimal']
            p_min = f"{int(p*0.97)}:{int((p*0.97%1)*60):02d}"
            p_max = f"{int(p*1.03)}:{int((p*1.03%1)*60):02d}"
            print(f"\n  🏃 Run km {s['km_inicio']}-{s['km_fin']}:")
            print(f"     Pace: {p_min} — {p_max} /km (Z{s['zona']})")
            print(f"     Glucogeno: {s['glucogeno_pct']}% | CHO quema {s['cho_quemado_g']}g | Ingerir {s['ingesta_cho_g']}g")
            print(f"     Hidratacion: {s['hidratacion_ml']}ml")

        elif d == 'cycl':
            w = s['potencia_w']
            w_min, w_max = round(w * 0.95), round(w * 1.05)
            v = s['vel_kmh']
            print(f"\n  🚴 Bike km {s['km_inicio']}-{s['km_fin']}:")
            print(f"     Potencia: {w_min}-{w_max}W (IF {s['if']}) | {v} km/h | {s['cadencia_rpm']} rpm")
            print(f"     Glucogeno: {s['glucogeno_pct']}% | CHO quema {s['cho_quemado_g']}g | Ingerir {s['ingesta_cho_g']}g")
            print(f"     Hidratacion: {s['hidratacion_ml']}ml")

        elif d == 'swim':
            p = s['pace_decimal']
            p_min = f"{int(p*0.97)}:{int((p*0.97%1)*60):02d}"
            p_max = f"{int(p*1.03)}:{int((p*1.03%1)*60):02d}"
            print(f"\n  🏊 Swim {s['distancia_m']}m:")
            print(f"     Pace: {p_min} — {p_max} /100m (Z{s['zona']})")

    # Nutricion
    n = est['nutricion']
    print(f"\n  {'='*66}")
    print(f"  PLAN DE NUTRICION")
    print(f"  {'='*66}")
    print(f"  {n['tipo']}")
    print(f"  Total CHO a ingerir: {n['cho_total_g']}g")
    if n['primer_gel_min']:
        print(f"  Primer gel: minuto {n['primer_gel_min']}")
        print(f"  Frecuencia: cada {n['freq_gel_min']} minutos")
    print(f"  Pre-carrera: {n['pre_carrera']}")

    # Hidratacion
    h = est['hidratacion']
    print(f"\n  {'='*66}")
    print(f"  PLAN DE HIDRATACION (temp {args.temp}°C)")
    print(f"  {'='*66}")
    print(f"  {h['tipo']}")
    print(f"  Sudoracion estimada: {h['sudor_estimado_ml_hr']} ml/hr")
    print(f"  Ingesta recomendada: {h['ml_hr']} ml/hr (cap 800ml/hr, Noakes 2012)")
    print(f"  Total: {h['ml_total']} ml")

    # Energia
    e = est['energia']
    print(f"\n  {'='*66}")
    print(f"  BALANCE ENERGETICO")
    print(f"  {'='*66}")
    print(f"  Gasto total: {e['kcal_total']} kcal")
    print(f"  CHO quemado total: {e['cho_quemado_g']}g")
    print(f"  Glucogeno disponible: {e['glucogeno_inicio_g']}g")
    if e['deficit_g'] > 0:
        print(f"  ⚠️ DEFICIT sin ingesta: {e['deficit_g']}g → BONKING seguro")
        print(f"  → Necesita ingerir minimo {e['deficit_g']}g de CHO durante la carrera")
    else:
        print(f"  ✓ Glucogeno suficiente sin ingesta externa")

    conn.close()

if __name__ == '__main__':
    main()
