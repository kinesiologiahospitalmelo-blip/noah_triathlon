path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

# Nuevo codigo del PredictorLSTM (GRU + Attention)
CODIGO_GRU = '''

# ── Predictor GRU con Atención Temporal ──────────────────────────────────────
class PredictorLSTM:
    """
    Red neuronal GRU con mecanismo de atención temporal.
    
    Por qué GRU + Atención sobre LSTM puro:
    - GRU: menos parámetros que LSTM, igual performance con 1500-3000 días
    - Atención: aprende QUÉ días de los últimos 28 importan más
      (ej: el día post-carrera pesa más que un martes normal)
    - Ideal para datos biológicos con patrones cíclicos (mesociclos)

    Arquitectura:
      Input:  [batch, 28 días, 17 features]
          ↓
      GRU(64, bidireccional=True) → [batch, 28, 128]
          ↓
      Attention Layer → [batch, 128]  (aprende pesos por día)
          ↓
      Dense(64, relu) → Dropout(0.3)
          ↓
      Dense(32, relu) → Dropout(0.2)
          ↓
      Output(4): [delta_ctl_7d, delta_tsb_7d, prob_absorcion, prob_riesgo]
    """

    SEQ_LEN  = 28   # días de historia que ve el modelo
    FEATURES = [
        'ctl', 'atl', 'tsb', 'tss_dia',
        'hrv_rmssd', 'stress_avg', 'sleep_h',
        'hrv_7d_avg', 'stress_7d_avg', 'sleep_7d_avg',
        'hrv_ratio_7d', 'delta_hrv', 'tss_7d',
        'adherencia_7d', 'hrv_respuesta_7d', 'patron_carga',
        'sesion_intensa',
    ]
    TARGETS  = ['delta_ctl_7d', 'delta_tsb_7d', 'absorcion_ok', 'riesgo_sobre']

    def __init__(self):
        self.modelo       = None
        self.scaler_X     = None
        self.scaler_y     = None
        self.entrenado    = False
        self.score        = {}
        self.features_ok  = []
        self.n_muestras   = 0
        self.ctl_baseline = 30.0

    def _verificar_pytorch(self) -> bool:
        try:
            import torch
            return True
        except ImportError:
            print('  [GRU] PyTorch no instalado. Correr: pip install torch --break-system-packages')
            return False

    def _construir_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mismo metodo que PredictorRespuestaFisiologica."""
        df = df.copy().sort_values('fecha').reset_index(drop=True)
        n  = len(df)
        d_ctl, d_tsb, absorcion, riesgo = [], [], [], []

        for i in range(n):
            fut7  = df.iloc[i+1 : min(i+8, n)]
            fut14 = df.iloc[i+1 : min(i+15, n)]
            if len(fut7) < 4:
                d_ctl.append(None); d_tsb.append(None)
                absorcion.append(None); riesgo.append(None); continue

            ctl_h = float(df.iloc[i].get('ctl') or self.ctl_baseline)
            tsb_h = float(df.iloc[i].get('tsb') or 0)
            hrv_h = float(df.iloc[i].get('hrv_rmssd') or 60)

            ctl_f = fut7['ctl'].dropna().tail(3).mean()    if 'ctl'       in fut7 else ctl_h
            tsb_f = fut7['tsb'].dropna().tail(3).mean()    if 'tsb'       in fut7 else tsb_h
            hrv_f = fut7['hrv_rmssd'].dropna().mean()      if 'hrv_rmssd' in fut7 else hrv_h

            d_ctl.append((ctl_f - ctl_h) if pd.notna(ctl_f) else None)
            d_tsb.append((tsb_f - tsb_h) if pd.notna(tsb_f) else None)

            if pd.notna(ctl_f) and pd.notna(hrv_f):
                absorcion.append(1 if (ctl_f >= ctl_h * 0.97 and
                                       (hrv_h <= 0 or hrv_f >= hrv_h * 0.90)) else 0)
            else:
                absorcion.append(None)

            r = 0
            if len(fut14) >= 5:
                atl_m = fut14['atl'].dropna().mean() if 'atl' in fut14 else 0
                ctl_m = fut14['ctl'].dropna().mean() if 'ctl' in fut14 else 1
                if ctl_m > 0 and (atl_m / ctl_m) > 1.5: r = 1
                if hrv_h > 0:
                    hrv_14 = fut14['hrv_rmssd'].dropna().mean() if 'hrv_rmssd' in fut14 else hrv_h
                    if hrv_14 < hrv_h * 0.85: r = 1
            riesgo.append(r)

        df['delta_ctl_7d'] = d_ctl
        df['delta_tsb_7d'] = d_tsb
        df['absorcion_ok']  = absorcion
        df['riesgo_sobre']  = riesgo
        return df

    def _construir_secuencias(self, df: pd.DataFrame):
        """
        Convierte el dataframe en secuencias de SEQ_LEN dias.
        Cada secuencia [X_t-28..t] predice [y_t+7].
        """
        import numpy as np
        features = [f for f in self.FEATURES if f in df.columns]
        self.features_ok = features

        df_t = self._construir_targets(df)
        df_t = df_t.sort_values('fecha').reset_index(drop=True)

        # Imputar NaN con mediana por columna
        for f in features:
            med = df_t[f].median()
            df_t[f] = df_t[f].fillna(med if pd.notna(med) else 0)

        X_seqs, y_seqs = [], []
        n = len(df_t)

        for i in range(self.SEQ_LEN, n):
            # Targets del dia i (mirando 7 dias al futuro)
            row = df_t.iloc[i]
            targets = [
                row.get('delta_ctl_7d'),
                row.get('delta_tsb_7d'),
                row.get('absorcion_ok'),
                row.get('riesgo_sobre'),
            ]
            if any(t is None or (isinstance(t, float) and np.isnan(t)) for t in targets):
                continue

            # Secuencia de los 28 dias anteriores
            seq = df_t.iloc[i - self.SEQ_LEN : i][features].values.astype(float)
            if seq.shape[0] != self.SEQ_LEN:
                continue

            X_seqs.append(seq)
            y_seqs.append(targets)

        if not X_seqs:
            return None, None

        return np.array(X_seqs, dtype=np.float32), np.array(y_seqs, dtype=np.float32)

    def entrenar(self, df: pd.DataFrame, epochs: int = 80, lr: float = 1e-3) -> dict:
        if not self._verificar_pytorch():
            return {}

        import torch
        import torch.nn as nn
        from sklearn.preprocessing import StandardScaler

        if df.empty or len(df) < self.SEQ_LEN + 30:
            print(f'  [GRU] Datos insuficientes: {len(df)} filas (min {self.SEQ_LEN + 30})')
            return {}

        self.ctl_baseline = float(df['ctl'].dropna().median()) if 'ctl' in df.columns else 30.0

        print(f'  [GRU] Construyendo secuencias de {self.SEQ_LEN} dias...')
        X, y = self._construir_secuencias(df)
        if X is None or len(X) < 50:
            print(f'  [GRU] Secuencias insuficientes: {0 if X is None else len(X)}')
            return {}

        print(f'  [GRU] {len(X)} secuencias | {X.shape[2]} features | 4 targets')

        # Normalizar features (por feature, no por secuencia)
        n_seq, seq_len, n_feat = X.shape
        X_2d = X.reshape(-1, n_feat)
        self.scaler_X = StandardScaler()
        X_2d_norm = self.scaler_X.fit_transform(X_2d)
        X_norm = X_2d_norm.reshape(n_seq, seq_len, n_feat)

        # Normalizar targets continuos (delta_ctl, delta_tsb), dejar binarios igual
        self.scaler_y = StandardScaler()
        y_cont = self.scaler_y.fit_transform(y[:, :2])
        y_norm = np.concatenate([y_cont, y[:, 2:]], axis=1)

        # Split train/val 85/15
        split = int(len(X_norm) * 0.85)
        X_tr, X_val = X_norm[:split], X_norm[split:]
        y_tr, y_val = y_norm[:split], y_norm[split:]

        X_tr  = torch.tensor(X_tr,  dtype=torch.float32)
        y_tr  = torch.tensor(y_tr,  dtype=torch.float32)
        X_val = torch.tensor(X_val, dtype=torch.float32)
        y_val = torch.tensor(y_val, dtype=torch.float32)

        # ── Arquitectura GRU + Atención ──────────────────────────────────────
        class AttentionLayer(nn.Module):
            def __init__(self, hidden_dim):
                super().__init__()
                self.attn = nn.Linear(hidden_dim, 1)

            def forward(self, gru_out):
                # gru_out: [batch, seq, hidden]
                scores = self.attn(gru_out).squeeze(-1)         # [batch, seq]
                weights = torch.softmax(scores, dim=1)           # [batch, seq]
                context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)  # [batch, hidden]
                return context, weights

        class GRUAttnModel(nn.Module):
            def __init__(self, n_feat):
                super().__init__()
                self.gru1  = nn.GRU(n_feat, 64, batch_first=True, bidirectional=True)
                self.attn  = AttentionLayer(128)  # 64*2 bidireccional
                self.gru2  = nn.GRU(128, 32, batch_first=True)
                self.drop1 = nn.Dropout(0.3)
                self.fc1   = nn.Linear(32, 64)
                self.drop2 = nn.Dropout(0.2)
                self.fc2   = nn.Linear(64, 32)
                self.out   = nn.Linear(32, 4)
                self.relu  = nn.ReLU()

            def forward(self, x):
                out, _ = self.gru1(x)            # [batch, seq, 128]
                ctx, _ = self.attn(out)          # [batch, 128]
                ctx    = ctx.unsqueeze(1)        # [batch, 1, 128]
                out, _ = self.gru2(ctx)          # [batch, 1, 32]
                out    = out.squeeze(1)          # [batch, 32]
                out    = self.drop1(out)
                out    = self.relu(self.fc1(out))
                out    = self.drop2(out)
                out    = self.relu(self.fc2(out))
                return self.out(out)             # [batch, 4]

            def get_attention_weights(self, x):
                out, _ = self.gru1(x)
                _, weights = self.attn(out)
                return weights

        modelo = GRUAttnModel(n_feat)
        optimizer = torch.optim.Adam(modelo.parameters(), lr=lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=8, factor=0.5)

        # Loss mixta: MSE para deltas (continuos) + BCE para clasificacion (binarios)
        mse  = nn.MSELoss()
        bce  = nn.BCEWithLogitsLoss()

        def loss_fn(pred, target):
            loss_reg  = mse(pred[:, :2], target[:, :2])          # delta_ctl, delta_tsb
            loss_cls  = bce(pred[:, 2:], target[:, 2:].clamp(0, 1))  # absorcion, riesgo
            return loss_reg * 0.6 + loss_cls * 0.4

        # Training con early stopping
        mejor_val   = float('inf')
        paciencia   = 15
        sin_mejora  = 0
        mejor_estado = None

        print(f'  [GRU] Entrenando {epochs} épocas...')
        for ep in range(epochs):
            modelo.train()
            pred_tr  = modelo(X_tr)
            loss_tr  = loss_fn(pred_tr, y_tr)
            optimizer.zero_grad()
            loss_tr.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            optimizer.step()

            modelo.eval()
            with torch.no_grad():
                pred_val = modelo(X_val)
                loss_val = loss_fn(pred_val, y_val).item()

            scheduler.step(loss_val)

            if loss_val < mejor_val:
                mejor_val    = loss_val
                sin_mejora   = 0
                mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}
            else:
                sin_mejora += 1
                if sin_mejora >= paciencia:
                    print(f'  [GRU] Early stopping en época {ep+1} (val_loss={mejor_val:.4f})')
                    break

            if (ep + 1) % 20 == 0:
                print(f'  [GRU] Época {ep+1:3d} | train={loss_tr.item():.4f} | val={loss_val:.4f}')

        # Cargar mejor modelo
        if mejor_estado:
            modelo.load_state_dict(mejor_estado)

        self.modelo    = modelo
        self.entrenado = True
        self.n_muestras = len(X)
        self.score     = {'val_loss': round(mejor_val, 4), 'n_seq': len(X), 'n_feat': n_feat}

        print(f'  [GRU] Entrenado: val_loss={mejor_val:.4f} | {len(X)} secuencias | {n_feat} features')
        return self.score

    def predecir(self, df_reciente: pd.DataFrame) -> dict:
        """
        Predice usando los ultimos SEQ_LEN dias del dataframe.
        """
        if not self.entrenado or self.modelo is None:
            return {'disponible': False}
        if not self._verificar_pytorch():
            return {'disponible': False}

        import torch
        import numpy as np

        features = self.features_ok
        if len(df_reciente) < self.SEQ_LEN:
            return {'disponible': False, 'razon': f'Necesita {self.SEQ_LEN} dias, tiene {len(df_reciente)}'}

        df_seq = df_reciente.tail(self.SEQ_LEN).copy()
        for f in features:
            med = df_seq[f].median()
            df_seq[f] = df_seq[f].fillna(med if pd.notna(med) else 0)

        X = df_seq[features].values.astype(np.float32)

        # Normalizar
        n_feat = X.shape[1]
        X_norm = self.scaler_X.transform(X)
        X_tensor = torch.tensor(X_norm[np.newaxis, :, :], dtype=torch.float32)

        self.modelo.eval()
        with torch.no_grad():
            pred   = self.modelo(X_tensor).numpy()[0]
            pesos  = self.modelo.get_attention_weights(X_tensor).numpy()[0]

        # Desnormalizar outputs continuos
        cont = self.scaler_y.inverse_transform(pred[:2].reshape(1, -1))[0]

        prob_abs = float(torch.sigmoid(torch.tensor(pred[2])).item())
        prob_rie = float(torch.sigmoid(torch.tensor(pred[3])).item())

        # Dias mas importantes (top 5 por peso de atencion)
        top_dias = sorted(enumerate(pesos), key=lambda x: -x[1])[:5]
        dias_clave = [{'dia_atras': self.SEQ_LEN - i, 'peso': round(float(w), 3)}
                      for i, w in top_dias]

        if prob_rie >= 0.65 or prob_abs < 0.35:
            semaforo = 'rojo'
            msg = 'GRU detecta alto riesgo — reducir carga'
        elif prob_abs >= 0.70 and cont[0] >= 0:
            semaforo = 'verde'
            msg = 'GRU predice buena absorcion y adaptacion positiva'
        else:
            semaforo = 'amarillo'
            msg = 'GRU predice absorcion moderada — monitorear'

        return {
            'disponible':            True,
            'delta_ctl_predicho':    round(float(cont[0]), 2),
            'delta_tsb_predicho':    round(float(cont[1]), 2),
            'prob_absorcion':        round(prob_abs, 3),
            'prob_riesgo':           round(prob_rie, 3),
            'semaforo':              semaforo,
            'interpretacion':        msg,
            'dias_clave_atencion':   dias_clave,
        }

    def guardar(self, ruta: str):
        if not self.entrenado: return
        try:
            import torch, joblib, os
            os.makedirs(ruta, exist_ok=True)
            torch.save(self.modelo.state_dict(), f'{ruta}/gru_model.pth')
            joblib.dump(self.scaler_X,  f'{ruta}/gru_scaler_X.pkl')
            joblib.dump(self.scaler_y,  f'{ruta}/gru_scaler_y.pkl')
            joblib.dump({
                'features_ok':  self.features_ok,
                'score':        self.score,
                'ctl_baseline': self.ctl_baseline,
            }, f'{ruta}/gru_meta.pkl')
            print(f'  [GRU] Modelo guardado en {ruta}/')
        except Exception as e:
            print(f'  [GRU] Error guardando: {e}')

    def cargar(self, ruta: str) -> bool:
        try:
            import torch, joblib, os
            import torch.nn as nn
            if not os.path.exists(f'{ruta}/gru_model.pth'):
                return False
            meta = joblib.load(f'{ruta}/gru_meta.pkl')
            self.features_ok  = meta['features_ok']
            self.score        = meta['score']
            self.ctl_baseline = meta.get('ctl_baseline', 30.0)
            self.scaler_X     = joblib.load(f'{ruta}/gru_scaler_X.pkl')
            self.scaler_y     = joblib.load(f'{ruta}/gru_scaler_y.pkl')

            # Reconstruir arquitectura
            n_feat = len(self.features_ok)

            class AttentionLayer(nn.Module):
                def __init__(self, hidden_dim):
                    super().__init__()
                    self.attn = nn.Linear(hidden_dim, 1)
                def forward(self, gru_out):
                    scores  = self.attn(gru_out).squeeze(-1)
                    weights = torch.softmax(scores, dim=1)
                    context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)
                    return context, weights

            class GRUAttnModel(nn.Module):
                def __init__(self, n_feat):
                    super().__init__()
                    self.gru1  = nn.GRU(n_feat, 64, batch_first=True, bidirectional=True)
                    self.attn  = AttentionLayer(128)
                    self.gru2  = nn.GRU(128, 32, batch_first=True)
                    self.drop1 = nn.Dropout(0.3)
                    self.fc1   = nn.Linear(32, 64)
                    self.drop2 = nn.Dropout(0.2)
                    self.fc2   = nn.Linear(64, 32)
                    self.out   = nn.Linear(32, 4)
                    self.relu  = nn.ReLU()
                def forward(self, x):
                    out, _ = self.gru1(x)
                    ctx, _ = self.attn(out)
                    ctx    = ctx.unsqueeze(1)
                    out, _ = self.gru2(ctx)
                    out    = out.squeeze(1)
                    out    = self.drop1(out)
                    out    = self.relu(self.fc1(out))
                    out    = self.drop2(out)
                    out    = self.relu(self.fc2(out))
                    return self.out(out)
                def get_attention_weights(self, x):
                    out, _ = self.gru1(x)
                    _, weights = self.attn(out)
                    return weights

            m = GRUAttnModel(n_feat)
            m.load_state_dict(torch.load(f'{ruta}/gru_model.pth', map_location='cpu'))
            m.eval()
            self.modelo   = m
            self.entrenado = True
            print(f'  [GRU] Modelo cargado (val_loss={self.score.get("val_loss","?")})')
            return True
        except Exception as e:
            print(f'  [GRU] Error cargando: {e}')
            return False

'''

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Insertar antes de NOAHMind class
ANCHOR = '\nclass NOAHMind:'
if ANCHOR in content:
    content = content.replace(ANCHOR, CODIGO_GRU + ANCHOR)
    print("OK 1 - PredictorLSTM (GRU+Attention) insertado")
