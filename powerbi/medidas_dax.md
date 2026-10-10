# Power BI · Modelo y medidas DAX (SolarBI · G50)

## 1. Conexión

1. Power BI Desktop → **Obtener datos → Base de datos PostgreSQL**.
2. Servidor: `localhost:5432` · Base de datos: `solarbi` · Modo: **Import**.
3. Credenciales: pestaña *Base de datos*, usuario y clave del `.env` (no se guardan en el repositorio).
4. Seleccionar: `dwh.fact_energia_dia`, `dwh.dim_fecha`, `dwh.dim_dispositivo`
   (opcional `silver.lectura_5min` para un visual de detalle).

## 2. Relaciones (esquema estrella)

| Desde (muchos) | Hacia (uno) | Dirección |
|---|---|---|
| `fact_energia_dia[fecha_key]` | `dim_fecha[fecha_key]` | Única |
| `fact_energia_dia[dispositivo_key]` | `dim_dispositivo[dispositivo_key]` | Única |

Marcar `dim_fecha` como tabla de fechas (columna `fecha`).

## 3. Parámetro de tarifa (What-if)

Modelado → **Nuevo parámetro → Intervalo numérico**:

- Nombre: `Tarifa COP kWh` · Tipo: decimal · Mínimo 500 · Máximo 1500 · Incremento 0.01 · Predeterminado **958.38**
- Fuente de la tarifa: EPM, *Publicación de tarifas de energía, septiembre de 2026, mercado regulado
  Antioquia, propiedad EPM*: CU total 958,38 COP/kWh (equivale a la tarifa residencial estratos 3‑4 por encima
  del consumo de subsistencia). https://www.epm.com.co/clientesyusuarios/energia/tarifas-energia/

Power BI crea la tabla y la medida del parámetro. Si se crea a mano:

```dax
Tarifa COP kWh = GENERATESERIES(500, 1500, 0.01)

Valor Tarifa COP kWh =
SELECTEDVALUE ( 'Tarifa COP kWh'[Tarifa COP kWh], 958.38 )
```

## 4. Medidas (tabla `_Medidas`)

```dax
Energía (kWh) =
SUM ( fact_energia_dia[energia_kwh] )

Potencia instalada (kWp) =
SUM ( dim_dispositivo[potencia_kwp] )

Yield (kWh/kWp) =
DIVIDE ( [Energía (kWh)], [Potencia instalada (kWp)] )

Días con datos =
DISTINCTCOUNT ( fact_energia_dia[fecha_key] )

Yield diario promedio (kWh/kWp/día) =
DIVIDE ( [Yield (kWh/kWp)], [Días con datos] )

Performance Ratio =
DIVIDE (
    [Energía (kWh)],
    SUMX ( fact_energia_dia,
           fact_energia_dia[irradiacion_kwh_m2] * RELATED ( dim_dispositivo[potencia_kwp] ) )
)

% Datos válidos =
DIVIDE ( SUM ( fact_energia_dia[lecturas_validas] ),
         SUM ( fact_energia_dia[lecturas_esperadas] ) )

Ahorro estimado (COP) =
[Energía (kWh)] * [Valor Tarifa COP kWh]
```

Formatos: `Energía` 1 decimal; `Yield` 2 decimales; `Performance Ratio` y `% Datos válidos` porcentaje;
`Ahorro estimado` moneda COP sin decimales.

## 5. Página "Desempeño y ahorro"

| Visual | Campos |
|---|---|
| Tarjeta | `Yield (kWh/kWp)` |
| Tarjeta | `Ahorro estimado (COP)` |
| Segmentador | `Tarifa COP kWh` (para mover la tarifa) |
| Gráfico de columnas | Eje: `dim_fecha[fecha]` · Valores: `Energía (kWh)` |
| Segmentador | `dim_dispositivo[nombre]` |
| Tarjetas opcionales | `% Datos válidos`, `Performance Ratio` |

## 6. Valores esperados con los datos de la semilla 50 (para verificar)

| Medida | Ambos inversores | Inversor 1 | Inversor 2 |
|---|---|---|---|
| Energía (kWh) | 159,0 | 80,95 | 78,07 |
| Yield (kWh/kWp) | 15,90 | 16,19 | 15,61 |
| Yield diario promedio | 5,30 | 5,40 | 5,20 |
| Performance Ratio | 84,9 % | 84,9 % | 84,9 % |
| % Datos válidos | 96,18 % | 95,60 % | 96,76 % |
| Ahorro (COP, 958,38) | 152.400 | 77.584 | 74.816 |
