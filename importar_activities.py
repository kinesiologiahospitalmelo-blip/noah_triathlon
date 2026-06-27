"""
importar_activities.py — Proyecto NOA
======================================
Importa el CSV de Garmin Connect al sistema NOA.
Genérico: funciona para cualquier atleta nuevo (onboarding).

Uso:
    python importar_activities.py --atleta eugenio --csv Activities.csv
    python importar_activities.py --atleta sofia   --csv Activities.csv --db noa.db
    python importar_activities.py --atleta eugenio --csv Activities.csv --dry-run

Salida:
    - Inserta/actualiza registros en SQLite (tabla `activities`)
    - Log por consola con resumen de importación
    - Archivo JSON de control: importacion_<atleta>_<timestamp>.json
"""

from __future__ import annotations
import argparse
import json
import logging
import re
import psycopg2
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────
# Configuración de logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("NOA.importar")


# ─────────────────────────────────────────────
# Mapeo de columnas Garmin ES → nombres internos NOA
# ─────────────────────────────────────────────
COLUMNAS = {
    "Tipo de actividad":                  "tipo_actividad",
    "Fecha":                              "fecha",
    "Título":                             "titulo",
    "Distancia":                          "distancia_km",
    "Calorías":                           "calorias",
    "Tiempo":                             "duracion_hms",
    "Frecuencia cardiaca media":          "fc_media",
    "FC máxima":                          "fc_max",
    "TE aeróbico":                        "te_aerobico",
    "Cadencia de carrera media":          "cadencia_media",
    "Cadencia de carrera máxima":         "cadencia_max",
    "Ritmo medio":                        "ritmo_medio_ms",       # convertido a seg/km
    "GAP medio":                          "gap_medio_ms",         # convertido a seg/km
    "Ascenso total":                      "ascenso_m",
    "Descenso total":                     "descenso_m",
    "Longitud media de zancada":          "zancada_media_m",
    "Relación vertical media":            "relacion_vertical",
    "Oscilación vertical media":          "oscilacion_vertical_cm",
    "Tiempo medio de contacto con el suelo": "contacto_suelo_ms",
    "Normalized Power® (NP®)":            "np_watts",
    "Training Stress Score®":             "tss",
    "Potencia media":                     "potencia_media_w",
    "Potencia máxima":                    "potencia_max_w",
    "Pasos":                              "pasos",
    "Temperatura mínima":                 "temp_min_c",
    "Temperatura máxima":                 "temp_max_c",
    "Número de vueltas":                  "num_vueltas",
    "Tiempo en movimiento":               "tiempo_movimiento_s",  # convertido a segundos
    "Tiempo transcurrido":                "tiempo_total_s",       # convertido a segundos
    "Altura mínima":                      "altura_min_m",
    "Altura máxima":                      "altura_max_m",
    # Columnas natación (presentes pero sólo relevantes para ese tipo)
    "Paladas totales":                    "paladas_totales",
    "Swolf medio":                        "swolf_medio",
}

# Tipos de actividad Garmin → etiqueta normalizada NOA
TIPO_NORM = {
    "Carrera":                 "running",
    "Natación en piscina":     "swim",
    "Ciclismo":                "cycling",
    "HIIT":                    "hiit",
    "Entrenamiento en cinta":  "running",   # treadmill → running
    "Entreno de fuerza":       "strength",
    "Otros":                   "other",
}


# ─────────────────────────────────────────────
# Funciones de conversión
# ─────────────────────────────────────────────

def hms_a_segundos(valor: str) -> float | None:
    """'01:27:00' o '00:42:14' → segundos. Acepta HH:MM:SS y MM:SS."""
    if pd.isna(valor) or str(valor).strip() in ("--", ""):
        return None
    partes = str(valor).strip().split(":")
    try:
        if len(partes) == 3:
            h, m, s = partes
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(partes) == 2:
            m, s = partes
            return int(m) * 60 + float(s)
    except ValueError:
        pass
    return None


