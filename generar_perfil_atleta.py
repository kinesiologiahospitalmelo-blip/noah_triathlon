"""
generar_perfil_atleta.py
------------------------------
Calcula el Perfil completo del atleta y lo guarda en la base. Cada uno
de los 18 analisis corre AISLADO -- si uno falla, no tira abajo a los
demas, y queda guardado el error especifico de ESE analisis puntual
(no se pierde todo el trabajo por uno solo que falle).

'predicciones_ml' ya NO depende de un modelo .pkl entrenado por atleta
(ver noah_perfil._predicciones_ml) -- es una proyeccion Banister +
reglas explicables, pura aritmetica. Por eso ya no hace falta correrlo
en un subproceso aislado: el conflicto de hilos que obligaba a eso era
especifico de joblib/sklearn cargando un pickle, y ese camino ya no
existe.

USO (en la raiz del repo, con DATABASE_URL seteada):
    python generar_perfil_atleta.py --atleta 4      # un solo atleta
    python generar_perfil_atleta.py --todos          # todos los atletas
                                                       # (para correr por cron)
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Falta psycopg2. Instalar con: pip install psycopg2-binary --break-system-packages")
    sys.exit(1)


PASOS = [
    ('patron_semanal', 'noah_perfil', '_patron_semanal'),
    ('distribucion_zonas', 'noah_perfil', '_distribucion_zonas'),
    ('mejores_marcas', 'noah_perfil', '_mejores_marcas'),
    ('punto_quiebre_tsb', 'noah_perfil', '_punto_quiebre_tsb'),
    ('consistencia', 'noah_perfil', '_consistencia'),
    ('predicciones_ml', 'noah_perfil', '_predicciones_ml'),
    ('acwr', 'noah_perfil', '_acwr'),
    ('progreso_tecnico', 'noah_perfil', '_progreso_tecnico'),
    ('marca_con_contexto', 'noah_perfil', '_marcas_con_contexto'),
    ('rachas_fatiga', 'noah_perfil', '_rachas_fatiga'),
    ('volumen_historico', 'noah_perfil', '_volumen_historico'),
    ('sesiones_anomalas', 'noah_perfil', '_sesiones_anomalas'),
    ('umbral_tss_tecnica', 'noah_perfil', '_umbral_tss_tecnica'),
    ('dias_recuperacion', 'noah_perfil', '_dias_recuperacion'),
    ('disciplina_mas_desgaste', 'noah_perfil', '_disciplina_mas_desgaste'),
    ('fase_actual', 'noah_perfil', '_fase_actual'),
    ('rendimiento_por_dia', 'noah_perfil', '_rendimiento_por_dia_controlado'),
    ('firma_recuperacion', 'noah_perfil', '_firma_recuperacion'),
    ('analisis_random_forest', 'noah_perfil', '_analisis_random_forest_rendimiento'),
]


def _conectar(db_url):
    from db_compat import ConexionCompat
    return ConexionCompat(psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor))


def calcular_perfil_atleta(db_url, atleta_id, np_mod):
    """Calcula y guarda el perfil de UN atleta. Devuelve (ok, fallidos)."""
    conn = _conectar(db_url)
    print(f"Calculando perfil del atleta {atleta_id}...")
    sys.stdout.flush()

    perfil = {}
    fallidos = []

    for nombre, _mod, fn_name in PASOS:
        print(f"  -> {nombre}...", end=' ')
        sys.stdout.flush()
        try:
            try:
                conn.close()
            except Exception:
                pass
            conn = _conectar(db_url)

            funcion = getattr(np_mod, fn_name)
            perfil[nombre] = funcion(conn, atleta_id)
            print("OK")
        except Exception as e:
            perfil[nombre] = {'disponible': False, 'motivo': f'error interno: {e}'}
            fallidos.append(nombre)
            print(f"FALLO -- {type(e).__name__}: {e}")
            # Seguimos con el resto -- este error no tira abajo a los demas.
        sys.stdout.flush()

    print()
    if fallidos:
        print(f"[AVISO] {len(fallidos)} analisis fallaron y quedaron marcados como no disponibles: {', '.join(fallidos)}")
    else:
        print(f"[OK] Los {len(PASOS)} analisis se calcularon sin errores.")

    perfil_json = json.dumps(perfil, ensure_ascii=False, default=str)
    conn.execute("""
        INSERT INTO perfil_atleta (atleta_id, perfil_json, actualizado)
        VALUES (%s,%s,%s)
        ON CONFLICT (atleta_id) DO UPDATE SET
            perfil_json=EXCLUDED.perfil_json,
            actualizado=EXCLUDED.actualizado
    """, (atleta_id, perfil_json, datetime.utcnow().isoformat()))
    conn.commit()

    print(f"[OK] Perfil guardado en la base para el atleta {atleta_id} "
          f"({len(PASOS)-len(fallidos)}/{len(PASOS)} análisis completos).")
    conn.close()
    return (len(fallidos) == 0, fallidos)


def main():
    ap = argparse.ArgumentParser()
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--atleta', type=int, help='Recalcula un solo atleta por id.')
    grupo.add_argument('--todos', action='store_true', help='Recalcula TODOS los atletas (uso: cron nocturno).')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL.")
        sys.exit(1)

    import noah_perfil as np_mod

    if args.atleta:
        calcular_perfil_atleta(db_url, args.atleta, np_mod)
        return

    # --todos: recorre todos los atletas activos de la base.
    conn = _conectar(db_url)
    ids = [r[0] for r in conn.execute("SELECT id FROM atletas ORDER BY id").fetchall()]
    conn.close()

    print(f"Recalculando perfil de {len(ids)} atletas...\n")
    resumen_ok, resumen_fallo = [], []
    for aid in ids:
        ok, fallidos = calcular_perfil_atleta(db_url, aid, np_mod)
        (resumen_ok if ok else resumen_fallo).append(aid)
        print('-' * 60)

    print(f"\n[RESUMEN] {len(resumen_ok)}/{len(ids)} atletas sin ningún análisis fallido.")
    if resumen_fallo:
        print(f"[RESUMEN] Atletas con al menos un análisis parcial: {resumen_fallo}")


if __name__ == '__main__':
    main()
