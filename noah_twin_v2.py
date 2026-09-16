"""
noah_twin_v2.py — Digital Twin Fisiológico de NOAH
====================================================
Réplica virtual del cuerpo del atleta.

EL TWIN RESPONDE:
  "Lunes tenía que correr 6km escalonado, mayor parte en FTP,
   o pasadas de 6x400m a 1'40 con pausas de 2'.
   Martes 1h30 endurance en bike porque su biomarcador de 7 días
   atrás y la noche anterior decían que no podía cargar más.
   Y eso en una regresión da como resultado que el miércoles
   pueda entrenar en FTP."

ARQUITECTURA:
  ┌───────────────────────────────────────────────────────────┐
  │                    DIGITAL TWIN                           │
  │                                                           │
  │  1. MODELO FISIOLÓGICO (Banister por disciplina)         │
  │     - k1, k2, tau_pos, tau_neg calibrados con datos      │
  │     - Cross-transfer swim↔bike↔run                       │
  │     - Simula fitness/fatigue/form día a día              │
  │                                                           │
  │  2. MODELO DE READINESS (qué puedo hacer HOY)            │
  │     - Input: bio 7 días, bio anoche, carga reciente      │
  │     - Output: nivel_carga (ALTO/NORMAL/REDUCIDO/MÍNIMO)  │
  │     - Red neuronal entrenada con historial real           │
  │                                                           │
  │  3. MODELO DE RESPUESTA (qué pasa si hago X)             │
  │     - Input: estado_hoy + sesión propuesta               │
  │     - Output: estado_mañana (HRV, fatigue, readiness)    │
  │     - Permite encadenar: lun→mar→mié→... predicho        │
  │                                                           │
  │  4. GENERADOR DE SEMANAS (sesiones reales)               │
  │     - Usa patrones_sesion.py: bloques, zonas, paces      │
  │     - 9 sesiones/sem: swim/bike/run con estructura       │
  │     - Varía: nivel_carga → cambia reps, zonas, volumen   │
  │                                                           │
  │  5. SIMULADOR + OPTIMIZADOR                              │
  │     - Genera 100+ combinaciones de semana                │
  │     - Simula día a día: sesión → respuesta → readiness   │
  │     - Scoring: mejora performance × safety × absorción   │
  │     - Devuelve las 5 mejores semanas completas           │
  └───────────────────────────────────────────────────────────┘
"""

import math
import json
import warnings
import numpy as np
import pandas as pd
from datetime import date, timedelta
from copy import deepcopy
from typing import Dict, List, Tuple, Optional

warnings.filterwarnings('ignore')

DISCIPLINAS = ['running', 'cycling', 'swimming']

# Performance direction: con eficiencia cardíaca, MAYOR = mejor para todos
PERF_DIR = {'running': 1, 'cycling': 1, 'swimming': 1}

# Cross-transfer (Millet 2002)
TRANSFER = {
    'cycling':  {'running': 0.25, 'swimming': 0.05},
    'running':  {'cycling': 0.15, 'swimming': 0.05},
    'swimming': {'running': 0.10, 'cycling': 0.08},
}


# ═══════════════════════════════════════════════════════════════
#  DB HELPERS
# ═══════════════════════════════════════════════════════════════

def _sql(q, conn, p=None):
    try:
        cur = conn.cursor()
        cur.execute(q, p)
    except Exception:
        try: conn.rollback()
        except: pass
        cur = conn.cursor()
        cur.execute(q, p)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


def _sf(v, d=0.0):
    try:
        f = float(v)
        return f if math.isfinite(f) else d
    except:
        return d


def _pace(v):
    """Formatea pace decimal a min'seg\". Ej: 5.5 → 5'30\", 4.75 → 4'45\"."""
    v = round(v, 2)
    mins = int(v)
    secs = int(round((v - mins) * 60))
    return f"{mins}'{secs:02d}\""


# ═══════════════════════════════════════════════════════════════
#  1. BANISTER PER DISCIPLINA (calibrado con datos reales)
# ═══════════════════════════════════════════════════════════════

class BanisterDisc:
    """Banister impulse-response calibrado para UNA disciplina."""

    def __init__(self, disc, k1=0.05, k2=0.10, tau_p=42, tau_n=7, p0=0):
        self.disc = disc
        self.k1, self.k2 = k1, k2
        self.tau_p, self.tau_n = tau_p, tau_n
        self.p0 = p0
        self.fitness = 0.0
        self.fatigue = 0.0
        self._tss_hist = []

    def step(self, tss):
        dp = math.exp(-1 / max(self.tau_p, 1))
        dn = math.exp(-1 / max(self.tau_n, 1))
        self.fitness = self.fitness * dp + self.k1 * tss
        self.fatigue = self.fatigue * dn + self.k2 * tss
        self._tss_hist.append(tss)
        if len(self._tss_hist) > 28:
            self._tss_hist = self._tss_hist[-28:]

    @property
    def perf(self):
        return self.p0 + self.fitness - self.fatigue

    @property
    def form(self):
        return self.fitness - self.fatigue

    @property
    def tss_7d(self):
        return sum(self._tss_hist[-7:])

    @property
    def tss_28d(self):
        return sum(self._tss_hist)

    @property
    def acwr(self):
        a = self.tss_28d / 4
        return self.tss_7d / max(a, 1)

    def snapshot(self):
        return {
            'fitness': round(self.fitness, 2),
            'fatigue': round(self.fatigue, 2),
            'form': round(self.form, 2),
            'perf': round(self.perf, 3),
            'tss_7d': round(self.tss_7d, 1),
            'acwr': round(self.acwr, 2),
        }

    def clone(self):
        c = BanisterDisc(self.disc, self.k1, self.k2, self.tau_p, self.tau_n, self.p0)
        c.fitness, c.fatigue = self.fitness, self.fatigue
        c._tss_hist = list(self._tss_hist)
        return c


