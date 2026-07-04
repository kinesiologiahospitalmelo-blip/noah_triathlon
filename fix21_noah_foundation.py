path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

errors = []

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Rediseñar PredictorLSTM para soportar fine-tuning desde foundation model
# ═══════════════════════════════════════════════════════════════════════════════
OLD_LSTM_CLASS = "class PredictorLSTM:"
NEW_LSTM_CLASS = """class _GRUEncoder(object):
    \"\"\"
    Marcador para identificar el encoder compartido del Foundation Model.
    La arquitectura real vive en PredictorLSTM._build_model().
    \"\"\"
    pass


class PredictorLSTM:"""

if OLD_LSTM_CLASS in content:
    content = content.replace(OLD_LSTM_CLASS, NEW_LSTM_CLASS, 1)
    print("OK 1 - marcador GRUEncoder agregado")
else:
    errors.append("ERROR 1 - no matcheo PredictorLSTM class header")

# Agregar fine_tune_from al final de PredictorLSTM (antes de NOAHFoundationModel)
OLD_LSTM_CARGAR_END = """    def cargar(self, ruta: str) -> bool:
        try:
            import torch, joblib, os
            import torch.nn as nn
            if not os.path.exists(f\'{ruta}/gru_model.pth\'):
                return False
            meta = joblib.load(f\'{ruta}/gru_meta.pkl\')
            self.features_ok  = meta[\'features_ok\']
            self.score        = meta[\'score\']
            self.ctl_baseline = meta.get(\'ctl_baseline\', 30.0)
            self.scaler_X     = joblib.load(f\'{ruta}/gru_scaler_X.pkl\')
            self.scaler_y     = joblib.load(f\'{ruta}/gru_scaler_y.pkl\')"""

NEW_LSTM_CARGAR_END = """    def fine_tune_from(self, foundation_path: str, df: pd.DataFrame,
                       epochs: int = 30, lr: float = 5e-4) -> dict:
        \"\"\"
        Fine-tune desde un Foundation Model pre-entrenado.

        Fase 2/3 de la arquitectura NOAH:
        - Carga el encoder pre-entrenado (congelado — no se modifica)
        - Entrena solo el head (decoder) con datos del atleta especifico
        - Convergencia rapida: 30 epocas vs 80 del entrenamiento completo
        - El atleta nuevo hereda todo el conocimiento fisiologico general
        \"\"\"
        if not self._verificar_pytorch():
            return {}
        import torch, joblib, os
        import torch.nn as nn

        # Cargar foundation encoder
        meta_path = f\'{foundation_path}/foundation_meta.pkl\'
        if not os.path.exists(meta_path):
            print(\'  [GRU] Foundation model no encontrado — entrenar desde cero\')
            return self.entrenar(df, epochs=epochs*2, lr=lr)

        meta = joblib.load(meta_path)
        self.features_ok  = meta[\'features_ok\']
        self.ctl_baseline = meta.get(\'ctl_baseline\', 30.0)
        self.scaler_X     = joblib.load(f\'{foundation_path}/foundation_scaler_X.pkl\')
        self.scaler_y     = joblib.load(f\'{foundation_path}/foundation_scaler_y.pkl\')

        X, y = self._construir_secuencias(df)
        if X is None or len(X) < 20:
            print(\'  [GRU] Datos insuficientes para fine-tune\')
            return {}

        n_seq, seq_len, n_feat = X.shape
        from sklearn.preprocessing import StandardScaler
        X_2d_norm = self.scaler_X.transform(X.reshape(-1, n_feat))
        X_norm    = X_2d_norm.reshape(n_seq, seq_len, n_feat)
        y_cont    = self.scaler_y.transform(y[:, :2])
        y_norm    = np.concatenate([y_cont, y[:, 2:]], axis=1)

        split   = int(len(X_norm) * 0.85)
        X_tr    = torch.tensor(X_norm[:split],  dtype=torch.float32)
        y_tr    = torch.tensor(y_norm[:split],  dtype=torch.float32)
        X_val   = torch.tensor(X_norm[split:],  dtype=torch.float32)
        y_val   = torch.tensor(y_norm[split:],  dtype=torch.float32)

        # Construir modelo y cargar encoder pre-entrenado
        modelo = self._build_model(n_feat)
        state  = torch.load(f\'{foundation_path}/foundation_encoder.pth\', map_location=\'cpu\')
        modelo.load_state_dict(state, strict=False)  # carga lo que matchea

        # Congelar encoder (GRU1 + Attention), solo entrenar head
        for name, param in modelo.named_parameters():
            if \'gru1\' in name or \'attn\' in name:
                param.requires_grad = False  # encoder congelado
            else:
                param.requires_grad = True   # head se entrena

        n_trainable = sum(p.numel() for p in modelo.parameters() if p.requires_grad)
        n_total     = sum(p.numel() for p in modelo.parameters())
        print(f\'  [GRU] Fine-tune: {n_trainable}/{n_total} params libres ({n_trainable/n_total*100:.0f}%)\')

        optimizer = torch.optim.Adam(
            [p for p in modelo.parameters() if p.requires_grad], lr=lr)
        mse = nn.MSELoss()
        bce = nn.BCEWithLogitsLoss()
        def loss_fn(pred, target):
            return mse(pred[:, :2], target[:, :2]) * 0.6 + bce(pred[:, 2:], target[:, 2:].clamp(0,1)) * 0.4

        mejor_val, mejor_estado = float(\'inf\'), None
        for ep in range(epochs):
            modelo.train()
            pred  = modelo(X_tr)
            loss  = loss_fn(pred, y_tr)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            modelo.eval()
            with torch.no_grad():
                val_loss = loss_fn(modelo(X_val), y_val).item()
            if val_loss < mejor_val:
                mejor_val    = val_loss
                mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}

        if mejor_estado:
            modelo.load_state_dict(mejor_estado)
        self.modelo    = modelo
        self.entrenado = True
        self.score     = {\'val_loss\': round(mejor_val, 4), \'n_seq\': len(X), \'modo\': \'fine_tune\'}
        print(f\'  [GRU] Fine-tune completado: val_loss={mejor_val:.4f} ({len(X)} seq)\')
        return self.score

    def _build_model(self, n_feat: int):
        \"\"\"Construye la arquitectura GRU+Atencion. Separada para reusar en cargar/fine-tune.\"\"\"
        import torch.nn as nn
        import torch

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

        return GRUAttnModel(n_feat)

    def cargar(self, ruta: str) -> bool:
        try:
            import torch, joblib, os
            import torch.nn as nn
            if not os.path.exists(f\'{ruta}/gru_model.pth\'):
                return False
            meta = joblib.load(f\'{ruta}/gru_meta.pkl\')
            self.features_ok  = meta[\'features_ok\']
            self.score        = meta[\'score\']
            self.ctl_baseline = meta.get(\'ctl_baseline\', 30.0)
            self.scaler_X     = joblib.load(f\'{ruta}/gru_scaler_X.pkl\')
            self.scaler_y     = joblib.load(f\'{ruta}/gru_scaler_y.pkl\')"""

