path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# s.fecha es TEXT en Postgres, hay que castearlo a date para comparar
old = """                AND s.fecha=p.fecha_generada::date
            LEFT JOIN sleep_hrv sh ON sh.atleta_id=p.atleta_id
                AND sh.fecha=p.fecha_generada::date"""

new = """                AND s.fecha::date=p.fecha_generada::date
            LEFT JOIN sleep_hrv sh ON sh.atleta_id=p.atleta_id
                AND sh.fecha::date=p.fecha_generada::date"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - fix15 aplicado: s.fecha::date y sh.fecha::date")
else:
    print("ERROR - no matcheo")