def calibrar_banister(fechas, tss, perf_f, perf_v, disc):
    """
    Calibra Banister minimizando error vs performance observada.
    Retorna (BanisterDisc, dict métricas).
    """
    from scipy.optimize import minimize as opt_min

    if len(perf_v) < 5:
        return BanisterDisc(disc), {'ok': False, 'n': len(perf_v)}

    n = len(tss)
    f2i = {f: i for i, f in enumerate(fechas)}
    pi, pv = [], []
    for f, v in zip(perf_f, perf_v):
        if f in f2i and math.isfinite(v):
            pi.append(f2i[f]); pv.append(v)
    if len(pv) < 5:
        return BanisterDisc(disc), {'ok': False, 'n': len(pv)}

    pi, pv = np.array(pi), np.array(pv)
    pm, ps = pv.mean(), max(pv.std(), 1e-6)
    pn = (pv - pm) / ps

    def _sim(x):
        k1, k2, tp, tn, p0 = x
        if tp < 10 or tn < 2 or k1 < 0 or k2 < 0 or tp <= tn:
            return np.full(len(pi), 99.0)
        dp, dn = math.exp(-1/tp), math.exp(-1/tn)
        fit = fat = 0.0
        out = []
        j = 0
        for d in range(n):
            fit = fit * dp + k1 * tss[d]
            fat = fat * dn + k2 * tss[d]
            if j < len(pi) and d == pi[j]:
                out.append(p0 + fit - fat)
                j += 1
        return np.array(out) if len(out) == len(pi) else np.full(len(pi), 99.0)

    def _loss(x):
        k1, k2, tp, tn, p0 = x
        base = float(np.mean((_sim(x) - pn) ** 2))
        # Penalizar si tau_pos <= tau_neg (fisiológicamente incorrecto)
        if tp <= tn:
            base += 10.0
        # Penalizar k1 muy chico (entrenamiento SÍ tiene efecto)
        if k1 < 0.005:
            base += (0.005 - k1) * 100
        return base

    best_l, best_x = 1e9, None
    bounds = [(0.005, 0.5), (0.005, 1.0), (20, 90), (2, 21), (-5, 5)]
    for x0 in [[.05,.10,42,7,0], [.03,.08,35,5,0], [.08,.15,50,10,0],
                [.04,.12,45,8,0], [.06,.09,38,6,0]]:
        try:
            r = opt_min(_loss, x0, method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': 500})
            if r.fun < best_l:
                best_l, best_x = r.fun, r.x
        except Exception:
            pass

    if best_x is None:
        return BanisterDisc(disc), {'ok': False, 'error': 'opt failed'}

    k1, k2, tp, tn, p0 = best_x
    pr = _sim(best_x)
    ss_r = np.sum((pn - pr) ** 2)
    ss_t = np.sum((pn - pn.mean()) ** 2)
    r2 = 1 - ss_r / max(ss_t, 1e-10)
    pr_real = pr * ps + pm
    mae = float(np.mean(np.abs(pv - pr_real)))

    bm = BanisterDisc(disc, k1, k2, tp, tn, p0 * ps + pm)
    return bm, {'ok': True, 'r2': round(r2, 4), 'mae': round(mae, 4), 'n': len(pv)}


# ═══════════════════════════════════════════════════════════════
#  2. MODELO DE READINESS
#     Predice: dado estado actual → qué nivel de carga tolera hoy
# ═══════════════════════════════════════════════════════════════

READINESS_FEATURES = [
    'hrv_rmssd', 'hrv_7d_avg', 'hrv_7d_cv', 'hrv_delta_pct',
    'sleep_h', 'sleep_7d_avg', 'stress_avg', 'stress_7d_avg',
    'recovery_score', 'body_battery',
    'tsb', 'ctl', 'atl', 'acwr',
    'tss_ayer', 'tss_2d', 'dias_desde_intensa',
]


class ReadinessModel:
    """
    Predice si el atleta puede hacer sesión intensa, normal, o reducida.
    Entrenado desde el historial real: los días que entrenó fuerte y le fue
    bien (buen cumplimiento, pace-HR ratio OK) vs los que no.
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.ok = False
        self.score = None

    def entrenar(self, X, y):
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import f1_score

        if len(X) < 20 or len(np.unique(y)) < 2:
            return {'ok': False, 'n': len(X)}

        self.scaler = StandardScaler()
        Xs = self.scaler.fit_transform(X)

        self.model = GradientBoostingClassifier(
            n_estimators=80, max_depth=3, learning_rate=0.05,
            min_samples_leaf=3, random_state=42)

        tscv = TimeSeriesSplit(n_splits=min(3, len(X) // 10))
        f1s = []
        for tr, te in tscv.split(Xs):
            if len(np.unique(y[tr])) < 2:
                continue
            self.model.fit(Xs[tr], y[tr])
            f1s.append(f1_score(y[te], self.model.predict(Xs[te]),
                               average='weighted', zero_division=0))

        self.model.fit(Xs, y)
        self.ok = True
        self.score = float(np.mean(f1s)) if f1s else 0
        return {'ok': True, 'f1_cv': round(self.score, 3), 'n': len(X)}

    def predecir(self, x_row):
        """Retorna nivel: 2=ALTO, 1=NORMAL, 0=REDUCIDO."""
        if not self.ok:
            return 1  # default NORMAL
        Xs = self.scaler.transform(x_row.reshape(1, -1))
        return int(self.model.predict(Xs)[0])

    def predecir_proba(self, x_row):
        if not self.ok:
            return [0.33, 0.34, 0.33]
        Xs = self.scaler.transform(x_row.reshape(1, -1))
        return self.model.predict_proba(Xs)[0].tolist()


# ═══════════════════════════════════════════════════════════════
#  3. MODELO DE RESPUESTA
#     Predice: dado estado + sesión → cómo se despierta mañana
# ═══════════════════════════════════════════════════════════════

RESPONSE_FEATURES = [
    # Estado pre-sesión
    'hrv_pre', 'sleep_pre', 'stress_pre', 'recovery_pre',
    'fitness_run', 'fitness_bike', 'fitness_swim',
    'fatigue_run', 'fatigue_bike', 'fatigue_swim',
    'tsb',
    # Sesión realizada
    'tss_sesion', 'duration_min', 'hr_avg_pct_lthr',
    'sport_run', 'sport_bike', 'sport_swim',  # one-hot
    'intensidad',  # 0=recovery, 1=endurance, 2=threshold, 3=vo2max
]

RESPONSE_TARGETS = ['hrv_post', 'recovery_post', 'fatigue_delta']


class ResponseModel:
    """
    Predice estado del atleta al día siguiente dado lo que hizo hoy.
    Permite encadenar: simular una semana completa día a día.
    """

    def __init__(self):
        self.models = {}  # un modelo por target
        self.scaler_X = None
        self.scalers_y = {}
        self.ok = False
        self.scores = {}

    def entrenar(self, X, Y_dict):
        """
        X: matrix features
        Y_dict: {'hrv_post': array, 'recovery_post': array, 'fatigue_delta': array}
        """
        from sklearn.neural_network import MLPRegressor
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import TimeSeriesSplit

        if len(X) < 20:
            return {'ok': False, 'n': len(X)}

        self.scaler_X = StandardScaler()
        Xs = self.scaler_X.fit_transform(X)
        results = {}

        for target_name, y in Y_dict.items():
            mask = np.isfinite(y)
            if mask.sum() < 15:
                continue

            Xm, ym = Xs[mask], y[mask]
            sc_y = StandardScaler()
            ys = sc_y.fit_transform(ym.reshape(-1, 1)).ravel()
            self.scalers_y[target_name] = sc_y

            model = MLPRegressor(
                hidden_layer_sizes=(32, 16), activation='relu',
                solver='adam', alpha=0.01, max_iter=400,
                early_stopping=True, validation_fraction=0.15,
                n_iter_no_change=15, random_state=42)

            tscv = TimeSeriesSplit(n_splits=min(3, len(Xm) // 8))
            r2s = []
            for tr, te in tscv.split(Xm):
                model.fit(Xm[tr], ys[tr])
                pred = model.predict(Xm[te])
                # Proteger contra predicciones divergentes
                if not np.all(np.isfinite(pred)):
                    continue
                ss_r = np.sum((ys[te] - pred)**2)
                ss_t = np.sum((ys[te] - ys[te].mean())**2)
                r2 = 1 - ss_r / max(ss_t, 1e-10)
                # Clamp R² para evitar valores absurdos
                r2 = max(r2, -1.0)
                r2s.append(r2)

            model.fit(Xm, ys)
            r2_cv = float(np.mean(r2s)) if r2s else 0
            self.scores[target_name] = round(r2_cv, 3)
            results[target_name] = {'r2_cv': round(r2_cv, 3), 'n': int(mask.sum())}
            # Solo guardar modelo si R² > 0 (mejor que predecir la media)
            if r2_cv > 0.0:
                self.models[target_name] = model

        self.ok = len(self.models) > 0
        return {'ok': self.ok, 'targets': results}

    def predecir(self, x_row):
        """Predice estado mañana. Retorna dict."""
        if not self.ok:
            return {}
        Xs = self.scaler_X.transform(x_row.reshape(1, -1))
        out = {}
        for name, model in self.models.items():
            ys = model.predict(Xs)
            y = self.scalers_y[name].inverse_transform(ys.reshape(-1, 1)).ravel()
            out[name] = float(y[0])
        return out


# ═══════════════════════════════════════════════════════════════
#  4. DIGITAL TWIN COMPLETO
# ═══════════════════════════════════════════════════════════════

class DigitalTwin:
    """
    Réplica fisiológica virtual del atleta.
    Calibra modelos per-disciplina, predice readiness y respuesta,
    genera y evalúa 100+ escenarios de semana con sesiones reales.
    """

    def __init__(self, conn, atleta_id: int):
        self.conn = conn
        self.atleta_id = atleta_id
        self.perfil = {}
        self.banister: Dict[str, BanisterDisc] = {}
        self.readiness = ReadinessModel()
        self.response = ResponseModel()
        self.calibrado = False
        self.metricas = {}
        self._ses = None
        self._bio = None
        self._estado = {}

    # ──────────────────────────────────────────────────────────
    #  CARGAR DATOS
    # ──────────────────────────────────────────────────────────

    def _cargar(self):
        df_p = _sql('SELECT * FROM atletas WHERE id=%s', self.conn, [self.atleta_id])
        if not df_p.empty:
            self.perfil = df_p.iloc[0].to_dict()

        self._ses = _sql('''
            SELECT id, fecha, sport, duration_min, distance_km,
                   hr_avg, hr_max, pace, np_watts, cadence,
                   tss_total, tss_z12, tss_z34, tss_z56,
                   ctl, atl, tsb, cumplimiento_pct,
                   session_type, tipo_sesion
            FROM sesiones
            WHERE atleta_id=%s AND tss_total > 0
              AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada'))
            ORDER BY fecha
        ''', self.conn, [self.atleta_id])

        if not self._ses.empty:
            self._ses['fecha'] = pd.to_datetime(self._ses['fecha'])
            for c in ['duration_min','distance_km','hr_avg','pace','np_watts',
                      'tss_total','tss_z12','tss_z34','tss_z56','ctl','atl','tsb',
                      'cumplimiento_pct','cadence']:
                if c in self._ses.columns:
                    self._ses[c] = pd.to_numeric(self._ses[c], errors='coerce')

        self._bio = _sql('''
            SELECT fecha, hrv_rmssd, sleep_h, stress_avg,
                   hanna_vfc, recovery_score, body_battery, deep_h, rem_h
            FROM sleep_hrv WHERE atleta_id=%s ORDER BY fecha
        ''', self.conn, [self.atleta_id])

        if not self._bio.empty:
            self._bio['fecha'] = pd.to_datetime(self._bio['fecha'])
            for c in ['hrv_rmssd','sleep_h','stress_avg','hanna_vfc',
                      'recovery_score','body_battery','deep_h','rem_h']:
                if c in self._bio.columns:
                    self._bio[c] = pd.to_numeric(self._bio[c], errors='coerce')

    # ──────────────────────────────────────────────────────────
    #  CALIBRAR TODO
    # ──────────────────────────────────────────────────────────

    def calibrar(self, verbose=True) -> dict:
        self._cargar()
        if self._ses is None or self._ses.empty:
            return {'ok': False, 'error': 'Sin sesiones'}

        nombre = self.perfil.get('nombre', f'ID {self.atleta_id}')
        n_total = len(self._ses)
        por_d = self._ses.groupby('sport').size().to_dict()

        if verbose:
            n_bio = len(self._bio) if self._bio is not None else 0
            print(f'\n{"="*65}')
            print(f'  DIGITAL TWIN — {nombre}')
            print(f'  {n_total} sesiones: {por_d}  |  {n_bio} días bio')
            print(f'{"="*65}')

        res = {}

        # ── 1. Banister per disciplina ──
        for disc in DISCIPLINAS:
            df_d = self._ses[self._ses['sport'] == disc]
            if df_d.empty:
                continue

            fechas_all, tss_all = self._tss_diario(disc)
            perf_f, perf_v = self._perf_obs(disc)

            bm, met = calibrar_banister(fechas_all, tss_all, perf_f, perf_v, disc)
            self.banister[disc] = bm

            # Correr Banister con datos reales para dejar estado actual
            bm_run = bm.clone()
            bm_run.fitness = bm_run.fatigue = 0
            bm_run._tss_hist = []
            for t in tss_all:
                bm_run.step(t)
            self.banister[disc] = bm_run
            self._estado[disc] = bm_run.snapshot()

            res[disc] = met
            if verbose:
                if met.get('ok'):
                    print(f'  [{disc:>8s}] Banister R²={met["r2"]:.3f}  '
                          f'MAE={met["mae"]:.3f}  (n={met["n"]})  '
                          f'k1={bm.k1:.3f} k2={bm.k2:.3f} τ+={bm.tau_p:.0f} τ-={bm.tau_n:.0f}')
                    print(f'  {"":>10s} Estado: fitness={bm_run.fitness:.1f}  '
                          f'fatigue={bm_run.fatigue:.1f}  form={bm_run.form:+.1f}')
                else:
                    print(f'  [{disc:>8s}] Banister: {met}')

        # ── 2. Readiness model ──
        X_read, y_read = self._build_readiness_data()
        if len(X_read) >= 20:
            res_read = self.readiness.entrenar(X_read, y_read)
            res['readiness'] = res_read
            if verbose:
                print(f'  [readiness] {res_read}')
        elif verbose:
            print(f'  [readiness] Datos insuficientes ({len(X_read)})')

        # ── 3. Response model ──
        X_resp, Y_resp = self._build_response_data()
        if len(X_resp) >= 20:
            res_resp = self.response.entrenar(X_resp, Y_resp)
            res['response'] = res_resp
            if verbose:
                print(f'  [response]  {res_resp}')
        elif verbose:
            print(f'  [response]  Datos insuficientes ({len(X_resp)})')

        self.calibrado = len(self.banister) > 0
        self.metricas = res

        if verbose:
            print(f'\n  TWIN {"CALIBRADO ✓" if self.calibrado else "✗"}')
            print(f'{"="*65}')

        return {'ok': self.calibrado, 'metricas': res}

    def _tss_diario(self, disc):
        df = self._ses[self._ses['sport'] == disc]
        if df.empty:
            return np.array([]), np.array([])
        rng = pd.date_range(df['fecha'].min(), df['fecha'].max(), freq='D')
        tss_d = df.groupby('fecha')['tss_total'].sum()
        return rng.values, np.array([_sf(tss_d.get(f, 0)) for f in rng])

    def _perf_obs(self, disc):
        """
        Métrica de rendimiento por disciplina.
        En vez de pace crudo (ruidoso), usa EFICIENCIA CARDÍACA:
          - Running/Swimming: speed_kmh / hr_avg → más alto = mejor
          - Cycling: np_watts / hr_avg → más alto = mejor (potencia/latido)
        Esto normaliza: un easy run y un interval tienen eficiencias comparables.
        """
        df = self._ses[self._ses['sport'] == disc].copy()
        df = df[df['hr_avg'].notna() & (df['hr_avg'] > 80)]

        if disc == 'cycling':
            df = df[df['np_watts'].notna() & (df['np_watts'] > 50)]
            if len(df) < 10:
                return np.array([]), np.array([])
            # Eficiencia = watts por latido (mayor = mejor)
            df['eficiencia'] = df['np_watts'] / df['hr_avg']
        elif disc == 'running':
            df = df[df['pace'].between(3.0, 10.0) & df['distance_km'].notna() & (df['distance_km'] > 0.5)]
            if len(df) < 10:
                return np.array([]), np.array([])
            # speed_kmh = 60 / pace (min/km)
            df['speed'] = 60.0 / df['pace']
            # Eficiencia = km/h por latido (mayor = mejor)
            df['eficiencia'] = df['speed'] / df['hr_avg']
        else:  # swimming
            df = df[df['pace'].between(1.0, 4.0)]
            if len(df) < 10:
                return np.array([]), np.array([])
            df['speed'] = 60.0 / df['pace']  # en este caso es 100m/min conceptual
            df['eficiencia'] = df['speed'] / df['hr_avg']

        # Suavizar: rolling 7 sesiones para reducir ruido
        df = df.sort_values('fecha')
        df['eficiencia_smooth'] = df['eficiencia'].rolling(7, min_periods=3, center=True).mean()
        df = df[df['eficiencia_smooth'].notna()]

        if len(df) < 10:
            return np.array([]), np.array([])

        g = df.groupby('fecha')['eficiencia_smooth'].mean().reset_index()
        return g['fecha'].values, g['eficiencia_smooth'].values

    # ──────────────────────────────────────────────────────────
    #  BUILD READINESS TRAINING DATA
    #  Para cada sesión real: bio pre-sesión → fue sesión intensa exitosa?
    # ──────────────────────────────────────────────────────────

    def _build_readiness_data(self):
        if self._bio is None or self._bio.empty:
            return np.array([]).reshape(0, len(READINESS_FEATURES)), np.array([])

        bio_idx = self._bio.set_index('fecha')
        ses = self._ses.copy()
        X_list, y_list = [], []

        for i, row in ses.iterrows():
            fecha = row['fecha']
            tss = _sf(row['tss_total'])
            hr_avg = _sf(row['hr_avg'])
            cumpl = _sf(row.get('cumplimiento_pct'), 80)
            lthr = _sf(self.perfil.get('lthr_run', 162), 162)

            # Bio del día
            bio_hoy = self._get_bio(bio_idx, fecha)
            if bio_hoy is None:
                continue

            # Bio 7 días
            bio_7d = self._get_bio_7d(bio_idx, fecha)

            # Carga reciente
            mask_prev = ses['fecha'] < fecha
            prev_2d = ses[mask_prev].tail(2)
            tss_ayer = _sf(prev_2d.iloc[-1]['tss_total']) if len(prev_2d) >= 1 else 0
            tss_2d = _sf(prev_2d.iloc[-2]['tss_total']) if len(prev_2d) >= 2 else 0

            # Días desde última sesión intensa (TSS > p75)
            p75 = ses['tss_total'].quantile(0.75)
            prev_intensa = ses[(ses['fecha'] < fecha) & (ses['tss_total'] > p75)]
            dias_intensa = (fecha - prev_intensa['fecha'].max()).days if not prev_intensa.empty else 7

            # Armar features
            x = np.array([
                bio_hoy.get('hrv_rmssd', 55),
                bio_7d.get('hrv_avg', 55),
                bio_7d.get('hrv_cv', 0.08),
                bio_hoy.get('hrv_delta_pct', 0),
                bio_hoy.get('sleep_h', 7),
                bio_7d.get('sleep_avg', 7),
                bio_hoy.get('stress_avg', 30),
                bio_7d.get('stress_avg', 30),
                bio_hoy.get('recovery_score', 50),
                bio_hoy.get('body_battery', 50),
                _sf(row.get('tsb'), 0),
                _sf(row.get('ctl'), 30),
                _sf(row.get('atl'), 30),
                self._acwr_at(fecha),
                tss_ayer,
                tss_2d,
                min(dias_intensa, 14),
            ])

            # Target: clasificar la sesión
            # Determinar si fue intensa (TSS/hr alto, HR > 85% LTHR)
            dur_h = _sf(row['duration_min']) / 60
            tss_per_h = tss / max(dur_h, 0.1)
            hr_pct = hr_avg / max(lthr, 100)

            # 2=ALTO (calidad, >80 TSS/h o HR>90% LTHR y buen cumplimiento)
            # 1=NORMAL (endurance, 40-80 TSS/h)
            # 0=REDUCIDO (recovery, <40 TSS/h)
            if tss_per_h > 80 or hr_pct > 0.90:
                label = 2 if cumpl >= 70 else 0  # si no completó, era demasiado
            elif tss_per_h > 40:
                label = 1
            else:
                label = 0

            X_list.append(x)
            y_list.append(label)

        return np.array(X_list), np.array(y_list)

    # ──────────────────────────────────────────────────────────
    #  BUILD RESPONSE TRAINING DATA
    #  Para cada par de días consecutivos: estado + sesión → estado mañana
    # ──────────────────────────────────────────────────────────

    def _build_response_data(self):
        if self._bio is None or self._bio.empty:
            return np.array([]).reshape(0, len(RESPONSE_FEATURES)), {}

        bio_idx = self._bio.set_index('fecha')
        ses = self._ses.sort_values('fecha').reset_index(drop=True)
        lthr = _sf(self.perfil.get('lthr_run', 162), 162)

        X_list = []
        Y_hrv, Y_rec, Y_fat = [], [], []

        for i in range(len(ses) - 1):
            row = ses.iloc[i]
            nxt = ses.iloc[i + 1]
            fecha = row['fecha']
            fecha_nxt = nxt['fecha']

            # Solo pares de días cercanos (≤3 días)
            gap = (fecha_nxt - fecha).days
            if gap > 3 or gap < 1:
                continue

            bio_pre = self._get_bio(bio_idx, fecha)
            bio_post = self._get_bio(bio_idx, fecha_nxt)
            if bio_pre is None or bio_post is None:
                continue

            # State features
            sport = row.get('sport', 'running')
            x = np.array([
                bio_pre.get('hrv_rmssd', 55),
                bio_pre.get('sleep_h', 7),
                bio_pre.get('stress_avg', 30),
                bio_pre.get('recovery_score', 50),
                self._fitness_at(fecha, 'running'),
                self._fitness_at(fecha, 'cycling'),
                self._fitness_at(fecha, 'swimming'),
                self._fatigue_at(fecha, 'running'),
                self._fatigue_at(fecha, 'cycling'),
                self._fatigue_at(fecha, 'swimming'),
                _sf(row.get('tsb'), 0),
                # Session
                _sf(row['tss_total']),
                _sf(row['duration_min']),
                _sf(row['hr_avg']) / max(lthr, 100),
                1 if sport == 'running' else 0,
                1 if sport == 'cycling' else 0,
                1 if sport == 'swimming' else 0,
                self._intensidad_sesion(row),
            ])

            X_list.append(x)
            Y_hrv.append(bio_post.get('hrv_rmssd', 55))
            Y_rec.append(bio_post.get('recovery_score', 50))
            # Fatigue delta approximation from TSB change
            tsb_pre = _sf(row.get('tsb'), 0)
            tsb_post = _sf(nxt.get('tsb'), 0)
            Y_fat.append(tsb_post - tsb_pre)

        X = np.array(X_list) if X_list else np.array([]).reshape(0, len(RESPONSE_FEATURES))
        return X, {
            'hrv_post': np.array(Y_hrv),
            'recovery_post': np.array(Y_rec),
            'fatigue_delta': np.array(Y_fat),
        }

    # ──────────────────────────────────────────────────────────
    #  SIMULAR UNA SEMANA COMPLETA
    # ──────────────────────────────────────────────────────────

    def simular_semana(self, plan_diario: List[dict]) -> dict:
        """
        Simula una semana día a día.

        plan_diario: lista de 7 dicts, uno por día:
          {
            'sport': 'running',
            'tipo': 'ftp_intervals',     # tipo de sesión
            'tss': 75,
            'duration_min': 55,
            'intensidad': 2,             # 0=recup, 1=endurance, 2=threshold, 3=vo2
            'descripcion': '6x800m a 3:55/km con 2\' pausa',
            'bloques': [...],            # opcional: detalle de la sesión
          }
          o {'descanso': True} para día libre

        Retorna: estado predicho día a día + performance al final
        """
        # Clonar Banister actual
        banisters = {d: bm.clone() for d, bm in self.banister.items()}

        # Estado bio actual (último disponible)
        estado_bio = self._estado_bio_actual()

        dias = []
        perf_acum = {d: 0 for d in DISCIPLINAS}

        for dia_idx, sesion in enumerate(plan_diario):
            if sesion.get('descanso'):
                # Día libre: Banister decae, bio se recupera
                for d, bm in banisters.items():
                    bm.step(0)
                estado_bio['hrv_rmssd'] *= 1.02  # recovery boost
                estado_bio['recovery_score'] = min(100, estado_bio.get('recovery_score', 50) + 5)
                dias.append({
                    'dia': dia_idx + 1,
                    'sesion': {'descanso': True},
                    'readiness': 'DESCANSO',
                    'estado_post': deepcopy(estado_bio),
                    'banister': {d: bm.snapshot() for d, bm in banisters.items()},
                })
                continue

            sport = sesion.get('sport', 'running')
            tss = sesion.get('tss', 50)
            intensidad = sesion.get('intensidad', 1)

            # Readiness predicha
            readiness_nivel = self._predecir_readiness(estado_bio, banisters)

            # Aplicar sesión al Banister
            if sport in banisters:
                banisters[sport].step(tss)
            for other in DISCIPLINAS:
                if other != sport and other in banisters:
                    banisters[other].step(0)

            # Predecir respuesta
            resp = self._predecir_respuesta(estado_bio, banisters, sesion)
            estado_bio = self._actualizar_bio(estado_bio, resp, tss, intensidad)

            # Performance acumulada
            if sport in banisters:
                perf_acum[sport] = banisters[sport].perf

            dias.append({
                'dia': dia_idx + 1,
                'sesion': {k: v for k, v in sesion.items() if k != 'bloques'},
                'readiness': ['REDUCIDO', 'NORMAL', 'ALTO'][min(readiness_nivel, 2)],
                'estado_post': deepcopy(estado_bio),
                'banister': {d: bm.snapshot() for d, bm in banisters.items()},
            })

        # Score final: práctico, no depende de Banister (que puede tener R² bajo)
        # Evaluar la calidad de la semana basada en principios fisiológicos
        score = 0
        sesiones_activas = [s for s in plan_diario if not s.get('descanso')]
        n_activas = len(sesiones_activas)
        tss_plan = sum(s.get('tss', 0) for s in sesiones_activas)

        # Calcular ACWR real contra historial
        tss_4sem_avg = 0
        if self._ses is not None and not self._ses.empty:
            fecha_max = self._ses['fecha'].max()
            ult_28 = self._ses[self._ses['fecha'] >= fecha_max - timedelta(days=28)]
            tss_4sem_avg = float(ult_28['tss_total'].sum()) / 4

        # 1. Distribución de intensidad (Seiler: 80/20 es óptimo)
        ints = [s.get('intensidad', 1) for s in sesiones_activas]
        n_easy = sum(1 for i in ints if i <= 1)     # recovery + endurance
        n_hard = sum(1 for i in ints if i >= 2)     # threshold + vo2
        ratio_hard = n_hard / max(n_activas, 1)
        # Óptimo: 25-35% de sesiones son duras
        if 0.20 <= ratio_hard <= 0.40:
            score += 15
        elif 0.15 <= ratio_hard <= 0.50:
            score += 8
        else:
            score -= 5

        # 2. Variedad de estímulos (no repetir el mismo tipo)
        tipos = [s.get('tipo', '') for s in sesiones_activas]
        variedad = len(set(tipos)) / max(len(tipos), 1)
        score += variedad * 20

        # 3. Alternancia hard/easy (no dos sesiones duras seguidas)
        penalidad_consecutivas = 0
        for i in range(len(ints) - 1):
            if ints[i] >= 2 and ints[i + 1] >= 2:
                penalidad_consecutivas += 5
        score -= penalidad_consecutivas

        # 4. Cobertura de disciplinas
        sports_in_plan = set(s.get('sport') for s in sesiones_activas)
        score += len(sports_in_plan) * 5

        # 5. TSS en rango apropiado (vs historial)
        if tss_4sem_avg > 0:
            tss_ratio = tss_plan / tss_4sem_avg
            if 0.85 <= tss_ratio <= 1.10:
                score += 10  # mantener/crecer suavemente
            elif 0.70 <= tss_ratio <= 1.20:
                score += 5
            else:
                score -= 5

        # 6. Día de descanso incluido
        tiene_descanso = any(s.get('descanso') for s in plan_diario)
        if tiene_descanso:
            score += 5

        # 7. Long session en finde
        if len(plan_diario) >= 7:
            for dia_idx in [5, 6]:  # sáb, dom
                s = plan_diario[dia_idx]
                if not s.get('descanso') and 'long' in s.get('tipo', '').lower():
                    score += 3

        # 8. Readiness: si el modelo funciona, penalizar sesiones duras
        #    cuando readiness predice que no puede
        if self.readiness.ok:
            readiness_nivel = self._predecir_readiness(self._estado_bio_actual(),
                                                        {d: bm.clone() for d, bm in self.banister.items()})
            if readiness_nivel == 0 and n_hard > 1:
                score -= 15  # readiness baja pero muchas sesiones duras

        # Riesgo: basado en TSS semanal vs historial real (no ACWR del clone)
        tss_sem_plan = tss_plan
        # ACWR real: TSS esta semana / promedio 4 semanas previas reales

        if tss_4sem_avg < 10:
            # Sin historial suficiente, asumir riesgo moderado
            acwr_real = 1.0
        else:
            acwr_real = tss_sem_plan / tss_4sem_avg

        # Riesgo basado en ACWR (Gabbett): sweet spot 0.8-1.3, danger >1.5
        if acwr_real <= 1.3:
            riesgo = max(0, (acwr_real - 0.8) * 0.2)   # 0-10%
        elif acwr_real <= 1.5:
            riesgo = 0.10 + (acwr_real - 1.3) * 1.5     # 10-40%
        else:
            riesgo = min(1.0, 0.40 + (acwr_real - 1.5) * 1.2)  # 40-100%

        # Debug (remover después)
        if not hasattr(self, '_debug_risk_printed'):
            print(f'\n  [RIESGO] TSS plan={tss_plan:.0f} vs prom 4sem={tss_4sem_avg:.0f} '
                  f'→ ACWR={acwr_real:.2f} → riesgo={riesgo*100:.0f}%')
            self._debug_risk_printed = True

        # Penalizar monotonía alta (todas las sesiones similares)
        intensidades = [s.get('intensidad', 1) for s in plan_diario if not s.get('descanso')]
        if len(intensidades) >= 3 and len(set(intensidades)) <= 1:
            riesgo = min(1.0, riesgo + 0.15)

        return {
            'dias': dias,
            'score': round(score, 4),
            'riesgo': round(riesgo, 3),
            'perf_final': {d: bm.snapshot() for d, bm in banisters.items()},
        }

    # ──────────────────────────────────────────────────────────
    #  GENERAR + EVALUAR 100 ESCENARIOS
    # ──────────────────────────────────────────────────────────

    def generar_escenarios(self, tss_semanal: float = None,
                            semana_tipo: str = 'carga',
                            n_escenarios: int = 100) -> dict:
        """
        Genera N escenarios de semana completa con sesiones reales,
        los simula día a día, y devuelve los top 5.

        Cada escenario es una semana de 7 días con sesiones concretas:
        "Lunes: 6x800m running a 3:55 con 2' pausa"
        "Martes: 1h30 bike endurance"
        etc.
        """
        if not self.calibrado:
            return {'ok': False, 'error': 'Twin no calibrado'}

        if tss_semanal is None:
            if self._ses is not None and not self._ses.empty:
                # Usar últimos 28 DÍAS calendario (misma ventana que el riesgo)
                fecha_max = self._ses['fecha'].max()
                ult_28d = self._ses[self._ses['fecha'] >= fecha_max - timedelta(days=28)]
                tss_semanal = float(ult_28d['tss_total'].sum()) / 4
                # Si el atleta estuvo inactivo, no saltar a carga histórica alta
                # Máximo ACWR 1.3 sobre lo actual
                tss_semanal = round(tss_semanal * 1.15)  # crecer suavemente
                if tss_semanal < 100:
                    tss_semanal = 150  # mínimo razonable
            else:
                tss_semanal = 300

        # Parámetros del atleta
        lthr = _sf(self.perfil.get('lthr_run', 162), 162)
        ftp = self.perfil.get('ftp_watts')
        pace_umbral = _sf(self.perfil.get('pace_umbral_run', 5.5), 5.5)
        pace_z2 = round(pace_umbral * 1.15, 2)
        css = round(_sf(self.perfil.get('css_100m', 1.75), 1.75), 2)

        # Templates de sesión por disciplina + intensidad
        templates = self._session_templates(tss_semanal, lthr, ftp, pace_z2, css)

        # Estructura semanal triatlón con DOBLES TURNOS:
        # LUN: swim          MAR: bike          MIÉ: swim AM + run PM
        # JUE: bike          VIE: swim AM + run PM
        # SÁB: bike long     DOM: run long
        # = 3 swim + 3 bike + 3 run = 9 sesiones en 7 días

        import random
        # Seed basado en atleta + fecha para reproducibilidad diaria
        # pero variación entre días
        from datetime import date
        random.seed(hash((self.atleta_id, str(date.today()))))

        all_scenarios = []

        for esc_i in range(n_escenarios):
            # Variaciones de TSS total
            tss_factor = 0.80 + random.random() * 0.40
            tss_esc = tss_semanal * tss_factor
            if semana_tipo == 'descarga':
                tss_esc *= 0.60

            # Distribución TSS por disciplina (varía cada escenario)
            pct_swim = 0.08 + random.random() * 0.08   # 8-16%
            pct_bike = 0.38 + random.random() * 0.14   # 38-52%
            pct_run  = 1.0 - pct_swim - pct_bike

            tss_swim = tss_esc * pct_swim
            tss_bike = tss_esc * pct_bike
            tss_run  = tss_esc * pct_run

            def pick(sport, tipo, tss_target):
                opciones = templates.get(sport, {}).get(tipo, [])
                if not opciones:
                    opciones = templates.get(sport, {}).get('endurance', [])
                if not opciones:
                    return None
                s = random.choice(opciones).copy()
                tss_template = s.get('tss', 50)
                intensidad = s.get('intensidad', 1)

                # Recovery (0) y Endurance (1): NUNCA inflar por encima del template
                # Quality (2) y VO2 (3): pueden subir hasta 1.3x del template
                if intensidad <= 0:
                    tss_final = min(tss_target, tss_template)  # cap al template
                elif intensidad <= 1:
                    tss_final = min(tss_target, tss_template * 1.15)  # max +15%
                else:
                    tss_final = min(tss_target, tss_template * 1.30)  # max +30%

                tss_final = max(10, round(tss_final))
                if tss_template > 0:
                    factor = tss_final / tss_template
                    s['tss'] = tss_final
                    if 'duration_min' in s:
                        s['duration_min'] = max(15, round(s['duration_min'] * factor))
                return s

            # Tipos variados por escenario
            swim_tipos = random.sample(['quality', 'endurance', 'endurance'], 3)
            run_tipos  = random.sample(['quality', 'quality', 'long'], 3)
            bike_tipos = random.sample(['quality', 'endurance', 'long'], 3)

            # Armar 7 días con dobles turnos
            plan_dias = [[] for _ in range(7)]

            # LUN: swim
            s = pick('swimming', swim_tipos[0], tss_swim * 0.30)
            if s: plan_dias[0].append(s)

            # MAR: bike
            s = pick('cycling', bike_tipos[0], tss_bike * 0.30)
            if s: plan_dias[1].append(s)

            # MIÉ: swim AM + run PM (doble turno)
            s = pick('swimming', swim_tipos[1], tss_swim * 0.35)
            if s: plan_dias[2].append(s)
            s = pick('running', run_tipos[0], tss_run * 0.30)
            if s: plan_dias[2].append(s)

            # JUE: bike
            s = pick('cycling', bike_tipos[1], tss_bike * 0.25)
            if s: plan_dias[3].append(s)

            # VIE: swim AM + run PM (doble turno)
            s = pick('swimming', swim_tipos[2], tss_swim * 0.35)
            if s: plan_dias[4].append(s)
            s = pick('running', run_tipos[1], tss_run * 0.30)
            if s: plan_dias[4].append(s)

            # SÁB: bike long
            s = pick('cycling', bike_tipos[2], tss_bike * 0.45)
            if s: plan_dias[5].append(s)

            # DOM: run long
            s = pick('running', 'long', tss_run * 0.40)
            if s: plan_dias[6].append(s)

            # Convertir a plan_7
            plan_7 = []
            for d_sesiones in plan_dias:
                if len(d_sesiones) == 0:
                    plan_7.append({'descanso': True})
                elif len(d_sesiones) == 1:
                    plan_7.append(d_sesiones[0])
                else:
                    dia = d_sesiones[0].copy()
                    dia['sesion_2'] = d_sesiones[1]
                    plan_7.append(dia)

            # TSS total incluyendo dobles
            tss_total_plan = 0
            for s in plan_7:
                if not s.get('descanso'):
                    tss_total_plan += s.get('tss', 0)
                    if 'sesion_2' in s:
                        tss_total_plan += s['sesion_2'].get('tss', 0)

            # Simular la semana
            resultado = self.simular_semana(plan_7)
            resultado['plan'] = plan_7
            resultado['tss_total'] = tss_total_plan
            resultado['escenario_id'] = esc_i + 1
            all_scenarios.append(resultado)

        # Ranking compuesto:
        # - performance score (positivo = mejora)
        # - penalización por riesgo
        # - bonus por variedad de estímulo (mezcla intensidades)
        # - bonus por día descanso cuando riesgo alto
        for s in all_scenarios:
            perf = s['score']
            risk = s['riesgo']
            # Variedad de estímulos
            ints = [d.get('sesion', {}).get('intensidad', -1) for d in s.get('dias', [])
                    if not d.get('sesion', {}).get('descanso')]
            variedad = len(set(i for i in ints if i >= 0)) / max(len(ints), 1)
            # Descanso apropiado
            tiene_descanso = any(d.get('sesion', {}).get('descanso') for d in s.get('dias', []))
            bonus_descanso = 0.05 if tiene_descanso else 0

            # Cobertura de 3 disciplinas
            sports_plan = set()
            for d in s.get('dias', []):
                sp = d.get('sesion', {}).get('sport')
                if sp:
                    sports_plan.add(sp)
            bonus_3disc = 10 if len(sports_plan) >= 3 else (3 if len(sports_plan) >= 2 else -5)
            bonus_descanso = 0.05 if tiene_descanso else 0

            s['ranking'] = round(
                perf * 100           # amplificar diferencias de performance
                - risk * 50          # penalizar riesgo
                + variedad * 10      # premiar variedad
                + bonus_descanso * 10  # premiar recuperación
                + bonus_3disc          # premiar cobertura 3 disciplinas
            , 4)

        all_scenarios.sort(key=lambda x: x['ranking'], reverse=True)
        top = all_scenarios[:5]

        return {
            'ok': True,
            'atleta': self.perfil.get('nombre', ''),
            'tss_ref': round(tss_semanal),
            'n_evaluados': len(all_scenarios),
            'mejores': [{
                'id': s['escenario_id'],
                'ranking': round(s['ranking'], 4),
                'score': s['score'],
                'riesgo': s['riesgo'],
                'tss_total': s['tss_total'],
                'plan': self._format_plan(s['plan']),
                'dias': s['dias'],
                'perf_final': s['perf_final'],
            } for s in top],
        }

    def _session_templates(self, tss_sem, lthr, ftp, pace_z2, css):
        """
        Templates de sesiones reales por disciplina y tipo.
        Se adaptan al nivel de carga del atleta:
          - tss_sem < 200: sesiones cortas, volumen bajo (vuelta al entreno)
          - tss_sem 200-400: sesiones normales
          - tss_sem > 400: sesiones completas de alto volumen
        """
        pace_ftp = round(pace_z2 * 0.87, 2)
        pace_vo2 = round(pace_z2 * 0.80, 2)
        pace_z1 = round(pace_z2 * 1.10, 2)

        pf = _pace(pace_ftp)
        pv = _pace(pace_vo2)
        p1 = _pace(pace_z1)
        p2 = _pace(pace_z2)

        ftp_w = int(_sf(ftp, 180))
        ss_w = round(ftp_w * 0.88)
        vo2_w = round(ftp_w * 1.15)
        z2_w = round(ftp_w * 0.65)

        css_z2 = round(css * 1.15, 2)
        css_ftp = round(css * 0.97, 2)
        cs2 = _pace(css_z2)
        csf = _pace(css_ftp)
        cs9 = _pace(round(css * 0.90, 2))

        # Tier: low (<200), mid (200-400), high (>400)
        if tss_sem < 200:
            # ── VUELTA AL ENTRENO: sesiones cortas ──
            t = {
                'running': {
                    'quality': [
                        {'sport': 'running', 'tipo': 'Tempo corto', 'tss': 35,
                         'duration_min': 30, 'intensidad': 2,
                         'descripcion': f'10\' cal Z1 + 12\' a {pf}/km + 8\' enfr'},
                        {'sport': 'running', 'tipo': 'Intervalos cortos', 'tss': 40,
                         'duration_min': 35, 'intensidad': 2,
                         'descripcion': f'10\' cal + 3x800m a {pf}/km c/2\' pausa + 8\' enfr'},
                        {'sport': 'running', 'tipo': 'Progresivo corto', 'tss': 35,
                         'duration_min': 30, 'intensidad': 2,
                         'descripcion': f'10\' Z1 a {p1}/km + 10\' Z2 a {p2}/km + 8\' Z3 a {pf}/km'},
                    ],
                    'endurance': [
                        {'sport': 'running', 'tipo': 'Easy run corto', 'tss': 25,
                         'duration_min': 30, 'intensidad': 1,
                         'descripcion': f'30\' continuo a {p2}/km, FC < {round(lthr*0.80)}'},
                        {'sport': 'running', 'tipo': 'Recovery jog', 'tss': 15,
                         'duration_min': 20, 'intensidad': 0,
                         'descripcion': f'20\' suave a {p1}/km'},
                    ],
                    'long': [
                        {'sport': 'running', 'tipo': 'Fondo medio', 'tss': 45,
                         'duration_min': 40, 'intensidad': 1,
                         'descripcion': f'40\' a {p2}/km'},
                        {'sport': 'running', 'tipo': 'Fondo progresivo', 'tss': 50,
                         'duration_min': 45, 'intensidad': 1,
                         'descripcion': f'30\' a {p2}/km + 15\' bajando a {_pace(round(pace_z2*0.95,2))}/km'},
                    ],
                },
                'cycling': {
                    'quality': [
                        {'sport': 'cycling', 'tipo': 'Sweet spot corto', 'tss': 40,
                         'duration_min': 40, 'intensidad': 2,
                         'descripcion': f'10\' cal + 2x10\' a {ss_w}w c/4\' + 8\' enfr'},
                        {'sport': 'cycling', 'tipo': 'Tempo bike', 'tss': 35,
                         'duration_min': 35, 'intensidad': 2,
                         'descripcion': f'10\' cal + 15\' a {ss_w}w + 10\' enfr'},
                    ],
                    'endurance': [
                        {'sport': 'cycling', 'tipo': 'Z2 ride corto', 'tss': 30,
                         'duration_min': 45, 'intensidad': 1,
                         'descripcion': f'45\' a {z2_w}w, cadencia 85-90rpm'},
                        {'sport': 'cycling', 'tipo': 'Recovery spin', 'tss': 15,
                         'duration_min': 30, 'intensidad': 0,
                         'descripcion': f'30\' suave a {round(z2_w*0.75)}w'},
                    ],
                    'long': [
                        {'sport': 'cycling', 'tipo': 'Fondo bike', 'tss': 55,
                         'duration_min': 65, 'intensidad': 1,
                         'descripcion': f'65\' a {z2_w}w'},
                    ],
                },
                'swimming': {
                    'quality': [
                        {'sport': 'swimming', 'tipo': 'Threshold swim corto', 'tss': 25,
                         'duration_min': 35, 'intensidad': 2,
                         'descripcion': f'200m cal + 6x100m a {csf}/100m c/20" + 200m enfr'},
                    ],
                    'endurance': [
                        {'sport': 'swimming', 'tipo': 'Swim endurance', 'tss': 20,
                         'duration_min': 35, 'intensidad': 1,
                         'descripcion': f'35\' continuo a {cs2}/100m, foco en técnica'},
                        {'sport': 'swimming', 'tipo': 'Swim recovery', 'tss': 12,
                         'duration_min': 25, 'intensidad': 0,
                         'descripcion': f'25\' suave variando estilos, drill cada 200m'},
                    ],
                    'long': [
                        {'sport': 'swimming', 'tipo': 'Swim técnica', 'tss': 25,
                         'duration_min': 40, 'intensidad': 1,
                         'descripcion': f'40\' a {cs2}/100m, foco DPS y rolido'},
                    ],
                },
            }
        else:
            # ── CARGA NORMAL/ALTA ──
            t = {
                'running': {
                    'quality': [
                        {'sport': 'running', 'tipo': 'FTP intervals', 'tss': 70,
                         'duration_min': 55, 'intensidad': 2,
                         'descripcion': f'12\' cal Z1 + 5x1000m a {pf}/km c/2\' pausa + 8\' vuelta calma'},
                        {'sport': 'running', 'tipo': 'Tempo run', 'tss': 65,
                         'duration_min': 50, 'intensidad': 2,
                         'descripcion': f'12\' cal Z1 + 20\' continuo a {pf}/km + 10\' Z1'},
                        {'sport': 'running', 'tipo': 'VO2max', 'tss': 80,
                         'duration_min': 55, 'intensidad': 3,
                         'descripcion': f'12\' cal + 6x800m a {pv}/km c/2\'30" pausa + 8\' enfr'},
                        {'sport': 'running', 'tipo': 'Progresivo', 'tss': 60,
                         'duration_min': 50, 'intensidad': 2,
                         'descripcion': f'15\' Z1 a {p1}/km + 15\' Z2 a {p2}/km + 12\' Z3-4 a {pf}/km + 8\' enfr'},
                        {'sport': 'running', 'tipo': 'Cruise intervals', 'tss': 70,
                         'duration_min': 55, 'intensidad': 2,
                         'descripcion': f'12\' cal + 3x10\' a {pf}/km c/3\' pausa + 8\' enfr'},
                    ],
                    'endurance': [
                        {'sport': 'running', 'tipo': 'Easy run', 'tss': 40,
                         'duration_min': 45, 'intensidad': 1,
                         'descripcion': f'45\' continuo a {p2}/km, FC < {round(lthr*0.80)}'},
                        {'sport': 'running', 'tipo': 'Recovery run', 'tss': 25,
                         'duration_min': 30, 'intensidad': 0,
                         'descripcion': f'30\' suave a {p1}/km, FC < {round(lthr*0.75)}'},
                    ],
                    'long': [
                        {'sport': 'running', 'tipo': 'Long run', 'tss': 90,
                         'duration_min': 75, 'intensidad': 1,
                         'descripcion': f'75\' a {p2}/km, últimos 15\' bajar a {_pace(round(pace_z2*0.95,2))}/km'},
                        {'sport': 'running', 'tipo': 'Long run progresivo', 'tss': 100,
                         'duration_min': 80, 'intensidad': 2,
                         'descripcion': f'50\' a {p2}/km + 20\' a {pf}/km + 10\' enfr'},
                    ],
                },
                'cycling': {
                    'quality': [
                        {'sport': 'cycling', 'tipo': 'Sweet spot', 'tss': 75,
                         'duration_min': 60, 'intensidad': 2,
                         'descripcion': f'15\' cal + 3x12\' a {ss_w}w (88% FTP) c/4\' + 10\' enfr'},
                        {'sport': 'cycling', 'tipo': 'FTP intervals', 'tss': 80,
                         'duration_min': 65, 'intensidad': 2,
                         'descripcion': f'15\' cal + 2x20\' a {ftp_w}w c/5\' + 10\' enfr'},
                        {'sport': 'cycling', 'tipo': 'VO2max bike', 'tss': 85,
                         'duration_min': 60, 'intensidad': 3,
                         'descripcion': f'15\' cal + 5x4\' a {vo2_w}w c/4\' + 10\' enfr'},
                        {'sport': 'cycling', 'tipo': 'Over/Under', 'tss': 75,
                         'duration_min': 60, 'intensidad': 2,
                         'descripcion': f'15\' cal + 4x(3\' a {round(ftp_w*1.05)}w / 3\' a {ss_w}w) + enfr'},
                    ],
                    'endurance': [
                        {'sport': 'cycling', 'tipo': 'Z2 ride', 'tss': 55,
                         'duration_min': 75, 'intensidad': 1,
                         'descripcion': f'75\' continuo a {z2_w}w, cadencia 85-90rpm'},
                        {'sport': 'cycling', 'tipo': 'Recovery spin', 'tss': 25,
                         'duration_min': 40, 'intensidad': 0,
                         'descripcion': f'40\' suave a {round(z2_w*0.75)}w, cadencia libre'},
                    ],
                    'long': [
                        {'sport': 'cycling', 'tipo': 'Long ride', 'tss': 110,
                         'duration_min': 120, 'intensidad': 1,
                         'descripcion': f'2hs a {z2_w}w, últimos 30\' subir a {ss_w}w'},
                        {'sport': 'cycling', 'tipo': 'Long ride endurance', 'tss': 95,
                         'duration_min': 110, 'intensidad': 1,
                         'descripcion': f'1h50 continuo a {z2_w}w, nutrición cada 30\''},
                    ],
                },
                'swimming': {
                    'quality': [
                        {'sport': 'swimming', 'tipo': 'Threshold swim', 'tss': 35,
                         'duration_min': 45, 'intensidad': 2,
                         'descripcion': f'400m cal + 8x100m a {csf}/100m c/20" + 200m enfr'},
                        {'sport': 'swimming', 'tipo': 'Speed swim', 'tss': 40,
                         'duration_min': 45, 'intensidad': 3,
                         'descripcion': f'300m cal + 12x50m a {cs9}/100m c/30" + 200m enfr'},
                        {'sport': 'swimming', 'tipo': 'Cruise swim', 'tss': 35,
                         'duration_min': 50, 'intensidad': 2,
                         'descripcion': f'300m cal + 4x300m a {csf}/100m c/30" + 200m enfr'},
                    ],
                    'endurance': [
                        {'sport': 'swimming', 'tipo': 'Swim endurance', 'tss': 30,
                         'duration_min': 45, 'intensidad': 1,
                         'descripcion': f'45\' continuo a {cs2}/100m, foco en técnica y DPS'},
                        {'sport': 'swimming', 'tipo': 'Swim recovery', 'tss': 15,
                         'duration_min': 30, 'intensidad': 0,
                         'descripcion': f'30\' suave variando estilos, drill cada 200m'},
                    ],
                    'long': [
                        {'sport': 'swimming', 'tipo': 'Swim long', 'tss': 40,
                         'duration_min': 55, 'intensidad': 1,
                         'descripcion': f'55\' a {cs2}/100m, cambio de estilo cada 400m'},
                    ],
                },
            }
        return t

    def _format_plan(self, plan):
        """Formatea el plan para output legible."""
        dias_nombre = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        out = []
        for i, s in enumerate(plan):
            nombre = dias_nombre[i] if i < 7 else f'Día {i+1}'
            if s.get('descanso'):
                out.append({'dia': nombre, 'sesion': 'DESCANSO'})
            else:
                out.append({
                    'dia': nombre,
                    'sport': s.get('sport'),
                    'tipo': s.get('tipo'),
                    'tss': s.get('tss'),
                    'duracion': s.get('duration_min'),
                    'intensidad': ['Recovery', 'Endurance', 'Threshold', 'VO2max'][s.get('intensidad', 1)],
                    'descripcion': s.get('descripcion', ''),
                })
                if 'sesion_2' in s:
                    s2 = s['sesion_2']
                    out.append({
                        'dia': f'{nombre} (2da)',
                        'sport': s2.get('sport'),
                        'tipo': s2.get('tipo'),
                        'tss': s2.get('tss'),
                        'duracion': s2.get('duration_min'),
                        'intensidad': ['Recovery', 'Endurance', 'Threshold', 'VO2max'][s2.get('intensidad', 1)],
                        'descripcion': s2.get('descripcion', ''),
                    })
        return out

    # ──────────────────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────────────────

    def _get_bio(self, bio_idx, fecha):
        f = pd.Timestamp(fecha)
        for delta in [0, -1, 1]:
            f2 = f + timedelta(days=delta)
            if f2 in bio_idx.index:
                row = bio_idx.loc[f2]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                return {
                    'hrv_rmssd': _sf(row.get('hrv_rmssd'), 55),
                    'sleep_h': _sf(row.get('sleep_h'), 7),
                    'stress_avg': _sf(row.get('stress_avg'), 30),
                    'recovery_score': _sf(row.get('recovery_score'), 50),
                    'body_battery': _sf(row.get('body_battery'), 50),
                    'hrv_delta_pct': 0,
                }
        return None

    def _get_bio_7d(self, bio_idx, fecha):
        f = pd.Timestamp(fecha)
        rng = pd.date_range(f - timedelta(days=6), f, freq='D')
        hrvs, sleeps, stresses = [], [], []
        for d in rng:
            if d in bio_idx.index:
                r = bio_idx.loc[d]
                if isinstance(r, pd.DataFrame): r = r.iloc[0]
                h = _sf(r.get('hrv_rmssd'))
                if h > 0: hrvs.append(h)
                s = _sf(r.get('sleep_h'))
                if s > 0: sleeps.append(s)
                st = _sf(r.get('stress_avg'))
                if st > 0: stresses.append(st)
        return {
            'hrv_avg': np.mean(hrvs) if hrvs else 55,
            'hrv_cv': np.std(hrvs) / max(np.mean(hrvs), 1) if len(hrvs) >= 3 else 0.08,
            'sleep_avg': np.mean(sleeps) if sleeps else 7,
            'stress_avg': np.mean(stresses) if stresses else 30,
        }

    def _acwr_at(self, fecha):
        f = pd.Timestamp(fecha)
        mask_7 = (self._ses['fecha'] >= f - timedelta(days=6)) & (self._ses['fecha'] <= f)
        mask_28 = (self._ses['fecha'] >= f - timedelta(days=27)) & (self._ses['fecha'] <= f)
        t7 = self._ses[mask_7]['tss_total'].sum()
        t28 = self._ses[mask_28]['tss_total'].sum()
        return t7 / max(t28 / 4, 1)

    def _fitness_at(self, fecha, disc):
        if disc in self._estado:
            return self._estado[disc].get('fitness', 0)
        return 0

    def _fatigue_at(self, fecha, disc):
        if disc in self._estado:
            return self._estado[disc].get('fatigue', 0)
        return 0

    def _intensidad_sesion(self, row):
        tss = _sf(row['tss_total'])
        dur_h = _sf(row['duration_min']) / 60
        tss_h = tss / max(dur_h, 0.1)
        if tss_h > 100: return 3  # vo2
        if tss_h > 70: return 2   # threshold
        if tss_h > 35: return 1   # endurance
        return 0                   # recovery

    def _estado_bio_actual(self):
        if self._bio is not None and not self._bio.empty:
            last = self._bio.iloc[-1]
            return {
                'hrv_rmssd': _sf(last.get('hrv_rmssd'), 55),
                'sleep_h': _sf(last.get('sleep_h'), 7),
                'stress_avg': _sf(last.get('stress_avg'), 30),
                'recovery_score': _sf(last.get('recovery_score'), 50),
                'body_battery': _sf(last.get('body_battery'), 50),
            }
        return {'hrv_rmssd': 55, 'sleep_h': 7, 'stress_avg': 30,
                'recovery_score': 50, 'body_battery': 50}

    def _predecir_readiness(self, bio, banisters):
        if not self.readiness.ok:
            return 1
        tsb = sum(bm.form for bm in banisters.values()) / max(len(banisters), 1)
        ctl = sum(bm.fitness for bm in banisters.values()) / max(len(banisters), 1)
        atl = sum(bm.fatigue for bm in banisters.values()) / max(len(banisters), 1)
        acwr = max((bm.acwr for bm in banisters.values()), default=1.0)
        x = np.array([
            bio.get('hrv_rmssd', 55), bio.get('hrv_rmssd', 55), 0.08, 0,
            bio.get('sleep_h', 7), bio.get('sleep_h', 7),
            bio.get('stress_avg', 30), bio.get('stress_avg', 30),
            bio.get('recovery_score', 50), bio.get('body_battery', 50),
            tsb, ctl, atl, acwr, 0, 0, 3,
        ])
        return self.readiness.predecir(x)

    def _predecir_respuesta(self, bio, banisters, sesion):
        if not self.response.ok:
            return {}
        sport = sesion.get('sport', 'running')
        lthr = _sf(self.perfil.get('lthr_run', 162), 162)
        x = np.array([
            bio.get('hrv_rmssd', 55), bio.get('sleep_h', 7),
            bio.get('stress_avg', 30), bio.get('recovery_score', 50),
            banisters.get('running', BanisterDisc('r')).fitness,
            banisters.get('cycling', BanisterDisc('c')).fitness,
            banisters.get('swimming', BanisterDisc('s')).fitness,
            banisters.get('running', BanisterDisc('r')).fatigue,
            banisters.get('cycling', BanisterDisc('c')).fatigue,
            banisters.get('swimming', BanisterDisc('s')).fatigue,
            sum(bm.form for bm in banisters.values()) / max(len(banisters), 1),
            sesion.get('tss', 50), sesion.get('duration_min', 45),
            0.85,  # hr_avg / lthr approx
            1 if sport == 'running' else 0,
            1 if sport == 'cycling' else 0,
            1 if sport == 'swimming' else 0,
            sesion.get('intensidad', 1),
        ])
        return self.response.predecir(x)

    def _actualizar_bio(self, bio, resp, tss, intensidad):
        bio = dict(bio)
        # Si el modelo de respuesta predijo algo, usarlo
        if 'hrv_post' in resp:
            bio['hrv_rmssd'] = resp['hrv_post']
        else:
            # Heurística: TSS alto baja HRV temporalmente
            factor = 1 - (tss / 500) * 0.15
            bio['hrv_rmssd'] *= max(factor, 0.80)

        if 'recovery_post' in resp:
            bio['recovery_score'] = resp['recovery_post']
        else:
            bio['recovery_score'] = max(20, bio.get('recovery_score', 50) - intensidad * 8)

        bio['body_battery'] = max(10, bio.get('body_battery', 50) - tss * 0.08)
        return bio


# ═══════════════════════════════════════════════════════════════
#  API (para app.py)
# ═══════════════════════════════════════════════════════════════

_CACHE = {}

def twin_prescripcion(conn, atleta_id, tss=None, tipo_sem='carga', n=200):
    if atleta_id not in _CACHE:
        twin = DigitalTwin(conn, atleta_id)
        twin.calibrar(verbose=False)
        _CACHE[atleta_id] = twin
    else:
        _CACHE[atleta_id].conn = conn

    twin = _CACHE[atleta_id]
    if not twin.calibrado:
        return {'ok': False, 'error': 'No se pudo calibrar', 'metricas': twin.metricas}

    resultado = twin.generar_escenarios(tss_semanal=tss, semana_tipo=tipo_sem, n_escenarios=n)

    # Guardar automáticamente en DB
    if resultado.get('ok'):
        try:
            guardado = twin_guardar(conn, atleta_id, resultado)
            resultado['guardado'] = guardado
        except Exception as e:
            resultado['guardado'] = {'error': str(e)}

    return resultado


# ═══════════════════════════════════════════════════════════════
#  GUARDAR → EVALUAR → APRENDER
# ═══════════════════════════════════════════════════════════════

def twin_guardar(conn, atleta_id: int, resultado: dict) -> dict:
    """
    Guarda los top 5 escenarios del Twin en la DB.
    Se llama automáticamente después de generar escenarios.
    """
    if not resultado.get('ok'):
        return {'guardado': False}

    from datetime import date
    semana = date.today().strftime('%G-%V')
    cur = conn.cursor()

    guardados = 0
    for i, esc in enumerate(resultado.get('mejores', [])):
        try:
            cur.execute('''
                INSERT INTO twin_predicciones
                    (atleta_id, semana_iso, escenario_rank, plan,
                     tss_predicho, riesgo_predicho, score_predicho)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (atleta_id, semana_iso, escenario_rank)
                DO UPDATE SET plan=EXCLUDED.plan, tss_predicho=EXCLUDED.tss_predicho,
                    riesgo_predicho=EXCLUDED.riesgo_predicho, score_predicho=EXCLUDED.score_predicho,
                    fecha_gen=CURRENT_DATE
            ''', [
                atleta_id, semana, i + 1,
                json.dumps(esc.get('plan', []), ensure_ascii=False, default=str),
                esc.get('tss_total', 0),
                esc.get('riesgo', 0),
                esc.get('ranking', 0),
            ])
            guardados += 1
        except Exception as e:
            print(f'  [twin_guardar] Error escenario {i+1}: {e}')
            try: conn.rollback()
            except: pass

    try:
        conn.commit()
    except:
        pass

    return {'guardado': True, 'n': guardados, 'semana': semana}


def twin_elegir(conn, atleta_id: int, semana_iso: str, escenario_rank: int) -> dict:
    """El coach elige un escenario. Marca como 'elegido'."""
    cur = conn.cursor()
    # Desmarcar todos de esa semana
    cur.execute('''
        UPDATE twin_predicciones SET elegido=FALSE
        WHERE atleta_id=%s AND semana_iso=%s
    ''', [atleta_id, semana_iso])
    # Marcar el elegido
    cur.execute('''
        UPDATE twin_predicciones SET elegido=TRUE
        WHERE atleta_id=%s AND semana_iso=%s AND escenario_rank=%s
    ''', [atleta_id, semana_iso, escenario_rank])
    conn.commit()
    return {'ok': True, 'elegido': escenario_rank}


def twin_evaluar(conn, atleta_id: int, semana_iso: str = None) -> dict:
    """
    Evalúa la semana pasada: compara lo que el Twin predijo vs lo que pasó.

    Calcula 'acierto' (0 a 1):
      - ¿El TSS real se acercó al predicho?
      - ¿La HRV se mantuvo (como predijo el riesgo bajo)?
      - ¿La distribución por deporte fue similar?
      - ¿El rendimiento mejoró?
    """
    from datetime import date, timedelta

    if semana_iso is None:
        # Evaluar la semana pasada
        hoy = date.today()
        lunes_pasado = hoy - timedelta(days=hoy.weekday() + 7)
        semana_iso = lunes_pasado.strftime('%G-%V')

    cur = conn.cursor()

    # Obtener predicción guardada (la elegida, o la #1 si no eligieron)
    cur.execute('''
        SELECT plan, tss_predicho, riesgo_predicho, score_predicho, escenario_rank
        FROM twin_predicciones
        WHERE atleta_id=%s AND semana_iso=%s
        ORDER BY elegido DESC, escenario_rank ASC
        LIMIT 1
    ''', [atleta_id, semana_iso])
    pred = cur.fetchone()
    if not pred:
        return {'ok': False, 'error': f'Sin predicción para semana {semana_iso}'}

    plan_pred, tss_pred, riesgo_pred, score_pred, esc_rank = pred

    # Obtener lo que realmente pasó esa semana
    # Calcular fechas de la semana ISO
    year, week = map(int, semana_iso.split('-'))
    from datetime import datetime
    lunes = datetime.strptime(f'{year}-W{week:02d}-1', '%G-W%V-%u').date()
    domingo = lunes + timedelta(days=6)

    df_real = _sql('''
        SELECT fecha, sport, tss_total, hr_avg, pace, np_watts, duration_min
        FROM sesiones
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s AND tss_total > 0
        ORDER BY fecha
    ''', conn, [atleta_id, lunes, domingo])

    if df_real.empty:
        return {'ok': False, 'error': f'Sin sesiones reales en semana {semana_iso}'}

    tss_real = float(df_real['tss_total'].sum())

    # Distribución por deporte real
    dist_real = df_real.groupby('sport')['tss_total'].sum()
    n_swim_real = len(df_real[df_real['sport'] == 'swimming'])
    n_bike_real = len(df_real[df_real['sport'] == 'cycling'])
    n_run_real = len(df_real[df_real['sport'] == 'running'])

    # HRV de esa semana y la siguiente
    df_bio = _sql('''
        SELECT fecha, hrv_rmssd FROM sleep_hrv
        WHERE atleta_id=%s AND fecha BETWEEN %s AND %s
        ORDER BY fecha
    ''', conn, [atleta_id, lunes, domingo + timedelta(days=7)])

    hrv_sem = df_bio[df_bio['fecha'] <= pd.Timestamp(domingo)]['hrv_rmssd'].dropna()
    hrv_post = df_bio[df_bio['fecha'] > pd.Timestamp(domingo)]['hrv_rmssd'].dropna()
    hrv_ok = None
    if len(hrv_sem) >= 3 and len(hrv_post) >= 3:
        hrv_ok = bool(hrv_post.mean() >= hrv_sem.mean() * 0.90)

    # ── Calcular ACIERTO (0 a 1) ──
    puntos = 0
    max_puntos = 0

    # 1. TSS: ¿se acercó? (±15% = perfecto)
    max_puntos += 30
    if tss_pred > 0:
        ratio_tss = abs(tss_real - tss_pred) / tss_pred
        if ratio_tss <= 0.15:
            puntos += 30
        elif ratio_tss <= 0.30:
            puntos += 20
        elif ratio_tss <= 0.50:
            puntos += 10

    # 2. HRV mantenida (si riesgo predicho era bajo, HRV debería estar OK)
    max_puntos += 25
    if hrv_ok is not None:
        if riesgo_pred < 0.20 and hrv_ok:
            puntos += 25  # predijo bajo riesgo Y HRV se mantuvo
        elif riesgo_pred >= 0.20 and not hrv_ok:
            puntos += 15  # predijo riesgo Y HRV cayó (acertó el riesgo)
        elif hrv_ok:
            puntos += 15  # HRV OK siempre es positivo

    # 3. Cobertura 3 disciplinas
    max_puntos += 20
    if n_swim_real >= 2 and n_bike_real >= 2 and n_run_real >= 2:
        puntos += 20
    elif n_swim_real >= 1 and n_bike_real >= 1 and n_run_real >= 1:
        puntos += 12

    # 4. Absorción (CTL subió o se mantuvo)
    max_puntos += 25
    cur.execute('''
        SELECT ctl FROM sesiones WHERE atleta_id=%s AND fecha <= %s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    ''', [atleta_id, lunes - timedelta(days=1)])
    ctl_pre = cur.fetchone()
    cur.execute('''
        SELECT ctl FROM sesiones WHERE atleta_id=%s AND fecha <= %s AND ctl IS NOT NULL
        ORDER BY fecha DESC LIMIT 1
    ''', [atleta_id, domingo])
    ctl_post = cur.fetchone()
    absorcion_ok = None
    if ctl_pre and ctl_post:
        absorcion_ok = bool(float(ctl_post[0]) >= float(ctl_pre[0]) * 0.97)
        if absorcion_ok:
            puntos += 25
        else:
            puntos += 8  # bajó pero no necesariamente es error del Twin

    acierto = round(puntos / max(max_puntos, 1), 3)

    # ── Guardar evaluación ──
    cur.execute('''
        UPDATE twin_predicciones
        SET evaluado=TRUE, tss_real=%s, hrv_ok=%s, absorcion_ok=%s,
            acierto=%s, fecha_eval=CURRENT_DATE
        WHERE atleta_id=%s AND semana_iso=%s AND escenario_rank=%s
    ''', [tss_real, hrv_ok, absorcion_ok, acierto,
          atleta_id, semana_iso, esc_rank])
    conn.commit()

    return {
        'ok': True,
        'semana': semana_iso,
        'escenario': esc_rank,
        'tss_predicho': tss_pred,
        'tss_real': tss_real,
        'riesgo_predicho': riesgo_pred,
        'hrv_ok': hrv_ok,
        'absorcion_ok': absorcion_ok,
        'acierto': acierto,
        'acierto_pct': round(acierto * 100),
        'detalle': {
            'tss_diff_pct': round(abs(tss_real - tss_pred) / max(tss_pred, 1) * 100, 1),
            'n_sesiones_real': len(df_real),
            'distribucion_real': {
                'swim': n_swim_real, 'bike': n_bike_real, 'run': n_run_real
            },
        }
    }


def twin_historial(conn, atleta_id: int) -> dict:
    """Historial de aciertos del Twin. Muestra si está aprendiendo."""
    cur = conn.cursor()
    cur.execute('''
        SELECT semana_iso, escenario_rank, tss_predicho, tss_real,
               riesgo_predicho, acierto, elegido, evaluado
        FROM twin_predicciones
        WHERE atleta_id=%s AND evaluado=TRUE
        ORDER BY semana_iso DESC
        LIMIT 20
    ''', [atleta_id])
    rows = cur.fetchall()
    cols = ['semana', 'escenario', 'tss_pred', 'tss_real',
            'riesgo_pred', 'acierto', 'elegido', 'evaluado']

    historial = [dict(zip(cols, r)) for r in rows]

    # Tendencia de acierto
    aciertos = [h['acierto'] for h in historial if h['acierto'] is not None]
    tendencia = None
    if len(aciertos) >= 4:
        primera_mitad = np.mean(aciertos[len(aciertos)//2:])
        segunda_mitad = np.mean(aciertos[:len(aciertos)//2])
        tendencia = 'mejorando' if segunda_mitad > primera_mitad + 0.03 else \
                    'empeorando' if segunda_mitad < primera_mitad - 0.03 else 'estable'

    return {
        'historial': historial,
        'promedio_acierto': round(np.mean(aciertos), 3) if aciertos else None,
        'n_evaluaciones': len(aciertos),
        'tendencia': tendencia,
    }


# ═══════════════════════════════════════════════════════════════
#  DIAGNÓSTICO CLI
# ═══════════════════════════════════════════════════════════════

def diagnosticar(conn, atleta_id):
    twin = DigitalTwin(conn, atleta_id)
    res = twin.calibrar(verbose=True)
    if not res.get('ok'):
        print(f'  ✗ {res}')
        return

    print(f'\n  Generando 100 escenarios de semana...')
    # Mostrar TSS de referencia
    if twin._ses is not None and not twin._ses.empty:
        fecha_max = twin._ses['fecha'].max()
        ult_28d = twin._ses[twin._ses['fecha'] >= fecha_max - timedelta(days=28)]
        tss_4sem = float(ult_28d['tss_total'].sum()) / 4
        print(f'  TSS ref (prom 4 semanas recientes): {tss_4sem:.0f}  '
              f'→ target: {round(tss_4sem * 1.15)} (+15%)')
    esc = twin.generar_escenarios(n_escenarios=100)

    if not esc.get('ok'):
        print(f'  ✗ {esc}')
        return

    print(f'  ✓ {esc["n_evaluados"]} escenarios evaluados')
    print(f'\n  TOP 5 SEMANAS:')
    for rank, sem in enumerate(esc['mejores']):
        print(f'\n  ── Escenario #{sem["id"]} (ranking: {sem["ranking"]:.4f}, '
              f'riesgo: {sem["riesgo"]*100:.0f}%, TSS: {sem["tss_total"]}) ──')
        for dia in sem['plan']:
            if dia.get('sesion') == 'DESCANSO':
                print(f'    {dia["dia"]:>12s}: DESCANSO')
            else:
                print(f'    {dia["dia"]:>12s}: [{dia.get("sport","?"):>8s}] '
                      f'{dia.get("tipo",""):<20s} '
                      f'TSS={dia.get("tss",0):>3d}  '
                      f'{dia.get("intensidad",""):<10s}')
                desc = dia.get('descripcion', '')
                if desc:
                    print(f'    {"":>12s}  → {desc}')

    return twin


if __name__ == '__main__':
    import sys, os, psycopg2
    db_url = os.environ.get('DATABASE_URL',
        'postgresql://postgres.jbsggrkzudeiekgmwcel:noah_triatlon'
        '@aws-1-us-west-2.pooler.supabase.com:6543/postgres')
    conn = psycopg2.connect(db_url)

    if len(sys.argv) > 1:
        diagnosticar(conn, int(sys.argv[1]))
    else:
        cur = conn.cursor()
        cur.execute('SELECT id, nombre FROM atletas WHERE activo=true')
        for aid, nombre in cur.fetchall():
            print(f'\n\n{"#"*65}\n  {nombre} (ID {aid})\n{"#"*65}')
            diagnosticar(conn, aid)
    conn.close()