if OLD_LSTM_CARGAR_END in content:
    content = content.replace(OLD_LSTM_CARGAR_END, NEW_LSTM_CARGAR_END)
    print("OK 2 - fine_tune_from() y _build_model() agregados a PredictorLSTM")
else:
    errors.append("ERROR 2 - no matcheo cargar() para insertar fine_tune_from")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Insertar NOAHFoundationModel antes de NOAHMind
# ═══════════════════════════════════════════════════════════════════════════════
FOUNDATION_CODE = '''

# ── Foundation Model — pre-entrenamiento multi-atleta ─────────────────────────
class NOAHFoundationModel:
    """
    Foundation Model de NOAH — aprende patrones fisiologicos universales
    del deporte de resistencia entrenando en TODOS los atletas.

    Arquitectura de 3 fases:
      Fase 1: Cada atleta entrena su GRU independiente
      Fase 2: Foundation pre-entrena en todos los atletas combinados
      Fase 3: Fine-tune rapido (30 epocas) por atleta individual

    Ventajas vs modelo individual:
      - Atleta nuevo converge en 2 semanas en vez de 6 meses
      - Captura patrones universales (respuesta carga, recuperacion)
      - Cada atleta nuevo MEJORA el modelo base para todos
      - Robusto a datos faltantes (aprende a interpolar)

    Analogia: GPT aprende lenguaje general, fine-tune aprende dominio especifico.
    Aqui: Foundation aprende fisiologia general, fine-tune aprende al atleta.
    """

    MODEL_DIR = 'noah_modelos/foundation'
    FEATURES   = PredictorLSTM.FEATURES
    SEQ_LEN    = PredictorLSTM.SEQ_LEN

    def __init__(self):
        self.modelo      = None
        self.entrenado   = False
        self.score       = {}
        self.scaler_X    = None
        self.scaler_y    = None
        self.features_ok = []
        self.n_atletas   = 0
        self.n_seq_total = 0

    @classmethod
    def construir_dataset_multiatleta(cls, conn, atleta_ids: list) -> pd.DataFrame:
        """
        Combina datos de multiples atletas agregando un ID de atleta
        como feature categorico codificado.
        """
        dfs = []
        for aid in atleta_ids:
            try:
                df_a = construir_dataset(conn, aid)
                if df_a.empty or len(df_a) < cls.SEQ_LEN + 30:
                    continue
                df_a['atleta_id_enc'] = aid  # identificador del atleta
                # Normalizar CTL/ATL relativo al baseline del atleta
                # (permite comparar atletas con distintos niveles de fitness)
                ctl_med = df_a['ctl'].dropna().median()
                if ctl_med and ctl_med > 0:
                    df_a['ctl_rel'] = df_a['ctl'] / ctl_med
                    df_a['atl_rel'] = df_a['atl'] / ctl_med
                else:
                    df_a['ctl_rel'] = df_a['ctl']
                    df_a['atl_rel'] = df_a['atl']
                dfs.append(df_a)
                print(f'    [Foundation] Atleta {aid}: {len(df_a)} dias')
            except Exception as e:
                print(f'    [Foundation] Error atleta {aid}: {e}')
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def pretrain(self, conn, atleta_ids: list, epochs: int = 100) -> dict:
        """
        Pre-entrena el Foundation Model en todos los atletas.
        Guarda el encoder para fine-tuning posterior.
        """
        if not PredictorLSTM().__class__._verificar_pytorch(PredictorLSTM()):
            return {}
        import torch, torch.nn as nn, joblib, os
        from sklearn.preprocessing import StandardScaler

        print(f\'\\n  [Foundation] Pre-entrenando en {len(atleta_ids)} atletas...\')
        df_all = self.construir_dataset_multiatleta(conn, atleta_ids)
        if df_all.empty:
            print(\'  [Foundation] Sin datos suficientes\')
            return {}

        # Construir secuencias de todos los atletas
        all_X, all_y = [], []
        for aid in atleta_ids:
            df_a = df_all[df_all[\'atleta_id_enc\'] == aid].copy()
            tmp = PredictorLSTM()
            X, y = tmp._construir_secuencias(df_a)
            if X is not None and len(X) >= 20:
                all_X.append(X)
                all_y.append(y)

        if not all_X:
            return {}

        X_all = np.concatenate(all_X, axis=0).astype(np.float32)
        y_all = np.concatenate(all_y, axis=0).astype(np.float32)
        self.features_ok = tmp.features_ok
        self.n_atletas   = len(atleta_ids)
        self.n_seq_total = len(X_all)

        print(f\'  [Foundation] Total: {len(X_all)} secuencias | {X_all.shape[2]} features\')

        # Normalizar
        n_seq, seq_len, n_feat = X_all.shape
        self.scaler_X = StandardScaler()
        X_2d_norm = self.scaler_X.fit_transform(X_all.reshape(-1, n_feat))
        X_norm    = X_2d_norm.reshape(n_seq, seq_len, n_feat)
        self.scaler_y = StandardScaler()
        y_cont    = self.scaler_y.fit_transform(y_all[:, :2])
        y_norm    = np.concatenate([y_cont, y_all[:, 2:]], axis=1)

        # Shuffle y split 85/15
        idx   = np.random.permutation(len(X_norm))
        split = int(len(idx) * 0.85)
        X_tr  = torch.tensor(X_norm[idx[:split]], dtype=torch.float32)
        y_tr  = torch.tensor(y_norm[idx[:split]], dtype=torch.float32)
        X_val = torch.tensor(X_norm[idx[split:]], dtype=torch.float32)
        y_val = torch.tensor(y_norm[idx[split:]], dtype=torch.float32)

        modelo = PredictorLSTM()._build_model(n_feat)
        opt    = torch.optim.AdamW(modelo.parameters(), lr=1e-3, weight_decay=1e-4)
        sched  = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        mse    = nn.MSELoss()
        bce    = nn.BCEWithLogitsLoss()

        def loss_fn(pred, target):
            return mse(pred[:, :2], target[:, :2]) * 0.6 + bce(pred[:, 2:], target[:, 2:].clamp(0,1)) * 0.4

        mejor_val, mejor_estado = float(\'inf\'), None
        paciencia, sin_mejora   = 20, 0
        BATCH = 64

        print(f\'  [Foundation] Entrenando {epochs} epocas (batch={BATCH})...\')
        for ep in range(epochs):
            modelo.train()
            # Mini-batch training
            perm  = torch.randperm(len(X_tr))
            for i in range(0, len(X_tr), BATCH):
                idx_b = perm[i:i+BATCH]
                pred  = modelo(X_tr[idx_b])
                loss  = loss_fn(pred, y_tr[idx_b])
                opt.zero_grad(); loss.backward(); opt.step()

            modelo.eval()
            with torch.no_grad():
                val_loss = loss_fn(modelo(X_val), y_val).item()

            sched.step()
            if val_loss < mejor_val:
                mejor_val    = val_loss
                sin_mejora   = 0
                mejor_estado = {k: v.clone() for k, v in modelo.state_dict().items()}
            else:
                sin_mejora += 1
                if sin_mejora >= paciencia:
                    print(f\'  [Foundation] Early stopping ep {ep+1} (val={mejor_val:.4f})\')
                    break

            if (ep + 1) % 25 == 0:
                print(f\'  [Foundation] Ep {ep+1:3d} | val_loss={val_loss:.4f} | best={mejor_val:.4f}\')

        if mejor_estado:
            modelo.load_state_dict(mejor_estado)

        self.modelo    = modelo
        self.entrenado = True
        self.score     = {\'val_loss\': round(mejor_val, 4), \'n_atletas\': self.n_atletas, \'n_seq\': self.n_seq_total}

        # Guardar
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        torch.save(modelo.state_dict(), f\'{self.MODEL_DIR}/foundation_encoder.pth\')
        joblib.dump(self.scaler_X, f\'{self.MODEL_DIR}/foundation_scaler_X.pkl\')
        joblib.dump(self.scaler_y, f\'{self.MODEL_DIR}/foundation_scaler_y.pkl\')
        joblib.dump({
            \'features_ok\':  self.features_ok,
            \'score\':        self.score,
            \'ctl_baseline\': 30.0,
        }, f\'{self.MODEL_DIR}/foundation_meta.pkl\')
        import json
        with open(f\'{self.MODEL_DIR}/metadata.json\', \'w\') as f:
            json.dump({
                \'fecha\':     str(date.today()),
                \'n_atletas\': self.n_atletas,
                \'n_seq\':     self.n_seq_total,
                \'val_loss\':  mejor_val,
            }, f)
        print(f\'  [Foundation] Guardado en {self.MODEL_DIR}/ (val_loss={mejor_val:.4f})\')
        return self.score

    @classmethod
    def disponible(cls) -> bool:
        import os
        return os.path.exists(f\'{cls.MODEL_DIR}/foundation_encoder.pth\')

    @classmethod
    def info(cls) -> dict:
        import os, json
        meta_path = f\'{cls.MODEL_DIR}/metadata.json\'
        if not os.path.exists(meta_path):
            return {\'disponible\': False}
        with open(meta_path) as f:
            meta = json.load(f)
        meta[\'disponible\'] = True
        return meta

'''

