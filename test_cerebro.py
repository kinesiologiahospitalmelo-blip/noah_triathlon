"""
test_cerebro.py — Testea el cerebro de NOAH sin generar ciclo
===============================================================
Correr:  cd C:\\Users\\Win10\\Desktop\\noah_cloud
         python test_cerebro.py --atleta_id 4

Solo MUESTRA lo que NOAH decidiria. No genera prescripcion, no toca datos.
"""
import os, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import psycopg2, psycopg2.extras
except ImportError:
    print("pip install psycopg2-binary"); sys.exit(1)

from noah_cerebro import decidir_semana, SISTEMAS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atleta_id', type=int, required=True)
    ap.add_argument('--fase', default='A', help='A, T, R, Taper')
    ap.add_argument('--carrera', default='', help='10K, 21K, olimpico, 70.3, ironman, mtb...')
    ap.add_argument('--tss', type=int, default=0, help='TSS objetivo (0=auto)')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: Falta DATABASE_URL"); sys.exit(1)

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
    cur = conn.cursor()

    # Info del atleta
    cur.execute("SELECT nombre, deporte_ppal, ftp_watts, pace_umbral_run FROM atletas WHERE id=%s", (args.atleta_id,))
    at = cur.fetchone()
    if not at:
        print(f"Atleta {args.atleta_id} no encontrado"); sys.exit(1)

    nombre = at[0]
    deporte = at[1] or 'running'
    carrera_tipo = args.carrera or ''

    # TSS auto desde CTL
    tss = args.tss
    if tss == 0:
        cur.execute("SELECT ctl FROM sesiones WHERE atleta_id=%s AND ctl IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                    (args.atleta_id,))
        r = cur.fetchone()
        ctl = float(r[0]) if r and r[0] else 40
        tss = round(ctl * 7 * 1.05)

    print(f'\n{"="*60}')
    print(f'  TEST CEREBRO NOAH — {nombre} (id={args.atleta_id})')
    print(f'  Deporte: {deporte} | Fase: {args.fase} | Carrera: {carrera_tipo or "sin carrera"}')
    print(f'  TSS objetivo: {tss}')
    print(f'{"="*60}')

    # Correr cerebro (solo lectura)
    resultado = decidir_semana(conn, args.atleta_id, args.fase, carrera_tipo, tss)

    # Resumen
    ev = resultado['evaluacion']
    fo = resultado['foco']
    do = resultado['dosificacion']

    print(f'\n  {"="*50}')
    print(f'  RESUMEN DE DECISION')
    print(f'  {"="*50}')
    print(f'  CTL: {ev["ctl"]:.1f}' if ev['ctl'] else '  CTL: --')
    print(f'  TSB: {ev["tsb"]:+.1f}' if ev['tsb'] else '  TSB: --')
    print(f'  Readiness: {ev["readiness"]}')

    print(f'\n  SISTEMAS FISIOLOGICOS:')
    for s in SISTEMAS:
        v = ev['sistemas'][s]
        bar = '█' * int(v/5) + '░' * (20 - int(v/5))
        lim = ' ← LIMITANTE' if s == fo['limitante'] else ''
        print(f'    {s:<22s} {bar} {v:.0f}{lim}')

    print(f'\n  FOCO: {fo["foco"]}')
    print(f'  SESIONES CALIDAD: {fo["n_calidad"]}')
    print(f'  DOSIFICACION: {do["desc"]}')
    if do['reps'] > 1:
        print(f'    {do["reps"]}x{do["dur_min"]}\' en {do["zona"]} / rec {do["pausa_min"]}\' {"activa" if do["activa"] else "pasiva"}')
    print(f'  TSS AJUSTADO: {fo["tss_ajustado"]}')

    if ev.get('pct_z12') is not None:
        print(f'\n  DISTRIBUCION ACTUAL: Z1-Z2={ev["pct_z12"]}% Z3-Z4={ev["pct_z34"]}% Z5-Z6={ev["pct_z56"]}%')

    ap_r = resultado.get('aprendizaje')
    if ap_r and ap_r.get('delta_ctl') is not None:
        print(f'\n  SEMANA PASADA: ΔCTL={ap_r["delta_ctl"]:+.2f} {"✓" if ap_r["mejoro"] else "✗"}')

    print(f'\n  [Solo lectura — no se genero prescripcion]')
    conn.close()

if __name__ == '__main__':
    main()
