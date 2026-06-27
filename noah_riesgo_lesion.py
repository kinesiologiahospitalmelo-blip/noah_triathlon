"""
noah_riesgo_lesion.py — Riesgo de Lesión NOAH
================================================
Dos indicadores INDEPENDIENTES, deliberadamente NO fusionados en un score
único — fusionarlos introduciría sesgo: un atleta puede tener HRV/sueño
excelentes (HANNA LIFE alto) y aun así estar en zona de riesgo mecánico
por escalada brusca de carga (ACWR alto), o viceversa. Combinarlos en un
solo número permitiría que se cancelen entre sí, ocultando el riesgo real.

Esto es DISTINTO de HANNA LIFE (que mide vitalidad autonómica: HRV, FC,
sueño, stress) — el riesgo de lesión musculoesquelética es principalmente
una función de CARGA MECÁNICA ACUMULADA, no del sistema nervioso autónomo.

FUENTES BIBLIOGRÁFICAS:
  [1] Gabbett TJ. "The training-injury prevention paradox: should athletes
      be training smarter and harder?" Br J Sports Med. 2016;50(5):273-280.
      → ACWR (Acute:Chronic Workload Ratio)
  [2] Hulin BT, et al. "Spikes in acute workload are associated with
      increased injury risk in elite cricket fast bowlers." Br J Sports
      Med. 2014;48(8):708-712.
      → Validación de zonas de riesgo ACWR
  [3] Foster C. "Monitoring training in athletes with reference to
      overtraining syndrome." Med Sci Sports Exerc. 1998;30(7):1164-1168.
      → Monotonía y Strain de entrenamiento
"""

from datetime import date, timedelta


# ─── 1. ACWR — Acute:Chronic Workload Ratio (Gabbett 2016) [1][2] ───────────

def calcular_acwr(conn, atleta_id: int, fecha: str = None) -> dict:
    """
    ACWR = carga aguda (promedio diario últimos 7 días) /
           carga crónica (promedio diario últimos 28 días)

    Zonas de riesgo documentadas (Gabbett 2016, Hulin 2014):
      < 0.8           : carga insuficiente — riesgo de "destrenamiento",
                        paradójicamente también asociado a mayor riesgo al
                        volver a cargar
      0.8 - 1.3       : zona óptima / "sweet spot" — menor riesgo relativo
      1.3 - 1.5       : zona de precaución
      > 1.5           : zona de alto riesgo — incremento documentado de
                        lesiones en múltiples deportes (cricket, fútbol,
                        rugby)

    Usa promedio diario (no suma) en cada ventana para no penalizar
    semanas con menos sesiones absolutas.
    """
    if fecha is None:
        fecha = str(date.today())
    fecha_dt = date.fromisoformat(fecha)

    fecha_7d  = str(fecha_dt - timedelta(days=7))
    fecha_28d = str(fecha_dt - timedelta(days=28))

    rows_agudo = conn.execute("""
        SELECT SUM(tss_total) FROM sesiones
        WHERE atleta_id=%s AND fecha > %s AND fecha <= %s
    """, (atleta_id, fecha_7d, fecha)).fetchone()
    suma_aguda = rows_agudo[0] or 0
    carga_aguda_diaria = suma_aguda / 7

    rows_cronico = conn.execute("""
        SELECT SUM(tss_total) FROM sesiones
        WHERE atleta_id=%s AND fecha > %s AND fecha <= %s
    """, (atleta_id, fecha_28d, fecha)).fetchone()
    suma_cronica = rows_cronico[0] or 0
    carga_cronica_diaria = suma_cronica / 28

    # Verificar que haya suficiente historial — Gabbett recomienda al menos
    # 3 semanas de datos crónicos antes de confiar en el ratio
    dias_con_datos = conn.execute("""
        SELECT COUNT(DISTINCT fecha) FROM sesiones
        WHERE atleta_id=%s AND fecha > %s AND fecha <= %s
    """, (atleta_id, fecha_28d, fecha)).fetchone()[0]

    if dias_con_datos < 10 or carga_cronica_diaria == 0:
        return {
            'disponible': False,
            'acwr': None,
            'mensaje': 'Historial insuficiente (<10 días con actividad en las últimas 4 semanas) '
                       'para calcular ACWR de forma confiable (Gabbett 2016 recomienda mínimo 3 semanas).',
            'fuente': 'Gabbett, Br J Sports Med, 2016',
        }

    acwr = round(carga_aguda_diaria / carga_cronica_diaria, 2)

    if acwr < 0.8:
        zona = 'baja_carga'
        nivel_riesgo = 'atencion'
        mensaje = (f'ACWR {acwr} — por debajo de 0.8. Carga aguda muy inferior a la crónica. '
                   'Riesgo de "destrenamiento" — paradójicamente asociado a mayor riesgo al '
                   'reanudar carga normal sin progresión gradual.')
    elif acwr <= 1.3:
        zona = 'optima'
        nivel_riesgo = 'bajo'
        mensaje = f'ACWR {acwr} — zona óptima (0.8-1.3). Progresión de carga adecuada.'
    elif acwr <= 1.5:
        zona = 'precaucion'
        nivel_riesgo = 'moderado'
        mensaje = f'ACWR {acwr} — zona de precaución (1.3-1.5). Vigilar progresión de carga.'
    else:
        zona = 'alto_riesgo'
        nivel_riesgo = 'alto'
        mensaje = (f'ACWR {acwr} — por encima de 1.5. Zona de riesgo elevado de lesión '
                   'documentada en la literatura (incremento de carga muy brusco respecto '
                   'al promedio de las últimas 4 semanas).')

    return {
        'disponible': True,
        'acwr': acwr,
        'carga_aguda_diaria': round(carga_aguda_diaria, 1),
        'carga_cronica_diaria': round(carga_cronica_diaria, 1),
        'zona': zona,
        'nivel_riesgo': nivel_riesgo,
        'mensaje': mensaje,
        'fuente': 'Gabbett, Br J Sports Med, 2016; Hulin et al., Br J Sports Med, 2014',
    }


