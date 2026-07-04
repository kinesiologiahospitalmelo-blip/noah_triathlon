path = r"C:\Users\Win10\Desktop\noah_cloud\app.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """@app.route('/api/atletas/<int:atleta_id>', methods=['GET'])
@requiere_login
def get_atleta(atleta_id):
    \"\"\"Retorna datos completos de un atleta.\"\"\"
    db = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        return error('Atleta no encontrado', 404)
    return ok(atleta)"""

nuevo = """@app.route('/api/atletas/<int:atleta_id>', methods=['GET'])
@requiere_login
def get_atleta(atleta_id):
    \"\"\"Retorna datos completos de un atleta.\"\"\"
    db = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        return error('Atleta no encontrado', 404)
    return ok(atleta)


@app.route('/api/atletas/<int:atleta_id>', methods=['PUT'])
@requiere_login
def actualizar_atleta_endpoint(atleta_id):
    \"\"\"
    Actualiza el perfil fisiologico de un atleta existente (LTHR run/bike/
    swim, FTP, CSS, HR max, peso, etc). Solo pisa los campos que vienen en
    el body -- el resto del perfil queda igual.
    \"\"\"
    datos = request.json or {}
    db = NOADatabase(DB_PATH)
    atleta = db.get_atleta(atleta_id)
    if not atleta:
        return error('Atleta no encontrado', 404)
    db.actualizar_atleta(atleta_id, datos)
    atleta_actualizado = db.get_atleta(atleta_id)
    return ok(atleta_actualizado)"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto de get_atleta. No se modifico el archivo.")
elif "actualizar_atleta_endpoint" in contenido:
    print("AVISO: el endpoint PUT ya existe, no se duplico.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: endpoint PUT /api/atletas/<id> agregado a app.py")
