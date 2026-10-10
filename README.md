# SolarBI Pascual · Power BI y Grafana sobre los mismos datos

> *"One governed dataset, two views: Grafana for real-time operations and Power BI for business decisions."*

**Institución Universitaria Pascual Bravo** · Inteligencia de Negocios · **Grupo 50** · Semestre 2026‑II
Docente: Ramiro Grisales Montoya

| Integrante | Usuario GitHub |
|---|---|
| Yenifer Alenix Medina Salas | @USUARIO_1 |
| NOMBRE COMPLETO COMPAÑERO/A | @USUARIO_2 |

## Descripción

Trabajo de consulta y práctica guiada del proyecto de aula SolarBI Pascual (enfoque del Grupo 50:
**calidad y desempeño**: % de datos válidos, yield y ahorro). Se construye un flujo pequeño pero completo:

```
simulador.py ─► data/bronze/telemetria.csv   (crudo, no se modifica)
                     │  3 reglas de calidad (pandas)
                     ▼
               data/silver/lectura_5min.csv + reporte_calidad.json
                     │  UPSERT idempotente (PostgreSQL)
                     ▼
   silver.lectura_5min ── dwh.fact_energia_dia + dim_fecha + dim_dispositivo
             │                         │
          Grafana (operación,       Power BI (desempeño y
          series de 5 min)          ahorro, medidas DAX)
```

## Estructura

```
solarbi-apellido1-apellido2/
├── README.md
├── .gitignore            # excluye .env y archivos locales
├── .env.example          # plantilla de variables (sin claves reales)
├── docker-compose.yml    # PostgreSQL 16 + Grafana OSS
├── requirements.txt
├── docs/                 # PDF de la consulta y capturas
├── data/bronze/          # telemetria.csv (crudo)
├── data/silver/          # lectura_5min.csv, reporte_calidad.json
├── etl/                  # simulador.py, run_etl.py
├── sql/                  # 01_esquema.sql, 02_upserts.sql, 03_consultas_grafana.sql
├── powerbi/              # SolarBI_G50.pbip / .pbix y medidas_dax.md
└── grafana/              # dashboard.json exportado + provisioning/
```

## Cómo reproducir la práctica

Requisitos: Python 3.10+, Docker Desktop (o PostgreSQL 16 y Grafana OSS instalados), Power BI Desktop.

```bash
# 1. Clonar e instalar dependencias
git clone https://github.com/USUARIO_1/solarbi-apellido1-apellido2.git
cd solarbi-apellido1-apellido2
pip install -r requirements.txt

# 2. Variables de entorno (la clave real va solo en .env, que Git ignora)
cp .env.example .env          # Windows: copy .env.example .env
#   editar .env y cambiar PGPASSWORD y GF_ADMIN_PASSWORD

# 3. Levantar PostgreSQL y Grafana
docker compose up -d

# 4. Ejecutar el ETL (un solo comando). Ejecutarlo dos veces: los conteos no cambian.
python etl/run_etl.py
python etl/run_etl.py
```

5. **Grafana:** http://localhost:3000 (usuario `admin`). El data source *SolarBI PostgreSQL* y el
   dashboard *SolarBI Pascual – Operación y calidad (G50)* se cargan solos (carpeta `grafana/provisioning`).
   Si Grafana se instaló sin Docker: *Connections → Data sources → PostgreSQL* (host `localhost:5432`,
   base `solarbi`) y *Dashboards → New → Import* con `grafana/dashboard.json`.
6. **Power BI:** seguir `powerbi/medidas_dax.md`.

### Resultados de referencia (semilla 50, 2 inversores de 5 kWp, 5–7 oct. 2026)

| Métrica | Valor |
|---|---|
| Filas leídas (Bronze) | 1.768 |
| R1 · duplicados | 40 |
| R2 · faltantes | 30 |
| R3 · fuera de rango (potencia negativa) | 36 |
| Filas válidas (Silver) | 1.662 |
| % datos válidos (sobre filas leídas) | 94,00 % |
| % datos válidos (sobre 288 lecturas esperadas por día) | 96,18 % |
| Energía total | 159,02 kWh |
| Yield del periodo / diario | 15,90 kWh/kWp · 5,30 kWh/kWp/día |
| Performance Ratio | 84,9 % |
| Ahorro estimado (958,38 COP/kWh, EPM sep. 2026) | 152.400 COP |

### Reglas de calidad (Silver)

| Regla | Qué valida | Acción |
|---|---|---|
| R1 · Duplicados | Misma pareja (`ts`, `dispositivo_id`) | Se conserva la primera |
| R2 · Faltantes / formato | Campo vacío o no numérico / fecha inválida | Se rechaza la fila |
| R3 · Rango físico | `0 ≤ p_ac_kw ≤ 5,5` · `0 ≤ irradiancia ≤ 1500 W/m²` · `−10 ≤ temp ≤ 90 °C` | Se rechaza la fila |

La energía de cada intervalo es `p_ac_kw × 5/60` h. Las reglas se aplican en orden (R1 → R2 → R3),
así cada fila rechazada se cuenta en una sola regla.

### Idempotencia

Cada tabla tiene clave primaria (`silver.lectura_5min`: `ts, dispositivo_id`; `dwh.fact_energia_dia`:
`fecha_key, dispositivo_key`) y la carga usa `INSERT … ON CONFLICT … DO UPDATE`. Re‑ejecutar el ETL
actualiza las mismas filas en vez de duplicarlas. Solo `etl.log_calidad` crece una fila por ejecución,
porque es la bitácora de auditoría.

### Programación diaria (no implementada)

```cron
# cron (Linux/macOS): todos los días a las 00:00
0 0 * * * cd /ruta/solarbi-apellido1-apellido2 && /usr/bin/python3 etl/run_etl.py >> logs/etl.log 2>&1
```

```bat
:: Programador de tareas de Windows
schtasks /create /tn "SolarBI_ETL" /sc daily /st 00:00 ^
  /tr "cmd /c cd /d C:\ruta\solarbi-apellido1-apellido2 && python etl\run_etl.py >> logs\etl.log 2>&1"
```

## Cambios frente al simulador base

- Semilla fija (`--semilla 50`) para que los dos integrantes obtengan los mismos datos.
- Opción `--dispositivos` (por defecto 2) para que la variable *Dispositivo* de Grafana tenga sentido.
  Con `python etl/simulador.py --dispositivos 1 --forzar` se vuelve al caso de un solo inversor.

## Seguridad

No se suben contraseñas ni cadenas de conexión: el ETL, Docker y Grafana leen las credenciales de
variables de entorno (`.env`, excluido por `.gitignore`). Los datos son técnicos (telemetría de
equipos), sin datos personales (Ley 1581 de 2012).

## Quién hizo qué

| Tarea | Responsable |
|---|---|
| Consulta Bloques 1 y 2 (Power BI/Grafana, gobernanza) | |
| Consulta Bloques 3, 4 y 5 (ETL, IoT, versiones) | |
| Simulador y reglas de calidad (Silver) | |
| Esquema SQL y carga idempotente (Gold) | |
| Informe Power BI y medidas DAX | |
| Dashboard Grafana y exportación JSON | |
| README, revisión y PDF final | |
