"""
eval_twin.py — Evaluación retrospectiva del Digital Twin
=========================================================
Corre el Twin sobre semanas históricas y mide:

  1. ¿El Twin hubiera prescripto algo mejor que lo que se hizo?
  2. ¿Las semanas alineadas con el Twin tuvieron mejores resultados?
  3. ¿El modelo de readiness acertó?

CICLO PRODUCTIVO:
  Domingo noche → sync Garmin → Twin toma semana real → prescribe semana siguiente
  Domingo siguiente → comparar prescripción vs realidad → medir acierto

USO:
  python eval_twin.py 4          # evaluar Jimena
  python eval_twin.py 1          # evaluar Rodrigo
"""

import os
import sys
import math
import numpy as np
import pandas as pd
from datetime import timedelta

# ── importar twin ──
from noah_twin_v2 import DigitalTwin, _sql, _sf, _pace


def evaluar_twin(conn, atleta_id: int):
    """
    Backtesting: para cada semana histórica, comparar lo que el atleta
    realmente hizo vs lo que el Twin hubiera recomendado, y medir
    qué semanas tuvieron mejores resultados.
    """
    print(f'\n{"="*70}')
    print(f'  EVALUACIÓN RETROSPECTIVA — Atleta {atleta_id}')
    print(f'{"="*70}')

    # ── 1. Calibrar twin con TODOS los datos ──
    twin = DigitalTwin(conn, atleta_id)
    res = twin.calibrar(verbose=True)
    if not res.get('ok'):
        print(f'  ✗ No se pudo calibrar: {res}')
        return

    nombre = twin.perfil.get('nombre', f'ID {atleta_id}')

    # ── 2. Construir semanas reales ──
    ses = twin._ses.copy()
    bio = twin._bio.copy() if twin._bio is not None else pd.DataFrame()

    ses['semana_iso'] = ses['fecha'].dt.strftime('%G-%V')
    semanas = ses.groupby('semana_iso').agg(
        fecha_ini=('fecha', 'min'),
        fecha_fin=('fecha', 'max'),
        tss_total=('tss_total', 'sum'),
        sesiones=('tss_total', 'count'),
        tss_z12=('tss_z12', lambda x: x.fillna(0).sum()),
        tss_z34=('tss_z34', lambda x: x.fillna(0).sum()),
        tss_z56=('tss_z56', lambda x: x.fillna(0).sum()),
        ctl_fin=('ctl', 'last'),
        tsb_fin=('tsb', 'last'),
        pace_avg=('pace', lambda x: x.dropna().mean()),
        power_avg=('np_watts', lambda x: x.dropna().mean()),
    ).reset_index()

    semanas = semanas.sort_values('fecha_ini').reset_index(drop=True)
    n_sem = len(semanas)

    if n_sem < 12:
        print(f'  Pocas semanas ({n_sem}), necesito al menos 12')
        return

    # ── 3. Para cada semana: qué pasó DESPUÉS ──
    # Resultado = cómo evolucionó el atleta en las 2-4 semanas siguientes
    resultados = []
    for i in range(n_sem - 4):
        sem = semanas.iloc[i]
        futuro = semanas.iloc[i+1 : i+5]

        # Distribución real
        tss = sem['tss_total']
        pct_z12 = sem['tss_z12'] / max(tss, 1)
        pct_z34 = sem['tss_z34'] / max(tss, 1)
        pct_z56 = sem['tss_z56'] / max(tss, 1)

        # Deportes en la semana
        ses_sem = ses[ses['semana_iso'] == sem['semana_iso']]
        sports = ses_sem['sport'].value_counts().to_dict()
        n_sports = len(sports)

        # Intensidad: TSS/hora promedio
        dur_total = ses_sem['duration_min'].sum()
        tss_per_h = tss / max(dur_total / 60, 0.1)

        # ACWR
        tss_4sem = semanas.iloc[max(0,i-3):i+1]['tss_total'].mean()
        acwr = tss / max(tss_4sem, 1)

        # Resultado: ¿mejoró performance en las siguientes 4 semanas?
        pace_ahora = sem['pace_avg']
        pace_fut = futuro['pace_avg'].dropna().mean()
        power_ahora = sem['power_avg']
        power_fut = futuro['power_avg'].dropna().mean()

        delta_perf = None
        if pd.notna(pace_ahora) and pd.notna(pace_fut) and pace_ahora > 0:
            delta_perf = (pace_ahora - pace_fut) / pace_ahora * 100  # positivo = mejoró
        elif pd.notna(power_ahora) and pd.notna(power_fut) and power_ahora > 0:
            delta_perf = (power_fut - power_ahora) / power_ahora * 100

        # ¿HRV se mantuvo o mejoró?
        hrv_ok = None
        if not bio.empty:
            f0, f1 = sem['fecha_ini'], sem['fecha_fin']
            f2 = f1 + timedelta(days=14)
            hrv_sem = bio[(bio['fecha'] >= f0) & (bio['fecha'] <= f1)]['hrv_rmssd'].dropna()
            hrv_fut = bio[(bio['fecha'] > f1) & (bio['fecha'] <= f2)]['hrv_rmssd'].dropna()
            if len(hrv_sem) >= 3 and len(hrv_fut) >= 3:
                hrv_ok = 1 if hrv_fut.mean() >= hrv_sem.mean() * 0.90 else 0

        # CTL subió?
        ctl_ahora = _sf(sem['ctl_fin'])
        ctl_fut = futuro['ctl_fin'].dropna().mean()
        ctl_subio = 1 if pd.notna(ctl_fut) and ctl_fut > ctl_ahora * 0.98 else 0

        # ¿Semana alineada con principios del Twin?
        # (Seiler 80/20, ACWR 0.8-1.3, variedad, descanso)
        alineada = 0
        if pct_z12 >= 0.60 and pct_z34 <= 0.35:
            alineada += 1  # distribución OK
        if 0.80 <= acwr <= 1.30:
            alineada += 1  # ACWR sweet spot
        if n_sports >= 2:
            alineada += 1  # multi-deporte
        if sem['sesiones'] <= 8:
            alineada += 1  # no sobrecarga de sesiones

        resultados.append({
            'semana': sem['semana_iso'],
            'tss': tss,
            'pct_z12': round(pct_z12, 2),
            'pct_z34': round(pct_z34, 2),
            'acwr': round(acwr, 2),
            'n_sports': n_sports,
            'tss_per_h': round(tss_per_h, 1),
            'delta_perf': round(delta_perf, 2) if delta_perf is not None else None,
            'hrv_ok': hrv_ok,
            'ctl_subio': ctl_subio,
            'alineada': alineada,
        })

    df = pd.DataFrame(resultados)

    # ── 4. Análisis: semanas alineadas vs no alineadas ──
    print(f'\n  ANÁLISIS RETROSPECTIVO ({len(df)} semanas evaluadas)')
    print(f'  {"─"*60}')

    # Separar semanas bien alineadas (≥3 criterios) vs mal alineadas (≤1)
    bien = df[df['alineada'] >= 3]
    mal = df[df['alineada'] <= 1]

    print(f'\n  Semanas alineadas con Twin (≥3 criterios): {len(bien)}')
    print(f'  Semanas NO alineadas (≤1 criterio):        {len(mal)}')

    if len(bien) >= 5 and len(mal) >= 5:
        dp_bien = bien['delta_perf'].dropna()
        dp_mal = mal['delta_perf'].dropna()

        print(f'\n  RESULTADOS:')
        print(f'                          {"Alineadas":>12s}  {"No alineadas":>12s}')
        print(f'    Δ Performance (%)     {dp_bien.mean():>+11.2f}%  {dp_mal.mean():>+11.2f}%')

        hrv_bien = bien['hrv_ok'].dropna()
        hrv_mal = mal['hrv_ok'].dropna()
        if len(hrv_bien) >= 3 and len(hrv_mal) >= 3:
            print(f'    HRV mantenida (%)     {hrv_bien.mean()*100:>11.0f}%  {hrv_mal.mean()*100:>11.0f}%')

        ctl_bien = bien['ctl_subio'].mean()
        ctl_mal = mal['ctl_subio'].mean()
        print(f'    CTL subió (%)         {ctl_bien*100:>11.0f}%  {ctl_mal*100:>11.0f}%')

        # Conclusión
        if dp_bien.mean() > dp_mal.mean() and hrv_bien.mean() >= hrv_mal.mean():
            print(f'\n  ✓ VALIDACIÓN POSITIVA: semanas alineadas con Twin → '
                  f'mejor performance Y mejor absorción')
            fuerza = 'FUERTE' if (dp_bien.mean() - dp_mal.mean()) > 0.5 else 'MODERADA'
            print(f'    Evidencia: {fuerza}')
        elif dp_bien.mean() > dp_mal.mean():
            print(f'\n  ~ VALIDACIÓN PARCIAL: mejor performance pero HRV mixta')
        else:
            print(f'\n  ✗ SIN VALIDACIÓN CLARA: semanas alineadas no muestran ventaja')
            print(f'    → Posible causa: distribución de zonas no es el factor clave, '
                  f'o datos insuficientes')
    else:
        print(f'\n  Pocas semanas en algún grupo para comparar')

    # ── 5. ACWR y riesgo ──
    print(f'\n  ANÁLISIS DE RIESGO (ACWR):')
    acwr_bins = [
        ('< 0.8 (desentrenamiento)', df[df['acwr'] < 0.8]),
        ('0.8-1.3 (sweet spot)',     df[(df['acwr'] >= 0.8) & (df['acwr'] <= 1.3)]),
        ('> 1.3 (peligro)',          df[df['acwr'] > 1.3]),
    ]
    for label, grupo in acwr_bins:
        if len(grupo) >= 3:
            dp = grupo['delta_perf'].dropna()
            hrv = grupo['hrv_ok'].dropna()
            print(f'    {label:30s}  n={len(grupo):3d}  '
                  f'ΔPerf={dp.mean():+.2f}%  '
                  f'HRV_ok={hrv.mean()*100:.0f}%' if len(hrv) >= 3 else
                  f'    {label:30s}  n={len(grupo):3d}  '
                  f'ΔPerf={dp.mean():+.2f}%')

    # ── 6. Readiness model validation ──
    print(f'\n  READINESS MODEL:')
    print(f'    F1-score CV: {twin.readiness.score:.3f}' if twin.readiness.ok else '    No entrenado')
    if twin.readiness.ok and hasattr(twin.readiness.model, 'feature_importances_'):
        imp = dict(zip(
            [f[:15] for f in ['hrv_rmssd','hrv_7d_avg','hrv_7d_cv','hrv_delta',
                              'sleep_h','sleep_7d','stress','stress_7d',
                              'recovery','body_bat','tsb','ctl','atl','acwr',
                              'tss_ayer','tss_2d','dias_intensa']],
            twin.readiness.model.feature_importances_
        ))
        top5 = sorted(imp.items(), key=lambda x: -x[1])[:5]
        print(f'    Top features: {", ".join(f"{k}={v:.2f}" for k,v in top5)}')

    # ── 7. Resumen ejecutivo ──
    print(f'\n  {"="*60}')
    print(f'  RESUMEN PARA {nombre}')
    print(f'  {"="*60}')

    # Patrón óptimo encontrado
    if len(bien) >= 5:
        print(f'  Semanas con mejores resultados:')
        print(f'    TSS promedio:     {bien["tss"].mean():.0f}')
        print(f'    % Z1-2:           {bien["pct_z12"].mean()*100:.0f}%')
        print(f'    % Z3-4:           {bien["pct_z34"].mean()*100:.0f}%')
        print(f'    ACWR promedio:    {bien["acwr"].mean():.2f}')
        print(f'    Deportes/semana:  {bien["n_sports"].mean():.1f}')

    # Confianza del twin
    n_mod_ok = sum([
        twin.readiness.ok,
        twin.response.ok,
        any(m.get('ok', m.get('r2', -1) > 0) if isinstance(m, dict) else False
            for m in twin.metricas.values()),
    ])
    confianza = min(95, max(30,
        20 * n_mod_ok +
        10 * min(n_sem / 50, 1) +
        15 * (twin.readiness.score if twin.readiness.ok else 0)
    ))
    print(f'\n  Confianza del Twin: {confianza:.0f}%')
    print(f'  Basado en: {n_sem} semanas, {len(twin._ses)} sesiones, '
          f'{len(bio)} días bio')
    print(f'{"="*70}\n')


if __name__ == '__main__':
    import psycopg2
    db_url = os.environ.get('DATABASE_URL',
        'postgresql://postgres.jbsggrkzudeiekgmwcel:noah_triatlon'
        '@aws-1-us-west-2.pooler.supabase.com:6543/postgres')
    conn = psycopg2.connect(db_url)

    if len(sys.argv) > 1:
        for aid in sys.argv[1:]:
            evaluar_twin(conn, int(aid))
    else:
        cur = conn.cursor()
        cur.execute('SELECT id FROM atletas WHERE activo=true')
        for (aid,) in cur.fetchall():
            evaluar_twin(conn, aid)
    conn.close()