else:
    print("ERROR 1 - no matcheo anchor para insertar GRU")

# Agregar predictor_lstm a NOAHMind.__init__
OLD_INIT_END = "        self.analizador_adherencia  = AnalizadorAdherencia()\n        self._modelos_guardados     = {}"
NEW_INIT_END = """        self.analizador_adherencia  = AnalizadorAdherencia()
        self.predictor_lstm         = PredictorLSTM()   # GRU + Atención temporal
        self._modelos_guardados     = {}"""

if OLD_INIT_END in content:
    content = content.replace(OLD_INIT_END, NEW_INIT_END)
    print("OK 2 - predictor_lstm agregado a NOAHMind.__init__")
else:
    print("ERROR 2 - no matcheo __init__ para agregar predictor_lstm")

# Agregar entrenamiento GRU en NOAHMind.entrenar()
OLD_GUARDAR_CALL = "        # Guardar metadatos y modelos\n        self._guardar_metadatos(resultados)\n        self.guardar_modelos()\n        return resultados"
NEW_GUARDAR_CALL = """        # Modelo GRU + Atencion temporal (requiere PyTorch)
        try:
            import torch
            scores_gru = self.predictor_lstm.entrenar(self.df)
            if scores_gru:
                resultados['gru_attention'] = scores_gru
                print(f'  [GRU] val_loss={scores_gru.get("val_loss","?")} | {scores_gru.get("n_seq","?")} secuencias')
        except ImportError:
            print('  [GRU] PyTorch no disponible — saltando GRU')
        except Exception as e:
            print(f'  [GRU] Error entrenando GRU: {e}')

        # Guardar metadatos y modelos
        self._guardar_metadatos(resultados)
        self.guardar_modelos()
        return resultados"""

