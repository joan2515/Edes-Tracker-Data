import hashlib
import json
import re
from bs4 import BeautifulSoup
import requests

URL_EDESUR = (
    "https://www.edesur.com.do/enlaces-empresa/mantenimientos-programados/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def limpiar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def extraer_mantenimientos_edesur():
    """Extrae los mantenimientos respetando la estructura de acordeones y tabs de Edesur."""
    print("[*] Consultando portal de Edesur...")
    try:
        response = requests.get(URL_EDESUR, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Error al descargar la página de Edesur: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    registros = []

    # 1. Extraer los días (tabs/botones) vinculados por contenedor
    accordions = soup.find_all("div", class_=lambda c: c and "accordion" in c)

    for acc in accordions:
        fecha_texto = "Semana actual"
        tab_parent = acc.find_parent(
            "div", class_=lambda c: c and ("tab-pane" in c or "fade" in c)
        )
        if tab_parent and tab_parent.get("id"):
            boton_tab = soup.find(
                attrs={"data-bs-target": f"#{tab_parent.get('id')}"}
            ) or soup.find(attrs={"href": f"#{tab_parent.get('id')}"})
            if boton_tab:
                fecha_texto = limpiar_texto(boton_tab.get_text())

        # 2. Recorrer cada item del acordeón (Provincias)
        items = acc.find_all(
            "div", class_=lambda c: c and "accordion-item" in c
        )
        for item in items:
            h4_tag = item.find("h4")
            provincia = (
                limpiar_texto(h4_tag.get_text()) if h4_tag else "Santo Domingo"
            )

            body = item.find(
                "div", class_=lambda c: c and "accordion-body" in c
            )
            if not body:
                continue

            titulos_zona = body.find_all(
                "h5", class_=lambda c: c and "title-zona" in c
            )

            for tz in titulos_zona:
                texto_horario = limpiar_texto(tz.get_text())

                # Extraer rango de hora (ej: "09:00 a. m. a 02:00 p. m.")
                horario_match = re.search(
                    r"(\d{1,2}:\d{2}\s*(?:a\.\s*m\.|p\.\s*m\.)\s*a\s*\d{1,2}:\d{2}\s*(?:a\.\s*m\.|p\.\s*m\.))",
                    texto_horario,
                    re.IGNORECASE,
                )
                horario = (
                    horario_match.group(1) if horario_match else texto_horario
                )

                # El texto de sectores es el siguiente párrafo <p> no vacío
                parrafo_sectores = tz.find_next_sibling("p")
                while parrafo_sectores and not limpiar_texto(
                    parrafo_sectores.get_text()
                ):
                    parrafo_sectores = parrafo_sectores.find_next_sibling("p")

                cadena_sectores = (
                    limpiar_texto(parrafo_sectores.get_text())
                    if parrafo_sectores
                    else ""
                )

                # Separar los sectores por coma para granularidad en la app
                lista_sectores = [
                    s.strip() for s in cadena_sectores.split(",") if s.strip()
                ]

                for sector_individual in lista_sectores:
                    id_raw = f"{provincia}-{sector_individual}-{fecha_texto}-{horario}"
                    id_hash = hashlib.md5(id_raw.encode("utf-8")).hexdigest()[
                        :10
                    ]

                    registros.append({
                        "id": f"edesur_{id_hash}",
                        "distribuidora": "EDESUR",
                        "provincia": provincia,
                        "municipio": provincia,
                        "circuito": "Circuito Edesur",
                        "sector": sector_individual,
                        "fecha": fecha_texto,
                        "horario": horario,
                        "motivo": "Mantenimiento preventivo",
                    })

    print(f"[✓] Edesur: {len(registros)} sectores con mantenimientos extraídos.")
    return registros


# Alias para retrocompatibilidad con el nombre anterior
parsear_mantenimientos = extraer_mantenimientos_edesur


def main():
    datos = extraer_mantenimientos_edesur()
    with open("mantenimientos_edesur.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print("[✓] Guardado en mantenimientos_edesur.json")


if __name__ == "__main__":
    main()
