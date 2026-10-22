import hashlib
import json
import re
import requests
from bs4 import BeautifulSoup

URL_EDESUR = "https://www.edesur.com.do/enlaces-empresa/mantenimientos-programados/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def parsear_mantenimientos():
    try:
        response = requests.get(URL_EDESUR, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error al descargar la página de Edesur: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    registros = []

    # Localizar tablas de mantenimientos en el HTML
    tablas = soup.find_all("table")

    for tabla in tablas:
        filas = tabla.find_all("tr")
        if not filas:
            continue

        # Leer encabezados para mapear dinámicamente las columnas
        encabezados = [
            th.get_text(strip=True).lower() for th in filas[0].find_all(["th", "td"])
        ]

        for fila in filas[1:]:
            celdas = fila.find_all("td")
            if len(celdas) < 3:
                continue

            valores = [c.get_text(strip=True) for c in celdas]

            # Mapeo de columnas comunes en publicaciones de EDESUR
            # (Circuito, Provincia/Municipio, Sectores, Fecha, Horario, Causa)
            circuito = valores[0] if len(valores) > 0 else "N/A"
            municipio = valores[1] if len(valores) > 1 else "N/A"
            sector = valores[2] if len(valores) > 2 else "N/A"
            fecha = valores[3] if len(valores) > 3 else "N/A"
            horario = valores[4] if len(valores) > 4 else "N/A"
            motivo = valores[5] if len(valores) > 5 else "Mantenimiento general"

            # Generar un ID único determinista con hash para evitar duplicados en la app
            id_raw = f"{circuito}-{sector}-{fecha}-{horario}"
            id_mantenimiento = hashlib.md5(id_raw.encode("utf-8")).hexdigest()[:10]

            registros.append(
                {
                    "id": id_mantenimiento,
                    "sector": sector,
                    "municipio": municipio,
                    "circuito": circuito,
                    "fecha": fecha,
                    "horario": horario,
                    "motivo": motivo,
                }
            )

    return registros


def main():
    datos = parsear_mantenimientos()

    # Si la estructura de la web cambia o la tabla está vacía temporalmente,
    # se mantiene un fallback para evitar un JSON corrupto.
    if not datos:
        print("Aviso: No se encontraron tablas activas o el formato cambió.")

    with open("mantenimientos.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print(
        f"Proceso finalizado. Total de registros exportados: {len(datos)}"
    )


if __name__ == "__main__":
    main()