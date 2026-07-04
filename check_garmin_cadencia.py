import sys
sys.path.insert(0, '.')

from app import get_conn
from sincronizar_garmin import get_client

conn = get_conn()
row = conn.execute(
    "SELECT garmin_user, garmin_pass FROM atletas WHERE id=1"
).fetchone()
conn.close()

if not row or not row[0]:
    print("No hay credenciales Garmin para atleta 1")
    sys.exit(1)

user, pwd_enc = row[0], row[1]
print("Usuario Garmin:", user)

client = get_client(user, pwd_enc)
print("Login OK")

garmin_id = '23322864731'
print("Bajando streams de actividad", garmin_id)
details = client.get_activity_details(garmin_id)

descriptors = details.get('metricDescriptors', [])
print("Keys disponibles:", len(descriptors))
for d in descriptors:
    print("  idx=", d.get('metricsIndex'), " key=", d.get('key'))

cad_keys = [d for d in descriptors if 'cadence' in d.get('key','').lower() or 'Cadence' in d.get('key','')]
print("Keys de cadencia encontradas:", len(cad_keys))
for d in cad_keys:
    print(" ", d)