# ─── 2. MONOTONÍA Y STRAIN (Foster 1998) [3] ────────────────────────────────

def calcular_monotonia_strain(conn, atleta_id: int, fecha: str = None) -> dict:
    """
    Monotonía = promedio TSS diario semana / desviación estándar TSS diario semana
    Strain = TSS total semanal × Monotonía

    Foster (1998): monotonía alta (entrenar con TSS muy similar día tras día,
    sin variación) se asocia a mayor riesgo de sobreentrenamiento, lesión y
    enfermedad — incluso con carga total moderada. La variación día a día
    (fácil/difícil) es protectora, no solo el volumen total.

    Umbrales documentados:
      Monotonía > 2.0  : riesgo elevado, independientemente del volumen total
      Strain muy alto junto con monotonía alta: combinación de mayor riesgo
    """
    if fecha is None:
        fecha = str(date.today())
    fecha_dt = date.fromisoformat(fecha)
    fecha_7d = str(fecha_dt - timedelta(days=6))  # 7 días incluyendo hoy

    rows = conn.execute("""
        SELECT fecha, SUM(tss_total) as tss_dia
        FROM sesiones
        WHERE atleta_id=%s AND fecha >= %s AND fecha <= %s
        GROUP BY fecha
    """, (atleta_id, fecha_7d, fecha)).fetchall()

    if len(rows) < 4:
        return {
            'disponible': False,
            'monotonia': None,
            'strain': None,
            'mensaje': 'Historial insuficiente (<4 días con actividad en la última semana) '
                       'para calcular monotonía de forma confiable.',
            'fuente': 'Foster, Med Sci Sports Exerc, 1998',
        }

    # Completar con 0 los días sin entrenar dentro de la ventana de 7 días —
    # el día de descanso ES parte de la variación que mide la monotonía
    tss_por_dia = {r[0]: r[1] for r in rows}
    valores = []
    d = fecha_dt - timedelta(days=6)
    while d <= fecha_dt:
        valores.append(tss_por_dia.get(str(d), 0))
        d += timedelta(days=1)

    n = len(valores)
    media = sum(valores) / n
    varianza = sum((v - media)**2 for v in valores) / n
    desv_std = varianza ** 0.5

    if desv_std == 0:
        # Todos los días con TSS idéntico — monotonía técnicamente infinita,
        # se reporta como riesgo máximo de la escala práctica
        monotonia = 999
    else:
        monotonia = round(media / desv_std, 2)

    tss_semanal_total = sum(valores)
    strain = round(tss_semanal_total * monotonia, 0) if monotonia < 999 else None

    if monotonia >= 2.0 or monotonia == 999:
        nivel_riesgo = 'alto'
        mensaje = (f'Monotonía {monotonia if monotonia<999 else ">2.0"} — por encima del umbral '
                   'de riesgo (Foster 1998). Poca variación día a día en la carga — aunque el '
                   'volumen total sea moderado, la falta de días claramente más fáciles/difíciles '
                   'se asocia a mayor riesgo de sobreentrenamiento y lesión.')
    elif monotonia >= 1.5:
        nivel_riesgo = 'moderado'
        mensaje = f'Monotonía {monotonia} — zona intermedia. Conviene aumentar la variación entre días fáciles y difíciles.'
    else:
        nivel_riesgo = 'bajo'
        mensaje = f'Monotonía {monotonia} — buena variación día a día entre cargas fáciles y difíciles.'

    return {
        'disponible': True,
        'monotonia': monotonia if monotonia < 999 else None,
        'monotonia_maxima': monotonia == 999,
        'strain': strain,
        'tss_semanal_total': round(tss_semanal_total, 1),
        'nivel_riesgo': nivel_riesgo,
        'mensaje': mensaje,
        'fuente': 'Foster, Med Sci Sports Exerc, 1998',
    }