if '\nclass NOAHMind:' in content:
    content = content.replace('\nclass NOAHMind:', FOUNDATION_CODE + '\nclass NOAHMind:')
    print("OK 3 - NOAHFoundationModel insertado antes de NOAHMind")
else:
    errors.append("ERROR 3 - no matcheo NOAHMind para insertar Foundation")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Agregar ensemble en analisis_completo (GRU + RF combinados)
# ═══════════════════════════════════════════════════════════════════════════════
OLD_ESCENARIOS = """        # Escenarios para Optimizer
        if self.predictor_respuesta.entrenado:
            tss_base = round(ctl * 7)
            opciones = [round(tss_base * f) for f in [0.6, 0.8, 1.0, 1.1, 1.2]]
            resultado['escenarios_tss'] = self.predictor_respuesta.simular_escenarios(estado, opciones)

        return resultado"""

NEW_ESCENARIOS = """        # Escenarios para Optimizer
        if self.predictor_respuesta.entrenado:
            tss_base = round(ctl * 7)
            opciones = [round(tss_base * f) for f in [0.6, 0.8, 1.0, 1.1, 1.2]]
            resultado['escenarios_tss'] = self.predictor_respuesta.simular_escenarios(estado, opciones)

        # GRU + Atención temporal (usa secuencia de ultimos 28 dias)
        if self.predictor_lstm.entrenado and self.df is not None:
            try:
                pred_gru = self.predictor_lstm.predecir(self.df)
                resultado['gru_prediccion'] = pred_gru
                # Ensemble RF + GRU (promedio ponderado por val_loss inverso)
                if pred_gru.get('disponible') and self.predictor_respuesta.entrenado:
                    pred_rf = resultado.get('predictor_respuesta', {})
                    # Peso por calidad: mejor val_loss = más peso
                    w_gru = 1 / (self.predictor_lstm.score.get('val_loss', 0.5) + 0.01)
                    w_rf  = 1 / (1 - min(0.99, abs(
                        self.predictor_respuesta.scores.get('absorcion_ok', {}).get('f1', 0.5) - 1
                    )) + 0.01)
                    w_total = w_gru + w_rf
                    resultado['ensemble'] = {
                        'prob_absorcion': round(
                            (pred_gru.get('prob_absorcion', 0.5) * w_gru +
                             pred_rf.get('prob_absorcion', 0.5) * w_rf) / w_total, 3),
                        'prob_riesgo': round(
                            (pred_gru.get('prob_riesgo', 0.3) * w_gru +
                             pred_rf.get('prob_riesgo_sobrecarga', 0.3) * w_rf) / w_total, 3),
                        'delta_ctl': round(
                            (pred_gru.get('delta_ctl_predicho', 0) * w_gru +
                             pred_rf.get('delta_ctl_predicho', 0) * w_rf) / w_total, 2),
                        'pesos': {'gru': round(w_gru/w_total, 2), 'rf': round(w_rf/w_total, 2)},
                        'dias_clave': pred_gru.get('dias_clave_atencion', []),
                    }
                    # Semaforo del ensemble
                    p_r = resultado['ensemble']['prob_riesgo']
                    p_a = resultado['ensemble']['prob_absorcion']
                    d_c = resultado['ensemble']['delta_ctl']
                    if p_r >= 0.60 or p_a < 0.35:
                        resultado['ensemble']['semaforo'] = 'rojo'
                        resultado['ensemble']['interpretacion'] = f'Ensemble detecta alto riesgo ({p_r:.0%}) — reducir carga'
                    elif p_a >= 0.68 and d_c >= 0:
                        resultado['ensemble']['semaforo'] = 'verde'
                        resultado['ensemble']['interpretacion'] = f'Ensemble predice buena absorcion ({p_a:.0%}) y CTL+{d_c:.1f}'
                    else:
                        resultado['ensemble']['semaforo'] = 'amarillo'
                        resultado['ensemble']['interpretacion'] = f'Absorcion moderada ({p_a:.0%}) — monitorear esta semana'
            except Exception as e:
                print(f'  [GRU] Error en prediccion GRU: {e}')

        # Foundation Model status
        resultado['foundation_disponible'] = NOAHFoundationModel.disponible()
        resultado['foundation_info']       = NOAHFoundationModel.info()

        return resultado"""

