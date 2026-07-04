path = r"C:\Users\Win10\Desktop\noah_cloud\app.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

marcador = "\n# ─── DIAGNÓSTICO NOA ─────────────────────────────────────────────────────────"

nuevo_endpoint = """
# ─── TORQUE & W'BAL ───────────────────────────────────────────────────────────

@app.route('/api/atletas/<int:atleta_id>/sesiones/<int:sesion_id>/torque_wbal', methods=['GET'])
@requiere_login
def get_torque_wbal(atleta_id, sesion_id):
    \"\"\"
    Calcula Torque y W'bal segundo a segundo para una sesion de ciclismo.

    Torque (N.m) = (9.549 x P) / cadencia
    W'bal: modelo diferencial de Skiba con factor de penalizacion por torque alto.

    Devuelve samples, cuadrantes (% tiempo Q1-Q4) y metricas resumen.
    \"\"\"
    import math
    db     = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    ftp    = float(atleta.get('ftp_watts') or 200)
    cp     = ftp * 0.97
    w_prime  = float(atleta.get('w_prime') or 20000)
    cad_opt  = float(atleta.get('cadencia_optima') or 85)

    conn = db._conn()
    rows = conn.execute("""
        SELECT ts_s, power, cadence
        FROM activity_samples
        WHERE sesion_id = %s AND atleta_id = %s
        ORDER BY ts_s
    """, (sesion_id, atleta_id)).fetchall()
    conn.close()

    if not rows:
        return ok({'samples': [], 'cuadrantes': {}, 'metricas': {}})

    samples      = []
    wbal         = w_prime
    torque_acum  = 0.0
    vaciados     = 0
    ya_critico   = False
    q_counts     = {1: 0, 2: 0, 3: 0, 4: 0}
    sum_power    = 0.0
    sum_torque   = 0.0
    n_valid      = 0

    for i, row in enumerate(rows):
        ts_s    = float(row[0] or 0)
        power   = float(row[1] or 0)
        cadence = float(row[2] or 0)
        dt      = max(0.5, min(float(rows[i][0] - rows[i-1][0]) if i > 0 else 1.0, 5.0))

        # Torque
        torque = (9.549 * power) / cadence if cadence > 0 else 0.0
        torque_acum += torque * dt

        # W'bal Skiba diferencial
        if power > cp:
            wbal = max(0, wbal - (power - cp) * dt)
        else:
            deficit = w_prime - wbal
            if deficit > 0:
                tau = 546 * math.exp(-0.01 * (cp - power)) + 316
                torque_umbral = (9.549 * cp) / cad_opt if cad_opt > 0 else 30
                if torque > torque_umbral * 0.5:
                    tau *= (1.0 + (torque / torque_umbral) * 0.4)
                wbal = min(w_prime, wbal + (deficit / tau) * dt)

        wbal_pct = (wbal / w_prime) * 100
        if wbal_pct < 30:
            if not ya_critico:
                vaciados += 1
                ya_critico = True
        else:
            ya_critico = False

        # Cuadrante
        if cadence > 0:
            q = (1 if power > cp and cadence >= cad_opt else
                 2 if power > cp and cadence < cad_opt else
                 3 if power <= cp and cadence < cad_opt else 4)
            q_counts[q] += 1

        if power > 0 and torque > 0:
            sum_power  += power
            sum_torque += torque
            n_valid    += 1

        samples.append({
            'ts_s':     round(ts_s, 1),
            'power':    int(power),
            'cadence':  int(cadence),
            'torque':   round(torque, 1),
            'wbal_j':   round(wbal, 0),
            'wbal_pct': round(wbal_pct, 1),
        })

    total_ped  = sum(q_counts.values()) or 1
    cuadrantes = {f'Q{k}': round(v / total_ped * 100, 1) for k, v in q_counts.items()}
    nme        = round(sum_power / sum_torque, 2) if sum_torque > 0 else None

    return ok({
        'samples': samples,
        'cuadrantes': cuadrantes,
        'metricas': {
            'costo_torque_acumulado': round(torque_acum, 0),
            'vaciados_criticos':      vaciados,
            'nme':                    nme,
            'wbal_final_pct':         round((wbal / w_prime) * 100, 1),
            'ftp_usado':              ftp,
            'cp_usado':               round(cp, 1),
            'w_prime_usado':          w_prime,
            'cadencia_optima':        cad_opt,
            'total_muestras':         len(rows),
        }
    })

"""

if "get_torque_wbal" in contenido:
    print("AVISO: endpoint ya existe, no se duplico")
elif marcador not in contenido:
    print("ERROR: no se encontro el marcador de DIAGNOSTICO")
else:
    contenido = contenido.replace(marcador, nuevo_endpoint + marcador, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: endpoint /torque_wbal agregado a app.py")