def ritmo_a_seg_km(valor: str) -> float | None:
    """'7:32' (min:seg por km) → segundos por km (452.0)."""
    if pd.isna(valor) or str(valor).strip() in ("--", ""):
        return None
    partes = str(valor).strip().split(":")
    try:
        if len(partes) == 2:
            return int(partes[0]) * 60 + int(partes[1])
    except ValueError:
        pass
    return None


def limpiar_entero(valor) -> int | None:
    """'11,154' o '11154' → 11154. Maneja '--' y NaN."""
    if pd.isna(valor) or str(valor).strip() in ("--", ""):
        return None
    try:
        return int(str(valor).replace(",", "").replace(".", "").strip())
    except ValueError:
        return None


def limpiar_float(valor) -> float | None:
    """Convierte a float; retorna None si es '--' o inválido."""
    if pd.isna(valor) or str(valor).strip() in ("--", ""):
        return None
    try:
        return float(str(valor).replace(",", ".").strip())
    except ValueError:
        return None


# ─────────────────────────────────────────────
# Carga y transformación del CSV
# ─────────────────────────────────────────────

def cargar_csv(ruta: Path) -> pd.DataFrame:
    """Lee el CSV de Garmin y devuelve DataFrame con columnas normalizadas."""
    log.info(f"Leyendo CSV: {ruta}")
    try:
        df = pd.read_csv(ruta, dtype=str)  # todo como str para control manual
    except Exception as e:
        log.error(f"No se pudo leer el CSV: {e}")
        sys.exit(1)

    # Renombrar sólo las columnas que existen en este export
    rename = {k: v for k, v in COLUMNAS.items() if k in df.columns}
    df = df.rename(columns=rename)
    log.info(f"  {len(df)} filas, {len(df.columns)} columnas detectadas")
    return df


def transformar(df: pd.DataFrame, atleta: str) -> list[dict]:
    """Aplica conversiones y devuelve lista de dicts listos para insertar."""
    registros = []
    errores = 0

    for idx, row in df.iterrows():
        try:
            rec = {
                "atleta":           atleta,
                "tipo_actividad":   TIPO_NORM.get(
                    str(row.get("tipo_actividad", "Otros")).strip(), "other"
                ),
                "fecha":            pd.to_datetime(
                    row.get("fecha"), errors="coerce"
                ).isoformat() if row.get("fecha") else None,
                "titulo":           str(row.get("titulo", "")).strip() or None,

                # Métricas numéricas directas
                "distancia_km":     limpiar_float(row.get("distancia_km")),
                "calorias":         limpiar_entero(row.get("calorias")),
                "fc_media":         limpiar_entero(row.get("fc_media")),
                "fc_max":           limpiar_entero(row.get("fc_max")),
                "te_aerobico":      limpiar_float(row.get("te_aerobico")),
                "cadencia_media":   limpiar_entero(row.get("cadencia_media")),
                "cadencia_max":     limpiar_entero(row.get("cadencia_max")),
                "ascenso_m":        limpiar_entero(row.get("ascenso_m")),
                "descenso_m":       limpiar_entero(row.get("descenso_m")),
                "zancada_media_m":  limpiar_float(row.get("zancada_media_m")),
                "relacion_vertical":       limpiar_float(row.get("relacion_vertical")),
                "oscilacion_vertical_cm":  limpiar_float(row.get("oscilacion_vertical_cm")),
                "contacto_suelo_ms":       limpiar_entero(row.get("contacto_suelo_ms")),
                "np_watts":         limpiar_entero(row.get("np_watts")),
                "tss":              limpiar_float(row.get("tss")),
                "potencia_media_w": limpiar_entero(row.get("potencia_media_w")),
                "potencia_max_w":   limpiar_entero(row.get("potencia_max_w")),
                "pasos":            limpiar_entero(row.get("pasos")),
                "temp_min_c":       limpiar_float(row.get("temp_min_c")),
                "temp_max_c":       limpiar_float(row.get("temp_max_c")),
                "num_vueltas":      limpiar_entero(row.get("num_vueltas")),
                "altura_min_m":     limpiar_entero(row.get("altura_min_m")),
                "altura_max_m":     limpiar_entero(row.get("altura_max_m")),
                "paladas_totales":  limpiar_entero(row.get("paladas_totales")),
                "swolf_medio":      limpiar_float(row.get("swolf_medio")),

                # Conversiones de formato tiempo/ritmo
                "duracion_s":       hms_a_segundos(row.get("duracion_hms")),
                "tiempo_movimiento_s": hms_a_segundos(row.get("tiempo_movimiento_s")),
                "tiempo_total_s":   hms_a_segundos(row.get("tiempo_total_s")),
                "ritmo_medio_seg_km": ritmo_a_seg_km(row.get("ritmo_medio_ms")),
                "gap_medio_seg_km": ritmo_a_seg_km(row.get("gap_medio_ms")),

                # Metadata de importación
                "importado_en":     datetime.now().isoformat(),
                "fila_csv":         int(idx) + 2,  # +2 por header + 0-index
            }

            if rec["fecha"] is None:
                log.warning(f"  Fila {idx+2}: fecha inválida, se omite")
                errores += 1
                continue

            registros.append(rec)

        except Exception as e:
            log.warning(f"  Fila {idx+2}: error inesperado ({e}), se omite")
            errores += 1

    log.info(f"  Transformados: {len(registros)} OK, {errores} omitidos")
    return registros


