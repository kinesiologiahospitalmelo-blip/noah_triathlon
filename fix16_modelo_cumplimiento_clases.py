path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

old = """        X = df_clean[features].values.astype(float)
        y = df_clean['completada'].values

        self.modelo = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        self.modelo.fit(X, y)
        scores = cross_val_score(self.modelo, X, y, cv=3, scoring='accuracy')"""

new = """        X = df_clean[features].values.astype(float)
        y = df_clean['completada'].values

        # Necesita minimo 2 clases para clasificar
        if len(set(y)) < 2:
            self.tasa_base = float(y.mean())
            return self.tasa_base  # devuelve la tasa base si todos iguales

        self.modelo = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        self.modelo.fit(X, y)
        scores = cross_val_score(self.modelo, X, y, cv=3, scoring='accuracy')"""

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - fix16 aplicado: check de clases antes de fit()")
else:
    print("ERROR - no matcheo")
