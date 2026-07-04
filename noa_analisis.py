"""
noa_analisis.py
---------------
Modulo de analisis de distribucion de carga y diagnostico NOA.

Detecta patrones de entrenamiento inadecuados:
- Sobrecarga de intensidad (demasiado Z3-Z4)
- Base aerobica deficiente
- Proyeccion de CTL con distribucion actual vs correcta
- Alertas para coach y atleta

USO:
  from noa_analisis import NOAAnalisis
  analisis = NOAAnalisis(atleta_id=2, db_path='noa.db')
  diagnostico = analisis.generar_diagnostico()
"""

import psycopg2
import json
import numpy as np
import os
from datetime import date, timedelta
from pathlib import Path
from db_compat import ConexionCompat

BASE_DIR = Path(__file__).parent


class NOAAnalisis:

    def __init__(self, atleta_id: int, db_path: str = None):
        self.atleta_id = atleta_id
        # Antes: ruta a archivo SQLite local. Ahora: cadena de conexión a
        # Postgres (Supabase), por defecto desde DATABASE_URL si no se pasa
        # explícitamente — mismo patrón que el resto de los módulos migrados.
        self.db_path   = db_path or os.environ.get('DATABASE_URL', '')
        self._conn     = None

    def conn(self):
        if not self._conn:
            self._conn = ConexionCompat(psycopg2.connect(self.db_path))
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── DATOS BASE ────────────────────────────────────────────

    def get_atleta(self) -> dict:
        row = self.conn().execute(
            'SELECT id, nombre, lthr_run, hr_max, edad FROM atletas WHERE id=%s',
            (self.atleta_id,)
        ).fetchone()
        if not row: return {}
        return {'id': row[0], 'nombre': row[1], 'lthr_run': row[2],
                'hr_max': row[3], 'edad': row[4]}

    def get_perfil(self) -> dict:
        row = self.conn().execute(
            'SELECT datos_json FROM perfiles_macro WHERE atleta_id=%s AND activo=1',
            (self.atleta_id,)
        ).fetchone()
        if not row: return {}
        return json.loads(row[0])

    def get_sesiones(self, dias: int = 90) -> list:
        desde = str(date.today() - timedelta(days=dias))
        return self.conn().execute('''
            SELECT fecha, sport, hr_avg, duration_min, tss_total, pace
            FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s AND duration_min > 10
            ORDER BY fecha DESC
        ''', (self.atleta_id, desde)).fetchall()

    # ── ANÁLISIS DE ZONAS ─────────────────────────────────────

    def analizar_distribucion_zonas(self, dias: int = 60) -> dict:
        """
        Calcula la distribución real de tiempo por zona
        comparada con la distribución recomendada para la fase actual.
        """
        atleta  = self.get_atleta()
        perfil  = self.get_perfil()
        lthr    = atleta.get('lthr_run', 162)
        sesiones = self.get_sesiones(dias)

        if not sesiones:
            return {'error': 'Sin sesiones suficientes', 'dias': dias}

        # Umbrales de zona por HR
        z1_max = lthr * 0.75
        z2_max = lthr * 0.87
        z3_max = lthr * 0.93
        z4_max = lthr * 1.00
        z5_max = lthr * 1.06

        # Clasificar sesiones por zona dominante
        tiempo_z1z2 = 0
        tiempo_z3z4 = 0
        tiempo_z5z6 = 0
        tiempo_sin_hr = 0
        total_min = 0

        for ses in sesiones:
            _, sport, hr_avg, dur_min, tss, pace = ses
            if not dur_min: continue
            total_min += dur_min

            if not hr_avg or hr_avg < 60:
                tiempo_sin_hr += dur_min
                continue

            if hr_avg <= z2_max:
                tiempo_z1z2 += dur_min
            elif hr_avg <= z4_max:
                tiempo_z3z4 += dur_min
            else:
                tiempo_z5z6 += dur_min

        tiempo_clasificado = tiempo_z1z2 + tiempo_z3z4 + tiempo_z5z6
        if tiempo_clasificado == 0:
            return {'error': 'Sin datos de HR suficientes'}

        # Porcentajes reales
        pct_z1z2_real = round(tiempo_z1z2 / tiempo_clasificado * 100, 1)
        pct_z3z4_real = round(tiempo_z3z4 / tiempo_clasificado * 100, 1)
        pct_z5z6_real = round(tiempo_z5z6 / tiempo_clasificado * 100, 1)

        # Porcentajes recomendados según fase
        fase = self._calcular_fase(perfil)
        pct_z1z2_ideal = perfil.get('f1_z12_pct', 80) if fase == 'F1' else \
                         perfil.get('f2_z12_pct', 68) if fase == 'F2' else \
                         perfil.get('f3_z12_pct', 65) if fase == 'F3' else 90
        pct_z3z4_ideal = perfil.get('f1_z34_pct', 15) if fase == 'F1' else \
                         perfil.get('f2_z34_pct', 22) if fase == 'F2' else \
                         perfil.get('f3_z34_pct', 30) if fase == 'F3' else 10
        pct_z5z6_ideal = 100 - pct_z1z2_ideal - pct_z3z4_ideal

        # Gap entre real e ideal
        gap_z1z2 = pct_z1z2_real - pct_z1z2_ideal
        gap_z3z4 = pct_z3z4_real - pct_z3z4_ideal

        # Score de alineacion 0-1 (1 = perfecto)
        desviacion = (abs(gap_z1z2) + abs(gap_z3z4)) / 2
        score_alineacion = max(0, round(1 - desviacion / 50, 2))

        return {
            'fase'           : fase,
            'dias_analizados': dias,
            'sesiones_n'     : len(sesiones),
            'total_horas'    : round(total_min / 60, 1),
            'distribucion_real': {
                'z1z2_pct': pct_z1z2_real,
                'z3z4_pct': pct_z3z4_real,
                'z5z6_pct': pct_z5z6_real,
            },
            'distribucion_ideal': {
                'z1z2_pct': pct_z1z2_ideal,
                'z3z4_pct': pct_z3z4_ideal,
                'z5z6_pct': pct_z5z6_ideal,
            },
            'gaps': {
                'z1z2': round(gap_z1z2, 1),
                'z3z4': round(gap_z3z4, 1),
            },
            'score_alineacion': score_alineacion,
            'tiempo_sin_hr_h' : round(tiempo_sin_hr / 60, 1),
        }

    # ── PROYECCIÓN DE CTL ─────────────────────────────────────

    def proyectar_ctl(self, semanas: int = 16) -> dict:
        """
        Proyecta el CTL a futuro con:
        A) Distribución actual (patrón histórico)
        B) Distribución correcta (según fase)
        """
        from noa_db import NOADatabase
        from datetime import date, timedelta
        db     = NOADatabase(self.db_path)
        estado = db.get_estado_actual(self.atleta_id)
        perfil = self.get_perfil()

        ctl_actual = estado.get('ctl') or 40.0

        # TSS real de las ultimas 4 semanas (mas preciso que el objetivo)
        desde_4sem = str(date.today() - timedelta(days=28))
        # strftime('%Y-%W', fecha) (SQLite) no existe en Postgres — el
        # equivalente para agrupar por año-semana es to_char con formato
        # ISO ('IYYY-IW'). fecha es TEXT en la tabla, por eso el cast ::date.
        row_tss = self.conn().execute('''
            SELECT AVG(tss_sem) FROM (
                SELECT SUM(tss_total) as tss_sem
                FROM sesiones
                WHERE atleta_id=%s AND fecha >= %s
                AND tss_total > 0
                GROUP BY to_char(fecha::date, 'IYYY-IW')
            ) sub
        ''', (self.atleta_id, desde_4sem)).fetchone()

        tss_semana_real = float(row_tss[0]) if row_tss and row_tss[0] else None
        tss_semana_obj  = perfil.get('tss_semana_f1_min', 185)

        # Usar el real si existe, sino el objetivo del perfil
        tss_semana = tss_semana_real if tss_semana_real and tss_semana_real > 20 else tss_semana_obj

        # Constante de tiempo CTL = 42 dias (estandar PMC)
        import math
        k_ctl = 1 - math.exp(-1/42)

        # Proyeccion A: patron actual
        ctl_a = ctl_actual
        proyeccion_a = []
        for s in range(semanas):
            for d in range(7):
                ctl_a = ctl_a + (tss_semana / 7 - ctl_a) * k_ctl
            proyeccion_a.append(round(ctl_a, 1))

        # Proyeccion B: con distribucion correcta (+15% TSS)
        tss_corregido = tss_semana * 1.15
        ctl_b = ctl_actual
        proyeccion_b = []
        for s in range(semanas):
            for d in range(7):
                ctl_b = ctl_b + (tss_corregido / 7 - ctl_b) * k_ctl
            proyeccion_b.append(round(ctl_b, 1))

        return {
            'ctl_actual'     : round(ctl_actual, 1),
            'semanas'        : semanas,
            'con_patron_actual': {
                'ctl_final'  : proyeccion_a[-1],
                'proyeccion' : proyeccion_a,
                'descripcion': 'Mantiene distribución actual de zonas',
            },
            'con_correccion': {
                'ctl_final'  : proyeccion_b[-1],
                'proyeccion' : proyeccion_b,
                'descripcion': 'Con distribución Z1-Z2 correcta para la fase',
                'ganancia'   : round(proyeccion_b[-1] - proyeccion_a[-1], 1),
            },
        }

    # ── DETECCIÓN DE PATRONES ─────────────────────────────────

    def detectar_patrones(self) -> list:
        """
        Detecta patrones problemáticos en el historial.
        Retorna lista de alertas con nivel y descripción.
        """
        atleta   = self.get_atleta()
        lthr     = atleta.get('lthr_run', 162)
        sesiones = self.get_sesiones(dias=60)
        alertas  = []

        if len(sesiones) < 5:
            return [{'nivel': 'info', 'codigo': 'pocos_datos',
                     'texto_coach': 'Menos de 5 sesiones en 60 días. Análisis limitado.',
                     'texto_atleta': 'Estamos conociendo tu historial.'}]

        # Calcular HR promedio histórico
        hrs = [s[2] for s in sesiones if s[2] and s[2] > 60]
        if hrs:
            hr_promedio = np.mean(hrs)
            if_promedio = hr_promedio / lthr

            if if_promedio > 0.88:
                alertas.append({
                    'nivel'       : 'alto',
                    'codigo'      : 'sobrecarga_intensidad',
                    'valor'       : round(if_promedio, 2),
                    'texto_coach' : (
                        f'IF promedio histórico: {if_promedio:.2f} ({hr_promedio:.0f}/{lthr} bpm). '
                        f'El atleta entrena sistemáticamente en Z3-Z4. '
                        f'Base aeróbica probablemente deficiente. '
                        f'Riesgo de meseta y lesión por sobrecarga.'
                    ),
                    'texto_atleta': (
                        'Estás entrenando muy fuerte en la mayoría de tus salidas. '
                        'Esto puede funcionar a corto plazo pero limita tu progreso. '
                        'Esta semana vamos a bajar la intensidad para construir '
                        'una base más sólida.'
                    ),
                })
            elif if_promedio < 0.72:
                alertas.append({
                    'nivel'       : 'moderado',
                    'codigo'      : 'intensidad_baja',
                    'valor'       : round(if_promedio, 2),
                    'texto_coach' : (
                        f'IF promedio muy bajo: {if_promedio:.2f}. '
                        f'El atleta podría tolerar más carga.'
                    ),
                    'texto_atleta': 'Podés aumentar un poco la intensidad en las sesiones de calidad.',
                })

        # Detectar irregularidad — semanas sin entrenar
        fechas = [s[0] for s in sesiones]
        if fechas:
            fecha_mas_antigua = min(fechas)
            fecha_mas_reciente = max(fechas)
            dias_rango = (date.fromisoformat(fecha_mas_reciente) -
                          date.fromisoformat(fecha_mas_antigua)).days
            sesiones_esperadas = dias_rango / 7 * 3  # 3 sesiones/semana
            ratio_completitud = len(sesiones) / max(sesiones_esperadas, 1)

            if ratio_completitud < 0.6:
                alertas.append({
                    'nivel'       : 'moderado',
                    'codigo'      : 'irregularidad',
                    'valor'       : round(ratio_completitud, 2),
                    'texto_coach' : (
                        f'Completitud: {ratio_completitud*100:.0f}% de las sesiones esperadas. '
                        f'Entrenamiento irregular. CTL puede no reflejar forma real.'
                    ),
                    'texto_atleta': (
                        'Tu entrenamiento ha sido irregular. '
                        'La consistencia es clave para mejorar.'
                    ),
                })

        # Detectar falta de sesiones largas (fondos)
        sesiones_largas = [s for s in sesiones if s[3] and s[3] > 60]
        if len(sesiones_largas) < 2:
            alertas.append({
                'nivel'       : 'moderado',
                'codigo'      : 'sin_fondos',
                'valor'       : len(sesiones_largas),
                'texto_coach' : 'Pocas sesiones largas (>60 min) en los últimos 60 días. Base aeróbica limitada.',
                'texto_atleta': 'Necesitamos agregar más salidas largas a tu plan.',
            })

        return alertas

    # ── DIAGNÓSTICO COMPLETO ──────────────────────────────────

    def generar_diagnostico(self) -> dict:
        """
        Genera el diagnóstico completo del atleta.
        Integra distribución, proyección y patrones.
        """
        atleta       = self.get_atleta()
        perfil       = self.get_perfil()
        distribucion = self.analizar_distribucion_zonas()
        proyeccion   = self.proyectar_ctl(semanas=16)
        alertas      = self.detectar_patrones()

        # Score general 0-100
        score_alineacion = distribucion.get('score_alineacion', 0.5)
        n_alertas_altas  = sum(1 for a in alertas if a.get('nivel') == 'alto')
        score_general    = max(0, round((score_alineacion * 100) - (n_alertas_altas * 20)))

        # Color del semáforo
        if score_general >= 70:
            color = 'verde'
            resumen_coach  = 'Distribución de carga alineada con la fase.'
            resumen_atleta = 'Estás entrenando bien para tu objetivo.'
        elif score_general >= 40:
            color = 'amarillo'
            resumen_coach  = 'Distribución de carga con desviaciones moderadas.'
            resumen_atleta = 'Hay algunas cosas que podemos mejorar en tu entrenamiento.'
        else:
            color = 'rojo'
            resumen_coach  = 'Distribución de carga significativamente desviada del plan.'
            resumen_atleta = 'Tu entrenamiento necesita ajustes importantes para llegar bien a la carrera.'

        return {
            'atleta_id'      : self.atleta_id,
            'atleta_nombre'  : atleta.get('nombre'),
            'fecha'          : str(date.today()),
            'score_general'  : score_general,
            'color'          : color,
            'resumen_coach'  : resumen_coach,
            'resumen_atleta' : resumen_atleta,
            'distribucion'   : distribucion,
            'proyeccion'     : proyeccion,
            'alertas'        : alertas,
            'carrera'        : perfil.get('carrera_nombre'),
            'carrera_fecha'  : perfil.get('carrera_fecha'),
        }

    # ── HELPERS ───────────────────────────────────────────────

    def _calcular_fase(self, perfil: dict) -> str:
        if not perfil.get('carrera_fecha'):
            return 'F1'
        carrera = date.fromisoformat(perfil['carrera_fecha'])
        semanas = (carrera - date.today()).days / 7
        taper   = perfil.get('taper_semanas', 2)
        f3      = perfil.get('f3_semanas', 4)
        f2      = perfil.get('f2_semanas', 6)
        if semanas <= taper:            return 'TAPER'
        if semanas <= taper + f3:       return 'F3'
        if semanas <= taper + f3 + f2:  return 'F2'
        return 'F1'

    def mostrar_diagnostico(self, d: dict = None):
        """Muestra el diagnóstico en consola."""
        if not d:
            d = self.generar_diagnostico()

        iconos = {'verde': '✓', 'amarillo': '~', 'rojo': '✗'}
        print()
        print('=' * 62)
        print(f'  NOA DIAGNÓSTICO — {d["atleta_nombre"]}')
        print('=' * 62)
        print(f'  Score: {d["score_general"]}/100  {iconos.get(d["color"], "?")} {d["color"].upper()}')
        print(f'  {d["resumen_coach"]}')
        print()

        dist = d.get('distribucion', {})
        if 'distribucion_real' in dist:
            real  = dist['distribucion_real']
            ideal = dist['distribucion_ideal']
            print(f'  DISTRIBUCIÓN DE ZONAS ({dist.get("total_horas", 0)}h en {dist.get("dias_analizados", 60)} días):')
            print(f'  {"Zona":<10} {"Real":>8} {"Ideal":>8} {"Gap":>8}')
            print(f'  {"─"*36}')
            print(f'  {"Z1-Z2":<10} {real["z1z2_pct"]:>7.1f}% {ideal["z1z2_pct"]:>7.0f}% {dist["gaps"]["z1z2"]:>+7.1f}%')
            print(f'  {"Z3-Z4":<10} {real["z3z4_pct"]:>7.1f}% {ideal["z3z4_pct"]:>7.0f}% {dist["gaps"]["z3z4"]:>+7.1f}%')
            print(f'  {"Z5-Z6":<10} {real["z5z6_pct"]:>7.1f}% {ideal["z5z6_pct"]:>7.0f}% --')
            print()

        proy = d.get('proyeccion', {})
        if proy:
            print(f'  PROYECCIÓN CTL ({proy["semanas"]} semanas):')
            print(f'  Actual:       CTL {proy["ctl_actual"]} → {proy["con_patron_actual"]["ctl_final"]}')
            print(f'  Con corrección: CTL {proy["ctl_actual"]} → {proy["con_correccion"]["ctl_final"]} (+{proy["con_correccion"]["ganancia"]})')
            print()

        if d.get('alertas'):
            print('  ALERTAS:')
            for a in d['alertas']:
                nivel = a.get('nivel', '').upper()
                print(f'  [{nivel}] {a["texto_coach"]}')
            print()

        print('=' * 62)


# ── USO DIRECTO ───────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--atleta', default=2, type=int)
    args = ap.parse_args()

    analisis = NOAAnalisis(atleta_id=args.atleta)
    d = analisis.generar_diagnostico()
    analisis.mostrar_diagnostico(d)
    analisis.close()