# ─── 3. RESUMEN COMBINADO PARA UI (sin fusionar en un score) ───────────────

def resumen_riesgo_lesion(conn, atleta_id: int, fecha: str = None) -> dict:
    """
    Retorna ambos indicadores SEPARADOS, lado a lado, para mostrar en el
    dashboard sin fusionarlos. El coach los interpreta cruzados — igual
    que ya hace con CTL/ATL/TSB por separado.
    """
    acwr = calcular_acwr(conn, atleta_id, fecha)
    monotonia = calcular_monotonia_strain(conn, atleta_id, fecha)

    alertas = []
    if acwr.get('nivel_riesgo') == 'alto':
        alertas.append(f"ACWR alto ({acwr['acwr']}) — carga reciente muy por encima del promedio de 4 semanas.")
    if monotonia.get('nivel_riesgo') == 'alto':
        alertas.append(f"Monotonía alta — poca variación de carga día a día en la última semana.")

    return {
        'acwr': acwr,
        'monotonia_strain': monotonia,
        'alertas': alertas,
        'nota_metodologica': ('ACWR y Monotonía/Strain son indicadores INDEPENDIENTES de riesgo '
                              'mecánico de lesión — deliberadamente no se fusionan con HANNA LIFE '
                              '(que mide vitalidad autonómica vía HRV/sueño/stress). Ambos sistemas '
                              'miden fenómenos fisiológicos distintos y deben interpretarse cruzados, '
                              'no combinados en un único número.'),
    }


if __name__ == '__main__':
    import os
    import psycopg2
    from db_compat import ConexionCompat
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        exit(1)
    conn = ConexionCompat(psycopg2.connect(db_url))

    print("=== ACWR atleta 1 ===")
    print(calcular_acwr(conn, 1))

    print("\n=== Monotonía/Strain atleta 1 ===")
    print(calcular_monotonia_strain(conn, 1))

    print("\n=== Resumen combinado ===")
    import json
    print(json.dumps(resumen_riesgo_lesion(conn, 1), indent=2, ensure_ascii=False))