# ─────────────────────────────────────────────
# Base de datos SQLite
# ─────────────────────────────────────────────

DDL_ACTIVITIES = """
CREATE TABLE IF NOT EXISTS activities (
    id                      SERIAL PRIMARY KEY,
    atleta                  TEXT    NOT NULL,
    tipo_actividad          TEXT,
    fecha                   TEXT    NOT NULL,
    titulo                  TEXT,
    distancia_km            REAL,
    calorias                INTEGER,
    duracion_s              REAL,
    tiempo_movimiento_s     REAL,
    tiempo_total_s          REAL,
    fc_media                INTEGER,
    fc_max                  INTEGER,
    te_aerobico             REAL,
    cadencia_media          INTEGER,
    cadencia_max            INTEGER,
    ritmo_medio_seg_km      REAL,
    gap_medio_seg_km        REAL,
    ascenso_m               INTEGER,
    descenso_m              INTEGER,
    zancada_media_m         REAL,
    relacion_vertical       REAL,
    oscilacion_vertical_cm  REAL,
    contacto_suelo_ms       INTEGER,
    np_watts                INTEGER,
    tss                     REAL,
    potencia_media_w        INTEGER,
    potencia_max_w          INTEGER,
    pasos                   INTEGER,
    temp_min_c              REAL,
    temp_max_c              REAL,
    num_vueltas             INTEGER,
    altura_min_m            INTEGER,
    altura_max_m            INTEGER,
    paladas_totales         INTEGER,
    swolf_medio             REAL,
    importado_en            TEXT,
    fila_csv                INTEGER,
    UNIQUE (atleta, fecha)   -- evita duplicados en re-importaciones
);
"""


def inicializar_db(ruta_db) -> object:
    """`ruta_db` se mantiene como nombre del parámetro por compatibilidad
    con el resto del archivo, pero ahora se espera la cadena de conexión
    a Postgres (DATABASE_URL), no una ruta de archivo SQLite. PRAGMA
    journal_mode=WAL no tiene equivalente en Postgres — el motor maneja
    su propio WAL internamente, no hace falta configurarlo desde el cliente.
    """
    from db_compat import ConexionCompat
    conn = ConexionCompat(psycopg2.connect(str(ruta_db)))
    conn.execute(DDL_ACTIVITIES)
    conn.commit()
    log.info(f"DB lista: Postgres")
    return conn


def insertar(conn, registros: list[dict]) -> dict:
    """INSERT ... ON CONFLICT DO NOTHING (idempotente por atleta+fecha,
    restricción UNIQUE real confirmada en el esquema). Retorna stats."""
    stats = {"insertados": 0, "duplicados": 0, "errores": 0}
    cols = [k for k in registros[0].keys()]
    placeholders = ", ".join(["%s"] * len(cols))
    sql = (f"INSERT INTO activities ({', '.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT (atleta, fecha) DO NOTHING")

    for rec in registros:
        try:
            resultado = conn.execute(sql, list(rec.values()))
            # rowcount==1 si insertó, 0 si el ON CONFLICT DO NOTHING evitó
            # el duplicado — mismo significado que con SQLite, sin cambios
            # en la lógica de conteo.
            if resultado.rowcount == 1:
                stats["insertados"] += 1
            else:
                stats["duplicados"] += 1
        except Exception as e:
            log.warning(f"  Error al insertar fila {rec.get('fila_csv')}: {e}")
            conn.rollback()  # limpiar transacción abortada antes del próximo insert
            stats["errores"] += 1

    conn.commit()
    return stats


