-- =====================================================================
-- Consultas usadas en los paneles de Grafana (data source PostgreSQL)
-- $__timeFilter(col) : macro de Grafana -> col BETWEEN inicio AND fin del rango
-- $dispositivo       : variable de dashboard (multi-valor, incluye "All")
-- =====================================================================

-- Variable "dispositivo" (Dashboard settings > Variables > Query)
SELECT dispositivo_id AS __value, nombre AS __text
FROM dwh.dim_dispositivo ORDER BY dispositivo_id;

-- Panel 1 - Time series: irradiancia y potencia cada 5 minutos
SELECT ts AS "time",
       irradiancia_wm2 AS "Irradiancia (W/m2)",
       p_ac_kw         AS "Potencia AC (kW)"
FROM silver.lectura_5min
WHERE $__timeFilter(ts)
  AND dispositivo_id IN ($dispositivo)
ORDER BY 1;

-- Panel 2 - Stat/Gauge: % de datos validos en el rango elegido
SELECT ROUND(100.0 * SUM(f.lecturas_validas) / NULLIF(SUM(f.lecturas_esperadas), 0), 2)
       AS "% datos validos"
FROM dwh.fact_energia_dia f
JOIN dwh.dim_fecha d       ON d.fecha_key = f.fecha_key
JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
WHERE $__timeFilter(d.fecha::timestamp)
  AND x.dispositivo_id IN ($dispositivo);

-- Panel 3 - Bar chart: energia diaria (kWh)
SELECT d.fecha::timestamp AS "time", SUM(f.energia_kwh) AS "Energia (kWh)"
FROM dwh.fact_energia_dia f
JOIN dwh.dim_fecha d       ON d.fecha_key = f.fecha_key
JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
WHERE $__timeFilter(d.fecha::timestamp)
  AND x.dispositivo_id IN ($dispositivo)
GROUP BY 1 ORDER BY 1;

-- Panel 4 - Stat: yield diario promedio (kWh/kWp por dia) y Performance Ratio en el rango
SELECT ROUND(SUM(f.energia_kwh) / SUM(x.potencia_kwp), 2) AS "Yield diario promedio (kWh/kWp)",
       ROUND(SUM(f.energia_kwh) / NULLIF(SUM(x.potencia_kwp * f.irradiacion_kwh_m2), 0), 3) AS "PR"
FROM dwh.fact_energia_dia f
JOIN dwh.dim_fecha d       ON d.fecha_key = f.fecha_key
JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
WHERE $__timeFilter(d.fecha::timestamp)
  AND x.dispositivo_id IN ($dispositivo);
