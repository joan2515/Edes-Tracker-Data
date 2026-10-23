import json
import re
from bs4 import BeautifulSoup
import requests

URL_EDESUR = "https://edesur.com.do/interrupciones-programadas/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def limpiar_texto(valor):
    if not valor:
        return ""
    return " ".join(str(valor).replace("\n", " ").split()).strip()


def extraer_mantenimientos_edesur():
    """Consulta la tabla oficial de interrupciones programadas de Edesur y devuelve una lista estandarizada."""
    print("[*] Consultando portal de Edesur...")
    resp = requests.get(URL_EDESUR, headers=HEADERS, timeout=25)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    mantenimientos = []
    contador_id = 1

    # Localizar la tabla principal de Edesur
    tabla = soup.find("table")
    if not tabla:
        print("[!] No se encontró tabla en la página de Edesur.")
        return mantenimientos

    filas = tabla.find_all("tr")
    if len(filas) < 2:
        return mantenimientos

    # Detección de índices según cabecera
    indices = {
        "circuito": 0,
        "provincia": 1,
        "municipio": 2,
        "sector": 3,
        "fecha": 4,
        "horario": 5,
        "motivo": 6,
    }

    cabecera = [limpiar_texto(th.get_text()).lower() for th in filas[0].find_all(["th", "td"])]
    if cabecera:
        for idx, col in enumerate(cabecera):
            if "circuito" in col:
                indices["circuito"] = idx
            elif "provincia" in col:
                indices["provincia"] = idx
            elif "municipio" in col:
                indices["municipio"] = idx
            elif "sector" in col or "zona" in col:
                indices["sector"] = idx
            elif "fecha" in col:
                indices["fecha"] = idx
            elif "hora" in col or "periodo" in col:
                indices["horario"] = idx
            elif "motivo" in col or "trabajo" in col or "causa" in col:
                indices["motivo"] = idx

    for fila in filas[1:]:
        columnas = [limpiar_texto(td.get_text()) for td in fila.find_all(["td", "th"])]
        if not columnas or len(columnas) < 4:
            continue

        def obtener(clave, def_val="N/A"):
            pos = indices.get(clave)
            if pos is not None and pos < len(columnas) and columnas[pos]:
                return columnas[pos]
            return def_val

        sector = obtener("sector")
        circuito = obtener("circuito")
        if sector in ["", "N/A"] and circuito in ["", "N/A"]:
            continue

        prov = obtener("provincia", "Santo Domingo")
        mun = obtener("municipio", prov)

        mantenimientos.append({
            "id": f"edesur_{contador_id}",
            "distribuidora": "EDESUR",
            "provincia": prov,
            "municipio": mun,
            "circuito": circuito,
            "sector": sector,
            "fecha": obtener("fecha"),
            "horario": obtener("horario"),
            "motivo": obtener("motivo", "Mantenimiento preventivo"),
        })
        contador_id += 1

    print(f"[✓] Edesur: {len(mantenimientos)} cortes extraídos.")
    return mantenimientos


if __name__ == "__main__":
    datos = extraer_mantenimientos_edesur()
    with open("mantenimientos_edesur.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
