-- Consultas de los paneles de Grafana para PostgreSQL.
-- $__timeFilter(col) limita la consulta al rango temporal del dashboard.
-- $dispositivo es la variable multivalor del dashboard e incluye All.

-- Variable dispositivo
SELECT dispositivo_id AS __value, nombre AS __text
FROM dwh.dim_dispositivo
ORDER BY dispositivo_id;

-- Panel 1: irradiancia y potencia AC cada cinco minutos
SELECT ts AS "time",
       irradiancia_wm2 AS "Irradiancia (W/m2)",
       p_ac_kw AS "Potencia AC (kW)"
FROM silver.lectura_5min
WHERE $__timeFilter(ts)
  AND dispositivo_id IN ($dispositivo)
ORDER BY 1;

-- Panel 2: porcentaje de datos validos
SELECT ROUND(
           100.0 * SUM(f.lecturas_validas) /
           NULLIF(SUM(f.lecturas_esperadas), 0),
           2
       ) AS "% datos validos"
FROM dwh.fact_energia_dia f
JOIN dwh.dim_fecha d ON d.fecha_key = f.fecha_key
JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
WHERE $__timeFilter(d.fecha::timestamp)
  AND x.dispositivo_id IN ($dispositivo);

-- Panel 3: energia diaria
SELECT d.fecha::timestamp AS "time",
       SUM(f.energia_kwh) AS "Energia (kWh)"
FROM dwh.fact_energia_dia f
JOIN dwh.dim_fecha d ON d.fecha_key = f.fecha_key
JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
WHERE $__timeFilter(d.fecha::timestamp)
  AND x.dispositivo_id IN ($dispositivo)
GROUP BY 1 ORDER BY 1;

-- Panel 4: Yield acumulado y Performance Ratio
-- La potencia instalada se suma una sola vez por dispositivo.
WITH seleccion AS (
    SELECT dispositivo_key, potencia_kwp
    FROM dwh.dim_dispositivo
    WHERE dispositivo_id IN ($dispositivo)
),
datos AS (
    SELECT
        SUM(f.energia_kwh) AS energia_total,
        SUM(f.irradiacion_kwh_m2 * x.potencia_kwp) AS denominador_pr
    FROM dwh.fact_energia_dia f
    JOIN dwh.dim_fecha d ON d.fecha_key = f.fecha_key
    JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
    WHERE $__timeFilter(d.fecha::timestamp)
      AND x.dispositivo_id IN ($dispositivo)
),
potencia AS (
    SELECT SUM(potencia_kwp) AS potencia_instalada
    FROM seleccion
)
SELECT
    ROUND(datos.energia_total / NULLIF(potencia.potencia_instalada, 0), 2)
        AS "Yield acumulado (kWh/kWp)",
    ROUND(datos.energia_total / NULLIF(datos.denominador_pr, 0), 3)
        AS "Performance Ratio"
FROM datos
CROSS JOIN potencia;