# ─────────────────────────────────────────────
# Reporte de importación
# ─────────────────────────────────────────────

def guardar_reporte(atleta: str, stats: dict, registros: list[dict], dry_run: bool):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = f"importacion_{atleta}_{ts}.json"
    reporte = {
        "atleta":       atleta,
        "timestamp":    ts,
        "dry_run":      dry_run,
        "total_filas":  len(registros),
        **stats,
        "tipos": pd.Series(
            [r["tipo_actividad"] for r in registros]
        ).value_counts().to_dict(),
        "rango_fechas": {
            "inicio": min(r["fecha"] for r in registros),
            "fin":    max(r["fecha"] for r in registros),
        },
    }
    Path(nombre).write_text(json.dumps(reporte, indent=2, ensure_ascii=False))
    log.info(f"Reporte guardado: {nombre}")
    return reporte


def imprimir_resumen(reporte: dict):
    print("\n" + "=" * 50)
    print(f"  NOA — Resumen de importación")
    print("=" * 50)
    print(f"  Atleta:       {reporte['atleta']}")
    print(f"  Dry-run:      {'SÍ (nada guardado)' if reporte['dry_run'] else 'NO'}")
    print(f"  Total filas:  {reporte['total_filas']}")
    print(f"  Insertados:   {reporte.get('insertados', '-')}")
    print(f"  Duplicados:   {reporte.get('duplicados', '-')}")
    print(f"  Errores:      {reporte.get('errores', '-')}")
    print(f"  Rango:        {reporte['rango_fechas']['inicio'][:10]}  →  {reporte['rango_fechas']['fin'][:10]}")
    print(f"  Por tipo:")
    for tipo, n in sorted(reporte["tipos"].items(), key=lambda x: -x[1]):
        print(f"    {tipo:<15} {n:>4} actividades")
    print("=" * 50 + "\n")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NOA — Importa Activities.csv de Garmin para un atleta nuevo"
    )
    parser.add_argument("--atleta", required=True,
                        help="Nombre/ID del atleta (ej: eugenio, sofia)")
    parser.add_argument("--csv", required=True,
                        help="Ruta al archivo Activities.csv de Garmin")
    parser.add_argument("--db", default=None,
                        help="Cadena de conexión a Postgres/Supabase (default: variable de entorno DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Procesa y valida el CSV pero NO escribe en la DB")
    args = parser.parse_args()

    ruta_csv = Path(args.csv)
    if not ruta_csv.exists():
        log.error(f"CSV no encontrado: {ruta_csv}")
        sys.exit(1)

    log.info(f"=== NOA — Importando actividades para '{args.atleta}' ===")

    # 1. Cargar
    df = cargar_csv(ruta_csv)

    # 2. Transformar
    registros = transformar(df, args.atleta)

    if not registros:
        log.error("No se obtuvieron registros válidos. Revisar el CSV.")
        sys.exit(1)

    # 3. Insertar (o dry-run)
    if args.dry_run:
        log.info("DRY-RUN: no se escribe en la base de datos.")
        stats = {"insertados": 0, "duplicados": 0, "errores": 0}
    else:
        import os
        db_url = args.db or os.environ.get('DATABASE_URL')
        if not db_url:
            log.error("Falta --db o la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
            sys.exit(1)
        conn = inicializar_db(db_url)
        stats = insertar(conn, registros)
        conn.close()

    # 4. Reporte
    reporte = guardar_reporte(args.atleta, stats, registros, args.dry_run)
    imprimir_resumen(reporte)


if __name__ == "__main__":
    main()