if OLD_GUARDAR_CALL in content:
    content = content.replace(OLD_GUARDAR_CALL, NEW_GUARDAR_CALL)
    print("OK 3 - GRU entrenamiento agregado a NOAHMind.entrenar()")
else:
    print("ERROR 3 - no matcheo guardar_call en entrenar()")

# Guardar GRU en guardar_modelos
OLD_GUARDAR_META = "        meta = {\n            'fecha':      str(date.today()),\n            'atleta_id':  self.atleta_id,"
NEW_GUARDAR_META = """        ruta_gru = f'{directorio}/atleta_{self.atleta_id}'
        self.predictor_lstm.guardar(ruta_gru)
        meta = {
            'fecha':      str(date.today()),
            'atleta_id':  self.atleta_id,"""

if OLD_GUARDAR_META in content:
    content = content.replace(OLD_GUARDAR_META, NEW_GUARDAR_META)
    print("OK 4 - GRU guardado en guardar_modelos()")
else:
    print("ERROR 4 - no matcheo guardar_modelos meta")

# Cargar GRU en cargar_modelos
OLD_CARGAR_PRINT = "            print(f'  [NOAH ML] Modelos cargados (entrenados hace {dias} días)')\n            return mind"
NEW_CARGAR_PRINT = """            ruta_gru = f'{ruta}'
            mind.predictor_lstm.cargar(ruta_gru)
            print(f'  [NOAH ML] Modelos cargados (entrenados hace {dias} días)')
            return mind"""

if OLD_CARGAR_PRINT in content:
    content = content.replace(OLD_CARGAR_PRINT, NEW_CARGAR_PRINT)
    print("OK 5 - GRU cargado en cargar_modelos()")
else:
    print("ERROR 5 - no matcheo cargar_modelos print")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nGUARDADO OK - PredictorLSTM (GRU+Attention) integrado en noah_ml.py")
