"""Genera grafana/dashboard.json (se ejecuta una vez; el JSON es el que se versiona)."""
import json, pathlib

DS = {"type": "grafana-postgresql-datasource", "uid": "solarbi-pg"}

def target(sql, fmt="table", ref="A"):
    return {"datasource": DS, "refId": ref, "rawQuery": True, "editorMode": "code",
            "format": fmt, "rawSql": sql}

TS = """SELECT ts AS "time",
       irradiancia_wm2 AS "Irradiancia (W/m2)",
       p_ac_kw AS "Potencia AC (kW)"
FROM silver.lectura_5min
WHERE $__timeFilter(ts) AND dispositivo_id IN ($dispositivo)
ORDER BY 1"""
FROM_FACT = """FROM dwh.fact_energia_dia f
JOIN dwh.dim_fecha d ON d.fecha_key = f.fecha_key
JOIN dwh.dim_dispositivo x ON x.dispositivo_key = f.dispositivo_key
WHERE $__timeFilter(d.fecha::timestamp) AND x.dispositivo_id IN ($dispositivo)"""
PCT = 'SELECT ROUND(100.0*SUM(f.lecturas_validas)/NULLIF(SUM(f.lecturas_esperadas),0),2) AS "% datos validos"\n' + FROM_FACT
ENERGIA = 'SELECT d.fecha::timestamp AS "time", SUM(f.energia_kwh) AS "Energia (kWh)"\n' + FROM_FACT + "\nGROUP BY 1 ORDER BY 1"
YIELD = 'SELECT ROUND(SUM(f.energia_kwh)/SUM(x.potencia_kwp),2) AS "Yield diario promedio (kWh/kWp)",\n       ROUND(SUM(f.energia_kwh)/NULLIF(SUM(x.potencia_kwp*f.irradiacion_kwh_m2),0),3) AS "Performance Ratio"\n' + FROM_FACT

panels = [
    {"id": 1, "type": "timeseries", "title": "Irradiancia y potencia AC (cada 5 min)",
     "datasource": DS, "gridPos": {"h": 10, "w": 24, "x": 0, "y": 0},
     "targets": [target(TS, "time_series")],
     "fieldConfig": {"defaults": {"custom": {"lineWidth": 1, "fillOpacity": 10}},
                     "overrides": [
                         {"matcher": {"id": "byRegexp", "options": ".*Potencia.*"},
                          "properties": [{"id": "unit", "value": "kwatt"},
                                         {"id": "custom.axisPlacement", "value": "right"},
                                         {"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}}]},
                         {"matcher": {"id": "byRegexp", "options": ".*Irradiancia.*"},
                          "properties": [{"id": "unit", "value": "W/m²"},
                                         {"id": "color", "value": {"mode": "fixed", "fixedColor": "yellow"}}]}]},
     "options": {"legend": {"displayMode": "list", "placement": "bottom"},
                 "tooltip": {"mode": "multi"}}},
    {"id": 2, "type": "gauge", "title": "% de datos validos",
     "description": "Lecturas validas / lecturas esperadas (288 por dia y dispositivo). Umbrales: <90 rojo, 90-95 amarillo, >=95 verde.",
     "datasource": DS, "gridPos": {"h": 8, "w": 8, "x": 0, "y": 10},
     "targets": [target(PCT)],
     "fieldConfig": {"defaults": {"unit": "percent", "min": 0, "max": 100, "decimals": 2,
                                  "thresholds": {"mode": "absolute", "steps": [
                                      {"color": "red", "value": None},
                                      {"color": "yellow", "value": 90},
                                      {"color": "green", "value": 95}]}},
                     "overrides": []},
     "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                 "showThresholdMarkers": True, "showThresholdLabels": False}},
    {"id": 3, "type": "barchart", "title": "Energia diaria (kWh)",
     "datasource": DS, "gridPos": {"h": 8, "w": 10, "x": 8, "y": 10},
     "targets": [target(ENERGIA)],
     "fieldConfig": {"defaults": {"unit": "kwatth", "decimals": 1,
                                  "color": {"mode": "fixed", "fixedColor": "green"}}, "overrides": []},
     "options": {"xField": "time", "showValue": "always", "legend": {"showLegend": False},
                 "xTickLabelRotation": 0}},
    {"id": 4, "type": "stat", "title": "Yield y Performance Ratio",
     "datasource": DS, "gridPos": {"h": 8, "w": 6, "x": 18, "y": 10},
     "targets": [target(YIELD)],
     "fieldConfig": {"defaults": {"decimals": 2,
                                  "thresholds": {"mode": "absolute", "steps": [{"color": "blue", "value": None}]}},
                     "overrides": [{"matcher": {"id": "byName", "options": "Performance Ratio"},
                                    "properties": [{"id": "unit", "value": "percentunit"},
                                                   {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                                                       {"color": "red", "value": None},
                                                       {"color": "yellow", "value": 0.7},
                                                       {"color": "green", "value": 0.8}]}}]}]},
     "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                 "orientation": "vertical", "colorMode": "value", "textMode": "value_and_name"}},
]

dashboard = {
    "uid": "solarbi-g50", "title": "SolarBI Pascual - Operacion y calidad (G50)",
    "tags": ["solarbi", "iot", "calidad"], "timezone": "utc",
    "schemaVersion": 39, "version": 1, "editable": True, "refresh": "1m",
    "time": {"from": "2026-10-05T00:00:00.000Z", "to": "2026-10-08T00:00:00.000Z"},
    "timepicker": {"refresh_intervals": ["30s", "1m", "5m", "15m", "1h"]},
    "templating": {"list": [{
        "name": "dispositivo", "label": "Dispositivo", "type": "query", "datasource": DS,
        "query": "SELECT dispositivo_id AS __value, nombre AS __text FROM dwh.dim_dispositivo ORDER BY dispositivo_id",
        "definition": "SELECT dispositivo_id AS __value, nombre AS __text FROM dwh.dim_dispositivo ORDER BY dispositivo_id",
        "refresh": 1, "multi": True, "includeAll": True,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "sort": 0}]},
    "annotations": {"list": []},
    "panels": panels,
}
out = pathlib.Path(__file__).with_name("dashboard.json")
out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")
print("escrito", out)
