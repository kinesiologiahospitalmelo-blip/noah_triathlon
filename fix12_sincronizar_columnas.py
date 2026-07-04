path = r'C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Mapeo de nombres incorrectos (fix6) → nombres correctos (noah_streams schema)
reemplazos = [
    # KEY_MAP y todo el archivo
    ("'vertical_osc_mm'",    "'vert_osc_mm'"),
    ("'ground_contact_ms'",  "'gct_ms'"),
    ("'stride_length_m'",    "'stride_cm'"),
    ("'vertical_ratio'",     "'vert_ratio'"),
    ("'ground_balance'",     "'gct_balance'"),
    ("'respiration_rate'",   "'respiration'"),
    ("'performance_cond'",   "'stress'"),
    # temperatura: la columna en DB es temperature_c
    ("('temperature',",      "('temperature_c',"),
    # nombre de columna en INSERT y dict
    ('"vertical_osc_mm"',    '"vert_osc_mm"'),
    ('"ground_contact_ms"',  '"gct_ms"'),
    ('"stride_length_m"',    '"stride_cm"'),
    ('"vertical_ratio"',     '"vert_ratio"'),
    ('"ground_balance"',     '"gct_balance"'),
    ('"respiration_rate"',   '"respiration"'),
    ('"performance_cond"',   '"stress"'),
    ('"temperature"',        '"temperature_c"'),
]

cambios = 0
for old, new in reemplazos:
    n = content.count(old)
    if n > 0:
        content = content.replace(old, new)
        print(f"OK - '{old}' -> '{new}' ({n} cambio/s)")
        cambios += n
    else:
        print(f"-- '{old}' no encontrado (skip)")

if cambios > 0:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nGUARDADO OK - {cambios} cambios aplicados en sincronizar_garmin.py")
else:
    print("\nSin cambios - verificar manualmente")
