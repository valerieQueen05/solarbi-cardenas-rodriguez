"""
SolarBI Pascual - Simulador de telemetria (capa Bronze).

Basado en el simulador del curso (Inteligencia de Negocios, Grupo 50).
Genera 3 dias de telemetria cada 5 minutos de inversores de 5 kWp con
anomalias inyectadas: potencia negativa (~2 %), irradiancia faltante (~2 %)
y filas duplicadas (~2 %).

Cambios frente al simulador base (documentados en el README):
  * semilla fija (--semilla) para que la practica sea reproducible;
  * opcion --dispositivos para simular mas de un inversor y poder probar
    la variable de dashboard de Grafana (por defecto 2).

Uso:
    python etl/simulador.py                 # 2 inversores, semilla 50
    python etl/simulador.py --dispositivos 1
    python etl/simulador.py --forzar        # sobrescribe el Bronze existente

El archivo de Bronze NO se modifica despues de generado: si ya existe,
el script no hace nada salvo que se pase --forzar.
"""
import argparse
import csv
import math
import os
import random
from datetime import datetime, timedelta

RUTA_BRONZE = os.path.join("data", "bronze", "telemetria.csv")
INICIO = datetime(2026, 10, 5, 0, 0)
DIAS = 3
INTERVALOS_DIA = 288  # 24 h * 12 lecturas por hora


def generar(dispositivos: int, semilla: int, ruta: str = RUTA_BRONZE) -> int:
    random.seed(semilla)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    filas_escritas = 0
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts", "dispositivo_id", "p_ac_kw", "irradiancia_wm2", "temp_modulo_c"])
        for i in range(DIAS * INTERVALOS_DIA):  # 3 dias, cada 5 min
            ts = INICIO + timedelta(minutes=5 * i)
            sol = max(0.0, math.sin(math.pi * (ts.hour + ts.minute / 60 - 6) / 12))
            for disp in range(1, dispositivos + 1):
                irr = round(1000 * sol * random.uniform(0.7, 1.0), 1)
                p_ac = round(5.0 * irr / 1000 * random.uniform(0.80, 0.90), 3)
                fila = [ts.isoformat(sep=" "), disp, p_ac, irr, round(22 + 30 * sol, 1)]
                r = random.random()
                if r < 0.02:
                    fila[2] = -1  # anomalia: potencia negativa
                elif r < 0.04:
                    fila[3] = ""  # anomalia: dato faltante
                w.writerow(fila)
                filas_escritas += 1
                if r > 0.98:
                    w.writerow(fila)  # anomalia: fila duplicada
                    filas_escritas += 1
    return filas_escritas


def main() -> None:
    p = argparse.ArgumentParser(description="Simulador de telemetria SolarBI (Bronze)")
    p.add_argument("--dispositivos", type=int, default=2)
    p.add_argument("--semilla", type=int, default=50)
    p.add_argument("--forzar", action="store_true", help="sobrescribir el Bronze existente")
    a = p.parse_args()

    if os.path.exists(RUTA_BRONZE) and not a.forzar:
        print(f"[simulador] {RUTA_BRONZE} ya existe; no se modifica (use --forzar).")
        return
    n = generar(a.dispositivos, a.semilla)
    print(f"[simulador] {n} filas escritas en {RUTA_BRONZE}")


if __name__ == "__main__":
    main()
