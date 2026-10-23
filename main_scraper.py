import json
import traceback

# Importar las funciones de extracción de tus 3 archivos
# Asegúrate de que cada archivo tenga una función que devuelva la lista de diccionarios
from scraper_edesur import extraer_mantenimientos_edesur
from scraper_edeeste import extraer_datos_edeeste
from scraper_edenorte import extraer_datos_edenorte


def consolidar_mantenimientos():
    todos_los_mantenimientos = []

    # 1. Edesur
    print("[1/3] Extrayendo datos de Edesur...")
    try:
        datos_edesur = extraer_mantenimientos_edesur()
        print(f" -> {len(datos_edesur)} registros de Edesur.")
        todos_los_mantenimientos.extend(datos_edesur)
    except Exception as e:
        print(f"[!] Error extrayendo Edesur: {e}")
        traceback.print_exc()

    # 2. Edeeste
    print("[2/3] Extrayendo datos de Edeeste...")
    try:
        datos_edeeste = extraer_datos_edeeste()
        print(f" -> {len(datos_edeeste)} registros de Edeeste.")
        todos_los_mantenimientos.extend(datos_edeeste)
    except Exception as e:
        print(f"[!] Error extrayendo Edeeste: {e}")
        traceback.print_exc()

    # 3. EdeNorte
    print("[3/3] Extrayendo datos de EdeNorte...")
    try:
        datos_edenorte = extraer_datos_edenorte()
        print(f" -> {len(datos_edenorte)} registros de EdeNorte.")
        todos_los_mantenimientos.extend(datos_edenorte)
    except Exception as e:
        print(f"[!] Error extrayendo EdeNorte: {e}")
        traceback.print_exc()

    print(
        f"\n[✓] Total consolidado: {len(todos_los_mantenimientos)} mantenimientos a nivel nacional."
    )

    # Guardar en el archivo único que lee la app
    with open("mantenimientos.json", "w", encoding="utf-8") as f:
        json.dump(todos_los_mantenimientos, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    consolidar_mantenimientos()
