path = r"C:\Users\Win10\Desktop\noah_cloud\noa_db.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

marcador = "    # ── SESIONES ──────────────────────────────────────────────────────────────"

nueva_funcion = '''    def actualizar_atleta(self, atleta_id: int, datos: dict) -> bool:
        """
        Actualiza campos del perfil fisiologico de un atleta YA EXISTENTE
        (LTHR running/bike/swim, FTP, CSS, HR max, peso, etc). A diferencia
        de crear_atleta() (que es para el alta inicial), esta funcion solo
        toca las columnas que vienen en `datos` -- si un campo no se manda,
        no se pisa el valor que ya estaba guardado.
        """
        columnas_permitidas = {
            'lthr_run', 'lthr_bike', 'lthr_swim', 'ftp_watts', 'hr_max',
            'peso_kg', 'altura_cm', 'edad', 'sexo', 'deporte_ppal',
            'css_100m', 'nivel_experiencia', 'horas_semana', 'nombre', 'email',
        }
        campos = {k: v for k, v in datos.items() if k in columnas_permitidas and v is not None}
        if not campos:
            return False

        sets = ', '.join(f'{k}=%({k})s' for k in campos.keys())
        campos['atleta_id'] = atleta_id

        with self._conn() as conn:
            conn.execute(
                f'UPDATE atletas SET {sets} WHERE id=%(atleta_id)s',
                campos
            )
        return True

''' + marcador

if marcador not in contenido:
    print("ERROR: no se encontro el marcador de SESIONES. No se modifico el archivo.")
elif "def actualizar_atleta" in contenido:
    print("AVISO: actualizar_atleta ya existe en el archivo, no se duplico.")
else:
    contenido = contenido.replace(marcador, nueva_funcion, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: funcion actualizar_atleta agregada a noa_db.py")
