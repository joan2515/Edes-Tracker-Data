import json
import traceback

from scraper_edesur import extraer_mantenimientos_edesur
from scraper_edeeste import extraer_datos_edeeste
from scraper_edenorte import extraer_datos_edenorte


def consolidar_todo():
    mantenimientos_totales = []

    # 1. Edesur
    print("=" * 50)
    print("[1/3] Procesando Edesur...")
    try:
        datos_edesur = extraer_mantenimientos_edesur()
        mantenimientos_totales.extend(datos_edesur)
    except Exception as e:
        print(f"[!] Error crítico en Edesur: {e}")
        traceback.print_exc()

    # 2. Edeeste
    print("=" * 50)
    print("[2/3] Procesando Edeeste...")
    try:
        datos_edeeste = extraer_datos_edeeste()
        mantenimientos_totales.extend(datos_edeeste)
    except Exception as e:
        print(f"[!] Error crítico en Edeeste: {e}")
        traceback.print_exc()

    # 3. EdeNorte
    print("=" * 50)
    print("[3/3] Procesando EdeNorte...")
    try:
        datos_edenorte = extraer_datos_edenorte()
        mantenimientos_totales.extend(datos_edenorte)
    except Exception as e:
        print(f"[!] Error crítico en EdeNorte: {e}")
        traceback.print_exc()

    print("=" * 50)

    # Reindexar IDs únicos para la lista de Jetpack Compose
    for idx, item in enumerate(mantenimientos_totales, start=1):
        item["id"] = f"{item['distribuidora'].lower()}_{idx}"

    print(
        f"[✓] Consolidación exitosa: {len(mantenimientos_totales)} mantenimientos guardados en mantenimientos.json"
    )

    with open("mantenimientos.json", "w", encoding="utf-8") as f:
        json.dump(mantenimientos_totales, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    consolidar_todo()