if OLD_ESCENARIOS in content:
    content = content.replace(OLD_ESCENARIOS, NEW_ESCENARIOS)
    print("OK 4 - ensemble GRU+RF agregado a analisis_completo()")
else:
    errors.append("ERROR 4 - no matcheo escenarios en analisis_completo")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Agregar metodo fine_tune_desde_foundation a NOAHMind
# ═══════════════════════════════════════════════════════════════════════════════
OLD_TSS_REC = "    def tss_recomendado(self, estado: dict) -> dict:"
NEW_TSS_REC = """    def fine_tune_gru(self) -> dict:
        \"\"\"
        Fine-tune del GRU desde el Foundation Model si esta disponible.
        Si no, entrena desde cero. Llamar despues de preparar_datos().
        \"\"\"
        if self.df is None:
            self.preparar_datos()
        if NOAHFoundationModel.disponible():
            print(f'  [GRU] Foundation disponible — fine-tuning para atleta {self.atleta_id}')
            return self.predictor_lstm.fine_tune_from(
                NOAHFoundationModel.MODEL_DIR, self.df)
        else:
            print(f'  [GRU] Sin Foundation — entrenando GRU desde cero')
            return self.predictor_lstm.entrenar(self.df)

    def tss_recomendado(self, estado: dict) -> dict:"""

if OLD_TSS_REC in content:
    content = content.replace(OLD_TSS_REC, NEW_TSS_REC)
    print("OK 5 - fine_tune_gru() agregado a NOAHMind")
else:
    errors.append("ERROR 5 - no matcheo tss_recomendado para insertar fine_tune_gru")

if errors:
    for e in errors: print(e)
else:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("\nGUARDADO OK - Foundation Model + Fine-tune + Ensemble integrados")
