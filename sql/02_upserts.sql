-- =====================================================================
-- SolarBI Pascual - Cargas idempotentes (UPSERT)
-- Referencia: estas son las sentencias que ejecuta etl/run_etl.py.
-- Los %s son parametros que llena psycopg2 (nunca se concatenan valores).
-- =====================================================================

-- 1) Silver: lecturas de 5 minutos
INSERT INTO silver.lectura_5min
    (ts, dispositivo_id, p_ac_kw, irradiancia_wm2, temp_modulo_c, energia_kwh)
VALUES %s
ON CONFLICT (ts, dispositivo_id) DO UPDATE SET
    p_ac_kw         = EXCLUDED.p_ac_kw,
    irradiancia_wm2 = EXCLUDED.irradiancia_wm2,
    temp_modulo_c   = EXCLUDED.temp_modulo_c,
    energia_kwh     = EXCLUDED.energia_kwh,
    cargado_en      = now();

-- 2) Dimension fecha
INSERT INTO dwh.dim_fecha (fecha_key, fecha, anio, mes, dia, nombre_dia)
VALUES %s
ON CONFLICT (fecha_key) DO NOTHING;

-- 3) Dimension dispositivo
INSERT INTO dwh.dim_dispositivo (dispositivo_key, dispositivo_id, nombre, potencia_kwp)
VALUES %s
ON CONFLICT (dispositivo_key) DO UPDATE SET
    nombre = EXCLUDED.nombre, potencia_kwp = EXCLUDED.potencia_kwp;

-- 4) Hecho diario: la clave primaria (fecha_key, dispositivo_key) garantiza
--    que re-ejecutar el ETL actualiza la fila en lugar de duplicarla.
INSERT INTO dwh.fact_energia_dia
    (fecha_key, dispositivo_key, energia_kwh, irradiacion_kwh_m2, potencia_max_kw,
     lecturas_esperadas, lecturas_validas, pct_datos_validos)
VALUES %s
ON CONFLICT (fecha_key, dispositivo_key) DO UPDATE SET
    energia_kwh        = EXCLUDED.energia_kwh,
    irradiacion_kwh_m2 = EXCLUDED.irradiacion_kwh_m2,
    potencia_max_kw    = EXCLUDED.potencia_max_kw,
    lecturas_esperadas = EXCLUDED.lecturas_esperadas,
    lecturas_validas   = EXCLUDED.lecturas_validas,
    pct_datos_validos  = EXCLUDED.pct_datos_validos,
    actualizado_en     = now();
