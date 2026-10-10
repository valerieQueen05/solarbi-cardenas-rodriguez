"""
SolarBI Pascual - Punto de entrada unico del ETL (Bronze -> Silver -> Gold).

    python etl/run_etl.py

Pasos:
  1. Bronze : si data/bronze/telemetria.csv no existe, lo genera el simulador.
              El archivo crudo nunca se modifica.
  2. Silver : aplica 3 reglas de calidad (duplicados, faltantes, rango fisico),
              guarda data/silver/lectura_5min.csv y data/silver/reporte_calidad.json.
  3. Gold   : crea las tablas si no existen (sql/01_esquema.sql) y carga con
              UPSERT (sql/02_upserts.sql) silver.lectura_5min, las dimensiones
              y dwh.fact_energia_dia. Al final imprime los conteos de cada tabla.

La carga es idempotente: ejecutar el script N veces deja los mismos conteos,
porque cada tabla tiene clave primaria y se usa INSERT ... ON CONFLICT DO UPDATE.

Conexion: variables de entorno (o archivo .env, que NO se sube a GitHub):
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "etl"))
os.chdir(RAIZ)  # rutas relativas a la raiz del repositorio

import simulador  # noqa: E402

try:  # .env opcional
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

BRONZE = RAIZ / "data" / "bronze" / "telemetria.csv"
SILVER_CSV = RAIZ / "data" / "silver" / "lectura_5min.csv"
REPORTE = RAIZ / "data" / "silver" / "reporte_calidad.json"

# --- Contrato de datos (resumen): rangos fisicos validos -------------------
POTENCIA_KWP = 5.0                      # potencia pico de cada inversor
RANGOS = {
    "p_ac_kw":         (0.0, POTENCIA_KWP * 1.1),  # no negativa, <= 110 % de kWp
    "irradiancia_wm2": (0.0, 1500.0),             # irradiancia terrestre maxima
    "temp_modulo_c":   (-10.0, 90.0),             # temperatura de modulo FV
}
LECTURAS_ESPERADAS_DIA = 288            # 24 h x 12 lecturas por hora
HORAS_INTERVALO = 5 / 60                # 5 minutos expresados en horas
DIAS_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


# ===========================================================================
# BRONZE
# ===========================================================================
def asegurar_bronze() -> None:
    if not BRONZE.exists():
        n = simulador.generar(dispositivos=2, semilla=50, ruta=str(BRONZE))
        print(f"[bronze] generado {BRONZE.relative_to(RAIZ)} ({n} filas)")
    else:
        print(f"[bronze] usando {BRONZE.relative_to(RAIZ)} (sin modificar)")


# ===========================================================================
# SILVER: reglas de calidad
# ===========================================================================
def limpiar(crudo: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = crudo.copy()
    leidas = len(df)

    # Regla 1 - Duplicados: misma (ts, dispositivo_id) -> se conserva la primera.
    dup = df.duplicated(subset=["ts", "dispositivo_id"], keep="first")
    df = df[~dup]

    # Regla 2 - Faltantes / formato: cualquier campo vacio o no convertible.
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    for c in ["dispositivo_id", *RANGOS]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    falt = df[["ts", "dispositivo_id", *RANGOS]].isna().any(axis=1)
    df = df[~falt]

    # Regla 3 - Rango fisico valido (contrato de datos).
    fuera = pd.Series(False, index=df.index)
    for c, (lo, hi) in RANGOS.items():
        fuera |= ~df[c].between(lo, hi)
    df = df[~fuera].copy()

    df["dispositivo_id"] = df["dispositivo_id"].astype(int)
    df["energia_kwh"] = (df["p_ac_kw"] * HORAS_INTERVALO).round(5)
    df = df.sort_values(["ts", "dispositivo_id"]).reset_index(drop=True)

    reporte = {
        "ejecutado_en": datetime.now().isoformat(timespec="seconds"),
        "archivo_origen": str(BRONZE.relative_to(RAIZ)),
        "filas_leidas": leidas,
        "rechazadas": {
            "R1_duplicados": int(dup.sum()),
            "R2_faltantes": int(falt.sum()),
            "R3_fuera_de_rango": int(fuera.sum()),
        },
        "filas_validas": len(df),
        "pct_datos_validos": round(100 * len(df) / leidas, 2),
    }
    return df, reporte


def resumen_diario(df: pd.DataFrame) -> pd.DataFrame:
    d = df.assign(fecha=df["ts"].dt.date)
    g = d.groupby(["fecha", "dispositivo_id"]).agg(
        energia_kwh=("energia_kwh", "sum"),
        irradiacion_kwh_m2=("irradiancia_wm2", lambda s: s.sum() * HORAS_INTERVALO / 1000),
        potencia_max_kw=("p_ac_kw", "max"),
        lecturas_validas=("p_ac_kw", "size"),
    ).reset_index()
    g["lecturas_esperadas"] = LECTURAS_ESPERADAS_DIA
    g["pct_datos_validos"] = (100 * g["lecturas_validas"] / LECTURAS_ESPERADAS_DIA).round(2)
    g["fecha_key"] = pd.to_datetime(g["fecha"]).dt.strftime("%Y%m%d").astype(int)
    return g


# ===========================================================================
# GOLD: carga en PostgreSQL
# ===========================================================================
def conectar():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "solarbi"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def sentencias_upsert() -> list[str]:
    texto = (RAIZ / "sql" / "02_upserts.sql").read_text(encoding="utf-8")
    sin_coment = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in sin_coment.split(";") if s.strip()]


def cargar(df: pd.DataFrame, diario: pd.DataFrame, reporte: dict) -> None:
    up_lectura, up_fecha, up_disp, up_fact = sentencias_upsert()
    with conectar() as con, con.cursor() as cur:
        cur.execute((RAIZ / "sql" / "01_esquema.sql").read_text(encoding="utf-8"))

        filas = [(r.ts.to_pydatetime(), int(r.dispositivo_id), float(r.p_ac_kw),
                  float(r.irradiancia_wm2), float(r.temp_modulo_c), float(r.energia_kwh))
                 for r in df.itertuples()]
        execute_values(cur, up_lectura, filas, page_size=1000)

        fechas = sorted(diario["fecha"].unique())
        execute_values(cur, up_fecha, [
            (int(f.strftime("%Y%m%d")), f, f.year, f.month, f.day, DIAS_ES[f.weekday()])
            for f in fechas])

        disps = sorted(diario["dispositivo_id"].unique())
        execute_values(cur, up_disp, [
            (int(d), int(d), f"Inversor {int(d)}", POTENCIA_KWP) for d in disps])

        execute_values(cur, up_fact, [
            (int(r.fecha_key), int(r.dispositivo_id), round(float(r.energia_kwh), 3),
             round(float(r.irradiacion_kwh_m2), 3), float(r.potencia_max_kw),
             int(r.lecturas_esperadas), int(r.lecturas_validas), float(r.pct_datos_validos))
            for r in diario.itertuples()])

        rc = reporte["rechazadas"]
        cur.execute(
            """INSERT INTO etl.log_calidad (archivo_origen, filas_leidas, rech_duplicados,
                   rech_faltantes, rech_rango, filas_validas, pct_datos_validos)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (reporte["archivo_origen"], reporte["filas_leidas"], rc["R1_duplicados"],
             rc["R2_faltantes"], rc["R3_fuera_de_rango"], reporte["filas_validas"],
             reporte["pct_datos_validos"]))

        print("\n[gold] conteos en PostgreSQL")
        for t in ["silver.lectura_5min", "dwh.dim_fecha", "dwh.dim_dispositivo",
                  "dwh.fact_energia_dia", "etl.log_calidad"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"   {t:<24} {cur.fetchone()[0]:>6} filas")
        cur.execute("SELECT ROUND(SUM(energia_kwh), 3) FROM dwh.fact_energia_dia")
        print(f"   energia total en fact   {cur.fetchone()[0]} kWh")


def main() -> None:
    asegurar_bronze()
    crudo = pd.read_csv(BRONZE, dtype=str, keep_default_na=False, na_values=[""])
    df, reporte = limpiar(crudo)
    diario = resumen_diario(df)

    SILVER_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SILVER_CSV, index=False)
    REPORTE.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")

    rc = reporte["rechazadas"]
    print("\n[silver] reporte de calidad")
    print(f"   filas leidas             {reporte['filas_leidas']:>6}")
    print(f"   R1 duplicados            {rc['R1_duplicados']:>6}")
    print(f"   R2 faltantes             {rc['R2_faltantes']:>6}")
    print(f"   R3 fuera de rango        {rc['R3_fuera_de_rango']:>6}")
    print(f"   filas validas            {reporte['filas_validas']:>6}")
    print(f"   % datos validos          {reporte['pct_datos_validos']:>6.2f} %")

    cargar(df, diario, reporte)
    print("\n[ok] ETL terminado")


if __name__ == "__main__":
    main()
