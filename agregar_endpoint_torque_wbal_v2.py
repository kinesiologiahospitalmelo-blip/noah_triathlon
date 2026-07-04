path = r"C:\Users\Win10\Desktop\noah_cloud\app.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

marcador = "\n# \u2500\u2500\u2500 DIAGN\u00d3STICO NOA \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"

if "get_torque_wbal" in contenido:
    print("AVISO: endpoint ya existe, no se duplico")
elif marcador not in contenido:
    print("ERROR: no se encontro el marcador")
    # Buscar alternativa
    alt = "\n# \u2500\u2500\u2500 DIAGN\u00d3STICO"
    if alt in contenido:
        print("  Alternativa encontrada, usando esa")
        marcador = alt
    else:
        import sys; sys.exit(1)

codigo = (
    "\n# \u2500\u2500\u2500 TORQUE & W'BAL \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
    "@app.route('/api/atletas/<int:atleta_id>/sesiones/<int:sesion_id>/torque_wbal', methods=['GET'])\n"
    "@requiere_login\n"
    "def get_torque_wbal(atleta_id, sesion_id):\n"
    "    import math\n"
    "    db     = NOADatabase(DB_PATH)\n"
    "    atleta = db.get_atleta(atleta_id)\n"
    "    ftp    = float(atleta.get('ftp_watts') or 200)\n"
    "    cp     = ftp * 0.97\n"
    "    w_prime   = float(atleta.get('w_prime') or 20000)\n"
    "    cad_opt   = float(atleta.get('cadencia_optima') or 85)\n"
    "    conn = db._conn()\n"
    "    sql  = ('SELECT ts_s, power, cadence FROM activity_samples '\n"
    "            'WHERE sesion_id = %s AND atleta_id = %s ORDER BY ts_s')\n"
    "    rows = conn.execute(sql, (sesion_id, atleta_id)).fetchall()\n"
    "    conn.close()\n"
    "    if not rows:\n"
    "        return ok({'samples': [], 'cuadrantes': {}, 'metricas': {}})\n"
    "    samples     = []\n"
    "    wbal        = w_prime\n"
    "    torque_acum = 0.0\n"
    "    vaciados    = 0\n"
    "    ya_critico  = False\n"
    "    q_counts    = {1: 0, 2: 0, 3: 0, 4: 0}\n"
    "    sum_power   = 0.0\n"
    "    sum_torque  = 0.0\n"
    "    for i, row in enumerate(rows):\n"
    "        ts_s    = float(row[0] or 0)\n"
    "        power   = float(row[1] or 0)\n"
    "        cadence = float(row[2] or 0)\n"
    "        dt      = max(0.5, min(float(rows[i][0] - rows[i-1][0]) if i > 0 else 1.0, 5.0))\n"
    "        torque  = (9.549 * power) / cadence if cadence > 0 else 0.0\n"
    "        torque_acum += torque * dt\n"
    "        if power > cp:\n"
    "            wbal = max(0, wbal - (power - cp) * dt)\n"
    "        else:\n"
    "            deficit = w_prime - wbal\n"
    "            if deficit > 0:\n"
    "                tau = 546 * math.exp(-0.01 * (cp - power)) + 316\n"
    "                torque_umbral = (9.549 * cp) / cad_opt if cad_opt > 0 else 30\n"
    "                if torque > torque_umbral * 0.5:\n"
    "                    tau *= (1.0 + (torque / torque_umbral) * 0.4)\n"
    "                wbal = min(w_prime, wbal + (deficit / tau) * dt)\n"
    "        wbal_pct = (wbal / w_prime) * 100\n"
    "        if wbal_pct < 30:\n"
    "            if not ya_critico:\n"
    "                vaciados += 1\n"
    "                ya_critico = True\n"
    "        else:\n"
    "            ya_critico = False\n"
    "        if cadence > 0:\n"
    "            alta_f = power > cp\n"
    "            alta_c = cadence >= cad_opt\n"
    "            q = 1 if alta_f and alta_c else 2 if alta_f else 3 if not alta_c else 4\n"
    "            q_counts[q] += 1\n"
    "        if power > 0 and torque > 0:\n"
    "            sum_power  += power\n"
    "            sum_torque += torque\n"
    "        samples.append({\n"
    "            'ts_s':     round(ts_s, 1),\n"
    "            'power':    int(power),\n"
    "            'cadence':  int(cadence),\n"
    "            'torque':   round(torque, 1),\n"
    "            'wbal_j':   round(wbal, 0),\n"
    "            'wbal_pct': round(wbal_pct, 1),\n"
    "        })\n"
    "    total_ped  = sum(q_counts.values()) or 1\n"
    "    cuadrantes = {f'Q{k}': round(v / total_ped * 100, 1) for k, v in q_counts.items()}\n"
    "    nme        = round(sum_power / sum_torque, 2) if sum_torque > 0 else None\n"
    "    return ok({\n"
    "        'samples': samples,\n"
    "        'cuadrantes': cuadrantes,\n"
    "        'metricas': {\n"
    "            'costo_torque_acumulado': round(torque_acum, 0),\n"
    "            'vaciados_criticos':      vaciados,\n"
    "            'nme':                    nme,\n"
    "            'wbal_final_pct':         round((wbal / w_prime) * 100, 1),\n"
    "            'ftp_usado':              ftp,\n"
    "            'cp_usado':               round(cp, 1),\n"
    "            'w_prime_usado':          w_prime,\n"
    "            'cadencia_optima':        cad_opt,\n"
    "            'total_muestras':         len(rows),\n"
    "        }\n"
    "    })\n\n"
)

contenido = contenido.replace(marcador, codigo + marcador, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)
print("OK: endpoint /torque_wbal agregado a app.py")
