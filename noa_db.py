"""
noa_db.py
---------
Modulo central de acceso a la base de datos NOA.
Todos los scripts del pipeline usan este modulo para
leer y escribir datos — nunca acceden a la DB directamente.

USO:
  from noa_db import NOADatabase
  db = NOADatabase()
  atleta = db.get_atleta(1)
  db.agregar_sesion(atleta_id=1, datos=...)
"""

import pandas as pd
import numpy as np
import os
import psycopg2
import psycopg2.extras
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from db_compat import ConexionCompat

# ─── CONFIGURACION ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
# Antes: archivo SQLite local (noa.db). Ahora: cadena de conexión a Postgres
# (Supabase), vía variable de entorno DATABASE_URL. Se mantiene el nombre
# DB_PATH para no tener que renombrar todos los call-sites que lo usan
# como valor por defecto del constructor.
DB_PATH = os.environ.get('DATABASE_URL', '')


# ─── CLASE PRINCIPAL ──────────────────────────────────────────────────────────

class NOADatabase:

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._verificar_db()

    def _conn(self):
        # DictCursor: equivalente Postgres de sqlite3.Row — permite acceder
        # a las filas tanto por nombre de columna (row['nombre']) como por
        # índice numérico (row[0]), igual que el código original esperaba.
        conn = psycopg2.connect(self.db_path, cursor_factory=psycopg2.extras.DictCursor)
        return ConexionCompat(conn)

    def _verificar_db(self):
        if not self.db_path:
            print('[NOAdb] Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase).')

    # ── ATLETAS ───────────────────────────────────────────────────────────────

    def get_atletas(self) -> pd.DataFrame:
        """Retorna todos los atletas activos."""
        with self._conn() as conn:
            return pd.read_sql('SELECT * FROM atletas WHERE activo=1', conn)

    def get_atleta(self, atleta_id: int) -> dict:
        """Retorna un atleta por ID."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM atletas WHERE id=%s', (atleta_id,)).fetchone()
            return dict(row) if row else {}

    def get_atleta_by_email(self, email: str) -> dict:
        """Retorna un atleta por email."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM atletas WHERE email=%s', (email,)).fetchone()
            return dict(row) if row else {}

    def crear_atleta(self, datos: dict) -> int:
        """Crea un atleta nuevo. Retorna el ID."""
        # Mapear todos los campos posibles de la tabla atletas
        campos = {
            'nombre':           datos.get('nombre'),
            'email':            datos.get('email'),
            'garmin_user':      datos.get('garmin_user') or datos.get('garmin_email') or datos.get('email'),
            'garmin_pass':      datos.get('garmin_pass') or datos.get('garmin_password'),
            'lthr_run':         datos.get('lthr_run', 162),
            'lthr_bike':        datos.get('lthr_bike', 160),
            'lthr_swim':        datos.get('lthr_swim'),
            'ftp_watts':        datos.get('ftp_watts') or datos.get('ftp'),
            'hr_max':           datos.get('hr_max', 190),
            'peso_kg':          datos.get('peso_kg') or datos.get('peso'),
            'altura_cm':        datos.get('altura_cm'),
            'edad':             datos.get('edad'),
            'sexo':             datos.get('sexo', 'M'),
            'deporte_ppal':     datos.get('deporte_ppal', 'running'),
            'css_100m':         datos.get('css_100m') or datos.get('css'),
            'nivel_experiencia':datos.get('nivel_experiencia') or datos.get('nivel'),
            'horas_semana':     datos.get('horas_semana'),
        }
        # Filtrar None para no pisar defaults de la DB
        campos_filtrados = {k: v for k, v in campos.items() if v is not None}
        cols = ', '.join(campos_filtrados.keys())
        # Placeholders nombrados estilo psycopg2 (%(nombre)s) — equivalente
        # a los :nombre que usaba sqlite3 (ambos aceptan dict como params).
        placeholders = ', '.join([f'%({k})s' for k in campos_filtrados.keys()])
        with self._conn() as conn:
            cur = conn.cursor()
            # INSERT OR IGNORE (SQLite) → INSERT ... ON CONFLICT (email)
            # DO NOTHING (Postgres). La restricción UNIQUE real está en la
            # columna email (confirmado contra el esquema real de la tabla
            # atletas) — por eso el ON CONFLICT se especifica sobre esa
            # columna, no de forma genérica.
            cur.execute(
                f'INSERT INTO atletas ({cols}) VALUES ({placeholders}) '
                f'ON CONFLICT (email) DO NOTHING RETURNING id',
                campos_filtrados
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                return row[0]
            # Hubo conflicto (email ya existía) — sqlite3 con INSERT OR
            # IGNORE no insertaba nada pero el código original confiaba en
            # lastrowid, cuyo valor en ese caso era ambiguo. Para que el
            # comportamiento sea útil y predecible, se busca el id del
            # registro existente con ese email.
            email = campos_filtrados.get('email')
            if email:
                cur.execute('SELECT id FROM atletas WHERE email=%s', (email,))
                existente = cur.fetchone()
                conn.commit()
                return existente[0] if existente else None
            conn.commit()
            return None

    # ── SESIONES ──────────────────────────────────────────────────────────────

    def get_sesiones(self, atleta_id: int,
                     desde: str = None, hasta: str = None,
                     sport: str = None) -> pd.DataFrame:
        """Retorna sesiones de un atleta con filtros opcionales."""
        q = 'SELECT * FROM sesiones WHERE atleta_id=%s'
        params = [atleta_id]
        if desde:
            q += ' AND fecha >= %s'; params.append(desde)
        if hasta:
            q += ' AND fecha <= %s'; params.append(hasta)
        if sport:
            q += ' AND sport = %s'; params.append(sport)
        q += ' ORDER BY fecha'
        with self._conn() as conn:
            return pd.read_sql(q, conn, params=params)

    def get_ultima_sesion(self, atleta_id: int) -> dict:
        """Retorna la ultima sesion del atleta."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM sesiones WHERE atleta_id=%s ORDER BY fecha DESC LIMIT 1',
                (atleta_id,)).fetchone()
            return dict(row) if row else {}

    def sesion_existe(self, atleta_id: int, fecha: str) -> bool:
        """Verifica si ya existe una sesion para esa fecha."""
        with self._conn() as conn:
            n = conn.execute(
                'SELECT COUNT(*) FROM sesiones WHERE atleta_id=%s AND fecha=%s',
                (atleta_id, fecha[:10])).fetchone()[0]
            return n > 0

    def agregar_sesion(self, atleta_id: int, datos: dict) -> int:
        """
        Agrega una sesion nueva. Retorna el ID.
        datos debe incluir al menos: fecha, distance_km, duration_min
        """
        fecha = str(datos.get('fecha', ''))[:10]
        if self.sesion_existe(atleta_id, fecha):
            print(f'  [NOAH] Sesion {fecha} ya existe para atleta {atleta_id}')
            return -1

        campos = ['atleta_id', 'fecha']
        valores = [atleta_id, fecha]

        cols_opcionales = [
            'sport','distance_km','duration_min','hr_avg','hr_max',
            'pace','speed_kmh','cadence','stride','temp','ascent_m','calories',
            'tss_total','tss_z12','tss_z34','tss_z56','ctl','atl','tsb',
            'form_status','session_type','tipo_sesion',
            'n_laps','n_series','pace_min','pace_std','pace_drift',
            'pace_series_avg','pace_recup_avg','consistencia_series',
            'presc_tipo','presc_duracion','presc_hr_min','presc_hr_max',
            'presc_pace_obj','presc_tss','cumplimiento_pct','cumplimiento_flag',
            'fuente',
        ]
        for col in cols_opcionales:
            if col in datos:
                v = datos[col]
                campos.append(col)
                valores.append(None if (v is not None and pd.isna(v)) else v)

        placeholders = ','.join(['%s'] * len(valores))
        cols_str = ','.join(campos)

        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f'INSERT INTO sesiones ({cols_str}) VALUES ({placeholders}) RETURNING id',
                valores)
            sid = cur.fetchone()[0]
            conn.commit()
            print(f'  [NOAH] Sesion {fecha} agregada (ID: {sid})')
            return sid

    def actualizar_ctl_atl_tsb(self, atleta_id: int):
        """
        Recalcula CTL/ATL/TSB para todas las sesiones del atleta.
        Multideporte: suma TSS de TODOS los deportes del mismo dia antes
        de aplicar la EMA, igual que TrainingPeaks/WKO.
        """
        # Normalizar sport='swim' → 'swimming' y leer datos
        conn = self._conn()
        # Borrar 'swim' duplicados donde ya existe 'swimming' ese día
        conn.execute('''
            DELETE FROM sesiones
            WHERE atleta_id=%s AND sport='swim'
            AND fecha IN (
                SELECT fecha FROM sesiones
                WHERE atleta_id=%s AND sport='swimming'
            )
        ''', (atleta_id, atleta_id))
        # Renombrar restantes swim → swimming
        conn.execute(
            "UPDATE sesiones SET sport='swimming' WHERE atleta_id=%s AND sport='swim'",
            (atleta_id,)
        )
        conn.commit()
        df = pd.read_sql(
            '''SELECT id, fecha, sport, tss_total
               FROM sesiones WHERE atleta_id=%s
               ORDER BY fecha, id''',
            conn, params=[atleta_id]
        )
        conn.close()

        if len(df) == 0:
            return

        df['fecha']     = df['fecha'].astype(str).str[:10]
        df['tss_total'] = df['tss_total'].fillna(0)

        # TSS diario = suma de todos los deportes ese dia
        tss_diario = (
            df.groupby('fecha')['tss_total']
            .sum().reset_index().sort_values('fecha')
        )

        # Rellenar dias sin actividad para EMA correcta
        fecha_min = pd.to_datetime(tss_diario['fecha'].min())
        fecha_max = pd.to_datetime(tss_diario['fecha'].max())
        todos = pd.DataFrame({
            'fecha': pd.date_range(fecha_min, fecha_max, freq='D').strftime('%Y-%m-%d')
        })
        tss_diario = todos.merge(tss_diario, on='fecha', how='left').fillna(0)

        # EMA dia a dia
        a_ctl = 2 / (42 + 1)
        a_atl = 2 / (7 + 1)
        n = len(tss_diario)
        ctl_d = np.zeros(n)
        atl_d = np.zeros(n)
        for i in range(n):
            t = float(tss_diario.iloc[i]['tss_total'])
            if i == 0:
                ctl_d[i] = t; atl_d[i] = t
            else:
                ctl_d[i] = ctl_d[i-1] * (1 - a_ctl) + t * a_ctl
                atl_d[i] = atl_d[i-1] * (1 - a_atl) + t * a_atl

        # Mapa fecha → (ctl, atl, tsb) — float() explícito: ctl_d/atl_d son
        # arrays de NumPy, así que sin esta conversión cada valor queda
        # como numpy.float64 (no float nativo de Python). SQLite no
        # distinguía esto y lo aceptaba igual, pero psycopg2 con Postgres
        # intenta serializar numpy.float64 literalmente como texto
        # ("np.float64(0.0)") dentro del SQL, rompiendo la consulta.
        ctl_map = {
            row['fecha']: (
                round(float(ctl_d[i]), 2),
                round(float(atl_d[i]), 2),
                round(float(ctl_d[i] - atl_d[i]), 2),
            )
            for i, row in tss_diario.iterrows()
        }

        def form_status(t):
            if t < -30: return 'overreaching'
            if t < -10: return 'loading'
            if t < 5:   return 'neutral'
            if t < 25:  return 'fresh'
            return 'detraining'

        conn2 = self._conn()
        for _, row in df.iterrows():
            vals = ctl_map.get(str(row['fecha'])[:10])
            if not vals:
                continue
            ctl_v, atl_v, tsb_v = vals
            conn2.execute('''
                UPDATE sesiones SET ctl=%s, atl=%s, tsb=%s, form_status=%s
                WHERE id=%s
            ''', (ctl_v, atl_v, tsb_v, form_status(tsb_v), int(row['id'])))
        conn2.commit()
        conn2.close()

        ctl_f = round(float(ctl_d[-1]), 1)
        atl_f = round(float(atl_d[-1]), 1)
        tsb_f = round(ctl_f - atl_f, 1)
        print(f'  [NOAH] CTL/ATL/TSB recalculados ({len(df)} sesiones, {n} dias)')
        print(f'  [NOAH] CTL={ctl_f}  ATL={atl_f}  TSB={tsb_f}')
        return {'ctl': ctl_f, 'atl': atl_f, 'tsb': tsb_f}

    # ── SLEEP / HRV ───────────────────────────────────────────────────────────

    def get_sleep_hrv(self, atleta_id: int,
                      ultimos_dias: int = 90) -> pd.DataFrame:
        """Retorna datos de sueño y HRV de los ultimos N dias."""
        desde = str(date.today() - timedelta(days=ultimos_dias))
        with self._conn() as conn:
            return pd.read_sql('''
            SELECT * FROM sleep_hrv
            WHERE atleta_id=%s AND fecha >= %s
            ORDER BY fecha
            ''', conn, params=[atleta_id, desde])

    def get_ultimo_sleep(self, atleta_id: int) -> dict:
        """Retorna el ultimo registro de sueño/HRV."""
        with self._conn() as conn:
            row = conn.execute('''
            SELECT * FROM sleep_hrv WHERE atleta_id=%s
            ORDER BY fecha DESC LIMIT 1
            ''', (atleta_id,)).fetchone()
            return dict(row) if row else {}

    def agregar_sleep(self, atleta_id: int, datos: dict) -> bool:
        """Agrega o actualiza un registro de sueño/HRV."""
        fecha = str(datos.get('fecha', ''))[:10]
        with self._conn() as conn:
            # Asegurar columnas existen — antes esto eran 2 chequeos
            # separados (uno parcial, otro completo) vía PRAGMA; ahora se
            # unifica en una sola llamada al helper con todas las columnas
            # que se necesitan, sin cambiar el resultado final.
            from db_compat import asegurar_columnas
            asegurar_columnas(conn, 'sleep_hrv', [
                ('hr_reposo',      'INTEGER'),
                ('hrv_estimado_valor', 'DOUBLE PRECISION'),
                ('fc_nocturna',    'DOUBLE PRECISION'),
                ('spo2_avg',       'DOUBLE PRECISION'),
                ('spo2_min',       'DOUBLE PRECISION'),
                ('resp_avg',       'DOUBLE PRECISION'),
                ('resp_min',       'DOUBLE PRECISION'),
                ('resp_max',       'DOUBLE PRECISION'),
                ('sleep_stress',   'DOUBLE PRECISION'),
                ('restless_count', 'INTEGER'),
                ('awake_count',    'INTEGER'),
                ('light_h',        'DOUBLE PRECISION'),
                ('awake_h',        'DOUBLE PRECISION'),
                ('restful_score',  'DOUBLE PRECISION'),
                ('sleep_feedback', 'TEXT'),
                ('hanna_life',     'DOUBLE PRECISION'),
                ('hanna_nivel',    'TEXT'),
                ('hanna_scores',   'TEXT'),
                ('hanna_puede_cargar', 'INTEGER'),
                ('riesgo_viral',   'DOUBLE PRECISION'),
                ('riesgo_viral_nivel', 'TEXT'),
                ('riesgo_viral_alertas', 'TEXT'),
            ])
            conn.commit()

            # INSERT OR REPLACE (SQLite) → INSERT ... ON CONFLICT (atleta_id,
            # fecha) DO UPDATE (Postgres). La restricción UNIQUE real está
            # sobre (atleta_id, fecha) — confirmado contra el esquema real
            # de la tabla sleep_hrv. DO UPDATE reescribe las mismas columnas
            # que SQLite reemplazaba por completo con OR REPLACE.
            conn.execute('''
            INSERT INTO sleep_hrv
            (atleta_id, fecha, hrv_rmssd, hrv_ratio, hrv_flag,
             hrv_baseline_7d, hrv_estimado, hrv_estimado_valor,
             sleep_h, deep_h, rem_h, light_h, awake_h,
             sleep_score, recovery_score, restful_score, sleep_feedback,
             stress_avg, sleep_stress, body_battery, spo2,
             hr_reposo, fc_nocturna,
             spo2_avg, spo2_min,
             resp_avg, resp_min, resp_max,
             restless_count, awake_count)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (atleta_id, fecha) DO UPDATE SET
                hrv_rmssd=EXCLUDED.hrv_rmssd, hrv_ratio=EXCLUDED.hrv_ratio,
                hrv_flag=EXCLUDED.hrv_flag, hrv_baseline_7d=EXCLUDED.hrv_baseline_7d,
                hrv_estimado=EXCLUDED.hrv_estimado, hrv_estimado_valor=EXCLUDED.hrv_estimado_valor,
                sleep_h=EXCLUDED.sleep_h, deep_h=EXCLUDED.deep_h, rem_h=EXCLUDED.rem_h,
                light_h=EXCLUDED.light_h, awake_h=EXCLUDED.awake_h,
                sleep_score=EXCLUDED.sleep_score, recovery_score=EXCLUDED.recovery_score,
                restful_score=EXCLUDED.restful_score, sleep_feedback=EXCLUDED.sleep_feedback,
                stress_avg=EXCLUDED.stress_avg, sleep_stress=EXCLUDED.sleep_stress,
                body_battery=EXCLUDED.body_battery, spo2=EXCLUDED.spo2,
                hr_reposo=EXCLUDED.hr_reposo, fc_nocturna=EXCLUDED.fc_nocturna,
                spo2_avg=EXCLUDED.spo2_avg, spo2_min=EXCLUDED.spo2_min,
                resp_avg=EXCLUDED.resp_avg, resp_min=EXCLUDED.resp_min, resp_max=EXCLUDED.resp_max,
                restless_count=EXCLUDED.restless_count, awake_count=EXCLUDED.awake_count
            ''', (
                atleta_id, fecha,
                datos.get('hrv_rmssd'),
                datos.get('hrv_ratio'),
                datos.get('hrv_flag'),
                datos.get('hrv_baseline_7d'),
                int(datos.get('hrv_estimado', 0)),
                datos.get('hrv_estimado_valor'),
                datos.get('sleep_h'),
                datos.get('deep_h'),
                datos.get('rem_h'),
                datos.get('light_h'),
                datos.get('awake_h'),
                datos.get('sleep_score'),
                datos.get('recovery_score'),
                datos.get('restful_score'),
                datos.get('sleep_feedback'),
                datos.get('stress_avg'),
                datos.get('sleep_stress'),
                datos.get('body_battery'),
                datos.get('spo2') or datos.get('spo2_avg'),
                datos.get('hr_reposo'),
                datos.get('fc_nocturna'),
                datos.get('spo2_avg'),
                datos.get('spo2_min'),
                datos.get('resp_avg'),
                datos.get('resp_min'),
                datos.get('resp_max'),
                datos.get('restless_count'),
                datos.get('awake_count'),
            ))

            # Guardar series nocturnas si están disponibles
            series_updates = {}
            for col in ['sleep_hr_serie','sleep_stress_serie','sleep_stress_avg','resp_serie']:
                if datos.get(col) is not None:
                    series_updates[col] = datos[col]
            if series_updates:
                sets = ', '.join(f'{k}=%s' for k in series_updates)
                vals = list(series_updates.values())
                conn.execute(
                    f'UPDATE sleep_hrv SET {sets} WHERE atleta_id=%s AND fecha=%s',
                    vals + [atleta_id, fecha]
                )
            conn.commit()
        return True

    # ── LAPS ──────────────────────────────────────────────────────────────────

    def get_laps(self, atleta_id: int,
                 sesion_id: int = None) -> pd.DataFrame:
        """Retorna laps de un atleta o de una sesion especifica."""
        if sesion_id:
            q = 'SELECT * FROM laps WHERE atleta_id=%s AND sesion_id=%s ORDER BY lap_num'
            params = [atleta_id, sesion_id]
        else:
            q = 'SELECT * FROM laps WHERE atleta_id=%s ORDER BY fecha, lap_num'
            params = [atleta_id]
        with self._conn() as conn:
            return pd.read_sql(q, conn, params=params)

    def agregar_laps(self, atleta_id: int,
                     sesion_id: int, fecha: str,
                     laps: list) -> int:
        """Agrega laps de una sesion. Retorna cantidad insertada."""
        if not laps:
            return 0
        insertados = 0
        with self._conn() as conn:
            for lap in laps:
                conn.execute('''
                INSERT INTO laps
                (atleta_id, sesion_id, fecha, activity_id, lap_num,
                 distance_km, duration_min, pace, hr_avg, hr_max,
                 cadence, stride_m, ascent_m)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ''', (
                    atleta_id, sesion_id, fecha[:10],
                    lap.get('activity_id'),
                    lap.get('lap_num'),
                    lap.get('distance_km'),
                    lap.get('duration_min'),
                    lap.get('pace'),
                    lap.get('hr_avg'),
                    lap.get('hr_max'),
                    lap.get('cadence'),
                    lap.get('stride_m'),
                    lap.get('ascent_m'),
                ))
                insertados += 1
            conn.commit()
        return insertados

    # ── PRESCRIPCIONES ────────────────────────────────────────────────────────

    def get_prescripcion_semana(self, atleta_id: int,
                                semana_id: str) -> dict:
        """Retorna la prescripcion de una semana."""
        with self._conn() as conn:
            row = conn.execute('''
            SELECT * FROM prescripciones
            WHERE atleta_id=%s AND semana_id=%s
            ORDER BY fecha_generada DESC LIMIT 1
            ''', (atleta_id, semana_id)).fetchone()
            return dict(row) if row else {}

    def guardar_prescripcion(self, atleta_id: int,
                             semana_id: str, datos: dict) -> int:
        """Guarda una prescripcion semanal."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute('''
            INSERT INTO prescripciones
            (atleta_id, semana_id, fecha_generada, fase,
             ses1_fecha, ses1_tipo, ses1_duracion, ses1_hr_min, ses1_hr_max, ses1_pace_obj, ses1_tss,
             ses2_fecha, ses2_tipo, ses2_duracion, ses2_hr_min, ses2_hr_max, ses2_pace_obj, ses2_tss,
             ses3_fecha, ses3_tipo, ses3_duracion, ses3_hr_min, ses3_hr_max, ses3_pace_obj, ses3_tss,
             tss_semana_total, estado)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            ''', (
                atleta_id, semana_id,
                str(date.today()), datos.get('fase','BASE'),
                datos.get('ses1_fecha'), datos.get('ses1_tipo'),
                datos.get('ses1_duracion'), datos.get('ses1_hr_min'),
                datos.get('ses1_hr_max'), datos.get('ses1_pace_obj'),
                datos.get('ses1_tss'),
                datos.get('ses2_fecha'), datos.get('ses2_tipo'),
                datos.get('ses2_duracion'), datos.get('ses2_hr_min'),
                datos.get('ses2_hr_max'), datos.get('ses2_pace_obj'),
                datos.get('ses2_tss'),
                datos.get('ses3_fecha'), datos.get('ses3_tipo'),
                datos.get('ses3_duracion'), datos.get('ses3_hr_min'),
                datos.get('ses3_hr_max'), datos.get('ses3_pace_obj'),
                datos.get('ses3_tss'),
                datos.get('tss_semana_total'),
                'pendiente',
            ))
            nuevo_id = cur.fetchone()[0]
            conn.commit()
            return nuevo_id

    # ── CUMPLIMIENTO ──────────────────────────────────────────────────────────

    def calcular_cumplimiento(self, sesion_real: dict,
                               presc: dict,
                               tolerancia: float = 0.10) -> dict:
        """
        Compara la sesion ejecutada con la prescripta.
        Tolerancia = 10% por defecto.
        Retorna dict con pct y flag (verde/amarillo/rojo).
        """
        scores = []

        # Duracion
        if presc.get('presc_duracion') and sesion_real.get('duration_min'):
            ratio = sesion_real['duration_min'] / presc['presc_duracion']
            scores.append(ratio)

        # HR promedio vs rango
        if (presc.get('presc_hr_min') and presc.get('presc_hr_max')
                and sesion_real.get('hr_avg')):
            hr = sesion_real['hr_avg']
            hr_min = presc['presc_hr_min'] * (1 - tolerancia)
            hr_max = presc['presc_hr_max'] * (1 + tolerancia)
            scores.append(1.0 if hr_min <= hr <= hr_max else 0.5)

        # Pace objetivo
        if presc.get('presc_pace_obj') and sesion_real.get('pace'):
            ratio = presc['presc_pace_obj'] / sesion_real['pace']
            scores.append(min(ratio, 1.0 / ratio))

        if not scores:
            return {'cumplimiento_pct': None, 'cumplimiento_flag': 'sin_datos'}

        pct = round(sum(scores) / len(scores) * 100, 1)

        if pct >= 90:   flag = 'verde'
        elif pct >= 70: flag = 'amarillo'
        else:           flag = 'rojo'

        return {'cumplimiento_pct': pct, 'cumplimiento_flag': flag}

    # ── ESTADO ACTUAL ─────────────────────────────────────────────────────────

    def get_estado_actual(self, atleta_id: int) -> dict:
        """
        Retorna el estado completo del atleta hoy.

        REGLA DE IMPUTACION:
        - CTL/ATL/TSB: se proyecta a hoy decayendo con EMA desde la ultima sesion.
          Si no entreno, TSS=0 y el CTL baja — eso es correcto, no es dato faltante.
        - HRV/sueno/recovery: solo se usa si el dato tiene menos de 7 dias.
          Si es mas antiguo, se devuelve None — ausencia de medicion, no cero.
        """
        from datetime import date, timedelta
        import numpy as np

        atleta     = self.get_atleta(atleta_id)
        ultima_ses = self.get_ultima_sesion(atleta_id)

        # ── CTL/ATL/TSB proyectado a hoy ─────────────────────────────────────
        # Tomar el CTL/ATL de la ultima sesion y decaer hasta hoy con TSS=0
        ctl_base = ultima_ses.get('ctl') or 0
        atl_base = ultima_ses.get('atl') or 0
        fecha_ult = ultima_ses.get('fecha')

        if fecha_ult and ctl_base > 0:
            try:
                dias_sin_entreno = (date.today() - date.fromisoformat(str(fecha_ult)[:10])).days
                a_ctl = 2 / (42 + 1)
                a_atl = 2 / (7 + 1)
                # Decaer con TSS=0 por cada dia sin entrenar
                ctl_hoy = ctl_base
                atl_hoy = atl_base
                for _ in range(max(0, dias_sin_entreno)):
                    ctl_hoy = ctl_hoy * (1 - a_ctl)
                    atl_hoy = atl_hoy * (1 - a_atl)
                ctl_hoy = round(ctl_hoy, 2)
                atl_hoy = round(atl_hoy, 2)
                tsb_hoy = round(ctl_hoy - atl_hoy, 2)
            except Exception:
                ctl_hoy = ctl_base
                atl_hoy = atl_base
                tsb_hoy = round(ctl_base - atl_base, 2)
        else:
            ctl_hoy = ctl_base
            atl_hoy = atl_base
            tsb_hoy = round(ctl_base - atl_base, 2)

        def form_status(t):
            if t < -30: return 'overreaching'
            if t < -10: return 'loading'
            if t < 5:   return 'neutral'
            if t < 25:  return 'fresh'
            return 'detraining'

        # ── HRV / sueno / biomarcadores ───────────────────────────────────────
        # Solo usar si el dato es reciente (menos de 7 dias)
        # Si es mas antiguo = ausencia de medicion, no imputar
        ultimo_sleep = self.get_ultimo_sleep(atleta_id)
        MAX_DIAS_BIO = 7

        def bio_val(key):
            """Retorna el valor solo si el sleep es reciente, sino None."""
            if not ultimo_sleep:
                return None
            fecha_sleep = ultimo_sleep.get('fecha')
            if not fecha_sleep:
                return None
            try:
                dias = (date.today() - date.fromisoformat(str(fecha_sleep)[:10])).days
                if dias > MAX_DIAS_BIO:
                    return None
            except Exception:
                return None
            return ultimo_sleep.get(key)

        def bio_hrv():
            """HRV real si existe, estimado si no, None si no hay nada."""
            if not ultimo_sleep:
                return None, None
            hrv_real = ultimo_sleep.get('hrv_rmssd')
            hrv_est  = ultimo_sleep.get('hrv_estimado_valor')
            hrv_ms   = hrv_real if hrv_real else hrv_est
            es_est   = hrv_real is None and hrv_est is not None
            return hrv_ms, es_est

        # Semana actual
        df_ses = self.get_sesiones(atleta_id,
            desde=str(date.today() - timedelta(days=7)))

        return {
            'atleta'      : atleta,
            'ctl'         : ctl_hoy,
            'atl'         : atl_hoy,
            'tsb'         : tsb_hoy,
            'form_status' : form_status(tsb_hoy),
            'dias_sin_entreno': (date.today() - date.fromisoformat(str(fecha_ult)[:10])).days if fecha_ult else None,
            # Biomarcadores — HRV real o estimado
            'hrv_ratio'   : bio_val('hrv_ratio'),
            'hrv_flag'    : bio_val('hrv_flag') or bio_val('hrv_flag'),
            'hrv_ms'      : bio_hrv()[0],
            'hrv_es_estimado': bio_hrv()[1],
            'sleep_h'     : bio_val('sleep_h'),
            'recovery'    : bio_val('recovery_score'),
            'deep_h'      : bio_val('deep_h'),
            'rem_h'       : bio_val('rem_h'),
            'stress'      : bio_val('stress_avg'),
            'body_battery': bio_val('body_battery'),
            'hr_reposo'   : bio_val('hr_reposo'),
            'hanna_life'  : bio_val('hanna_life'),
            'hanna_nivel' : bio_val('hanna_nivel'),
            'riesgo_viral': bio_val('riesgo_viral'),
            'riesgo_viral_nivel': bio_val('riesgo_viral_nivel'),
            # Semana
            'km_semana'   : round(df_ses['distance_km'].sum() / (1000 if df_ses['distance_km'].sum() > 500 else 1), 1) if len(df_ses) > 0 else 0,
            'tss_semana'  : round(df_ses['tss_total'].sum(), 0) if len(df_ses) > 0 else 0,
            'ses_semana'  : len(df_ses),
        }

    # ── DATOS PARA GRAFICOS ───────────────────────────────────────────────────

    def get_datos_graficos(self, atleta_id: int,
                           dias: int = 180) -> dict:
        """
        Retorna los datos necesarios para los graficos del dashboard.
        training: CTL/ATL/TSB historico
        sleep   : sueño historico
        """
        desde = str(date.today() - timedelta(days=dias))

        with self._conn() as conn:
            df_ses = pd.read_sql('''
            SELECT fecha, ctl, atl, tsb FROM sesiones
            WHERE atleta_id=%s AND fecha >= %s AND ctl IS NOT NULL
            ORDER BY fecha
            ''', conn, params=[atleta_id, desde])

            df_sleep = pd.read_sql('''
            SELECT s.fecha, s.hrv_ratio, s.hrv_flag, s.recovery_score,
                   sl.sleep_h, sl.deep_h, sl.rem_h, sl.light_h
            FROM sleep_hrv sl
            LEFT JOIN sleep_hrv s ON s.id = sl.id
            WHERE sl.atleta_id=%s AND sl.fecha >= %s
            ORDER BY sl.fecha
            ''', conn, params=[atleta_id, desde])

            # Fix — query mas simple
            df_sleep = pd.read_sql('''
            SELECT fecha, hrv_ratio, hrv_flag, recovery_score,
                   sleep_h, deep_h, rem_h, light_h
            FROM sleep_hrv
            WHERE atleta_id=%s AND fecha >= %s
            ORDER BY fecha
            ''', conn, params=[atleta_id, desde])

        training = []
        for _, r in df_ses.iterrows():
            # Buscar HRV de ese dia
            match = df_sleep[df_sleep['fecha'] == r['fecha']]
            hrv_r_val = match['hrv_ratio'].iloc[0] if len(match) > 0 else None
            hrv_f_val = match['hrv_flag'].iloc[0] if len(match) > 0 else None
            rec_val   = match['recovery_score'].iloc[0] if len(match) > 0 else None
            hrv_r = float(hrv_r_val) if hrv_r_val is not None else 1.0
            hrv_f = str(hrv_f_val) if hrv_f_val is not None else 'amarillo'
            rec   = float(rec_val) if rec_val is not None else 80.0
            training.append({
                'd'  : str(r['fecha'])[:10],
                'ctl': round(float(r['ctl']), 1),
                'atl': round(float(r['atl']), 1),
                'tsb': round(float(r['tsb']), 1),
                'hrv': hrv_r if hrv_r and not pd.isna(hrv_r) else 1.0,
                'hf' : hrv_f if hrv_f != 'nan' else 'amarillo',
                'rec': rec if rec and not pd.isna(rec) else 80.0,
            })

        sleep = []
        for _, r in df_sleep.tail(42).iterrows():
            sleep.append({
                'f'    : str(r['fecha'])[:10],
                'tot'  : round(float(r.get('sleep_h') or 0), 2),
                'deep' : round(float(r.get('deep_h') or 0), 2),
                'rem'  : round(float(r.get('rem_h') or 0), 2),
                'light': round(float(r.get('light_h') or 0), 2),
            })

        return {'training': training, 'sleep': sleep}

    # ── EXPORTAR A CSV (compatibilidad) ───────────────────────────────────────

    def exportar_dataset_csv(self, atleta_id: int,
                              output_path: str = None) -> str:
        """Exporta las sesiones a CSV para compatibilidad con el pipeline."""
        df = self.get_sesiones(atleta_id)
        out = output_path or str(BASE_DIR / f'dataset_atleta_{atleta_id}.csv')
        df.to_csv(out, index=False)
        print(f'  [NOAH] Exportado: {out} ({len(df)} sesiones)')
        return out


# ─── USO DIRECTO ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    db = NOADatabase()

    print('='*50)
    print('  NOA Database — Estado actual')
    print('='*50)

    atletas = db.get_atletas()
    for _, a in atletas.iterrows():
        print(f'\nAtleta: {a["nombre"]} (ID: {a["id"]})')
        estado = db.get_estado_actual(int(a['id']))
        print(f'  CTL: {estado["ctl"]:.1f}  ATL: {estado["atl"]:.1f}  TSB: {estado["tsb"]:.1f}')
        print(f'  HRV: {estado["hrv_ms"]} ms [{estado["hrv_flag"]}]')
        print(f'  Sueño: {estado["sleep_h"]}h')
        print(f'  Semana: {estado["ses_semana"]} ses / {estado["km_semana"]} km / TSS {estado["tss_semana"]}')
