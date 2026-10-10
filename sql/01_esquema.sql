-- =====================================================================
-- SolarBI Pascual - Esquema en PostgreSQL (Silver y Gold/DWH)
-- Inteligencia de Negocios - Grupo 50 - 2026-II
-- Idempotente: se puede ejecutar varias veces sin error ni duplicados.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS etl;

-- ---------------------------------------------------------------------
-- SILVER: lecturas limpias cada 5 minutos
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.lectura_5min (
    ts               TIMESTAMP     NOT NULL,          -- hora local Colombia (UTC-5)
    dispositivo_id   INTEGER       NOT NULL,
    p_ac_kw          NUMERIC(8,3)  NOT NULL CHECK (p_ac_kw >= 0),
    irradiancia_wm2  NUMERIC(7,1)  NOT NULL CHECK (irradiancia_wm2 >= 0),
    temp_modulo_c    NUMERIC(5,1)  NOT NULL,
    energia_kwh      NUMERIC(10,5) NOT NULL,          -- p_ac_kw * 5/60
    cargado_en       TIMESTAMP     NOT NULL DEFAULT now(),
    CONSTRAINT pk_lectura_5min PRIMARY KEY (ts, dispositivo_id)
);

-- ---------------------------------------------------------------------
-- GOLD / DWH: dimensiones
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_fecha (
    fecha_key    INTEGER PRIMARY KEY,                 -- AAAAMMDD
    fecha        DATE    NOT NULL UNIQUE,
    anio         SMALLINT NOT NULL,
    mes          SMALLINT NOT NULL,
    dia          SMALLINT NOT NULL,
    nombre_dia   VARCHAR(12) NOT NULL
);

CREATE TABLE IF NOT EXISTS dwh.dim_dispositivo (
    dispositivo_key  INTEGER PRIMARY KEY,
    dispositivo_id   INTEGER NOT NULL UNIQUE,         -- id de la fuente
    nombre           VARCHAR(60) NOT NULL,
    tipo             VARCHAR(30) NOT NULL DEFAULT 'Inversor',
    potencia_kwp     NUMERIC(6,2) NOT NULL,           -- potencia pico instalada
    sitio            VARCHAR(60) NOT NULL DEFAULT 'Pascual Bravo - Medellin'
);

-- ---------------------------------------------------------------------
-- GOLD / DWH: hecho diario de energia (granularidad dia x dispositivo)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_energia_dia (
    fecha_key            INTEGER NOT NULL REFERENCES dwh.dim_fecha(fecha_key),
    dispositivo_key      INTEGER NOT NULL REFERENCES dwh.dim_dispositivo(dispositivo_key),
    energia_kwh          NUMERIC(10,3) NOT NULL,
    irradiacion_kwh_m2   NUMERIC(8,3)  NOT NULL,      -- suma irradiancia * 5/60 / 1000
    potencia_max_kw      NUMERIC(8,3)  NOT NULL,
    lecturas_esperadas   INTEGER NOT NULL,            -- 288 por dia
    lecturas_validas     INTEGER NOT NULL,
    pct_datos_validos    NUMERIC(5,2)  NOT NULL,
    actualizado_en       TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT pk_fact_energia_dia PRIMARY KEY (fecha_key, dispositivo_key)
);

-- ---------------------------------------------------------------------
-- Bitacora de calidad: una fila por ejecucion del ETL (linaje / auditoria)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl.log_calidad (
    id_ejecucion           SERIAL PRIMARY KEY,
    ejecutado_en           TIMESTAMP NOT NULL DEFAULT now(),
    archivo_origen         TEXT    NOT NULL,
    filas_leidas           INTEGER NOT NULL,
    rech_duplicados        INTEGER NOT NULL,
    rech_faltantes         INTEGER NOT NULL,
    rech_rango             INTEGER NOT NULL,
    filas_validas          INTEGER NOT NULL,
    pct_datos_validos      NUMERIC(5,2) NOT NULL
);
