"""
descargar_xls_mef_ingresos.py
-------------------------------
Automatiza la descarga de los 4 archivos .xls de Consulta Amigable de
INGRESOS (MEF) para la Municipalidad Provincial de Lambayeque.

  fuente.xls    → Ejecución por Fuente de Financiamiento
  rubro.xls     → Ejecución por Rubro de Ingreso
  generica.xls  → Ejecución por Genérica de Ingreso
  ranking.xls   → Todas las municipalidades del Dpto. Lambayeque

MODO DE USO:
    pip install playwright
    playwright install chromium
    python descargar_xls_mef_ingresos.py

Los archivos se guardan en la carpeta xls/ del proyecto
(donde el index.html los espera con fetch("xls/...")).
"""

from playwright.sync_api import sync_playwright
import time
import shutil
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────
CARPETA_DESTINO = Path("xls")   # el index.html hace fetch("xls/archivo.xls")
ANIO            = "2026"
URL_BASE        = (
    f"https://apps5.mineco.gob.pe/transparenciaingresos/"
    f"Navegador/default.aspx?y={ANIO}"
)
FL = "#frame0"   # selector del iframe del portal


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def esperar(page, ms=5000):
    """Espera networkidle sin reventar si tarda."""
    try:
        page.wait_for_load_state("networkidle", timeout=ms)
    except Exception:
        pass


def fl(page):
    """Devuelve el content_frame del iframe principal."""
    return page.locator(FL).content_frame


def backup_y_guardar(descarga, nombre):
    """Guarda el archivo descargado en xls/ con backup previo."""
    destino = CARPETA_DESTINO / nombre
    if destino.exists():
        respaldo = CARPETA_DESTINO / "_respaldo_anterior" / nombre
        respaldo.parent.mkdir(exist_ok=True)
        shutil.copy(destino, respaldo)
        print(f"  → Backup guardado en {respaldo}")
    descarga.save_as(destino)
    print(f"  [OK] {nombre} → {destino.resolve()}")


# ─────────────────────────────────────────────────────────────────
# FLUJO COMÚN: bajar hasta la MPL
# (Confirmado con codegen — nombres exactos del portal de Ingresos)
# ─────────────────────────────────────────────────────────────────
def navegar_hasta_mpl(page):
    """
    Navega desde TOTAL hasta la MPL (140301).
    Pasos confirmados con playwright codegen en el portal real:
      TOTAL → Nivel de Gobierno → M: GOBIERNOS LOCALES
            → Gob.Loc./Mancom. → M: MUNICIPALIDADES
            → Departamento     → : LAMBAYEQUE
            → Municipalidad    → 140301-301238: MUNICIPALIDAD...
    """
    print(f"  → Cargando {URL_BASE}")
    page.goto(URL_BASE)
    esperar(page)

    f = fl(page)

    # TOTAL
    f.get_by_role("cell", name="TOTAL", exact=True).click()
    esperar(page)
    time.sleep(1)

    # Nivel de Gobierno → M: GOBIERNOS LOCALES
    print("  → Nivel de Gobierno | M: GOBIERNOS LOCALES")
    f.get_by_role("button", name="Nivel de Gobierno").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name="M: GOBIERNOS LOCALES").click()
    esperar(page); time.sleep(1)

    # Gob.Loc./Mancom. → M: MUNICIPALIDADES
    print("  → Gob.Loc./Mancom. | M: MUNICIPALIDADES")
    f.get_by_role("button", name="Gob.Loc./Mancom.").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name="M: MUNICIPALIDADES").click()
    esperar(page); time.sleep(1)

    # Departamento → : LAMBAYEQUE
    print("  → Departamento | : LAMBAYEQUE")
    f.get_by_role("button", name="Departamento").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name=": LAMBAYEQUE").click()
    esperar(page); time.sleep(1)

    # Municipalidad → 140301-301238
    print("  → Municipalidad | 140301-301238: MUNICIPALIDAD...")
    f.get_by_role("button", name="Municipalidad").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name="140301-301238: MUNICIPALIDAD").click()
    esperar(page); time.sleep(1.5)


# ─────────────────────────────────────────────────────────────────
# DESCARGA DE CADA ARCHIVO
# ─────────────────────────────────────────────────────────────────
def descargar_fuente(page):
    """fuente.xls — pivote a 'Fuente'."""
    navegar_hasta_mpl(page)
    f = fl(page)
    print("  → Pivotando a 'Fuente'")
    f.get_by_role("button", name="Fuente").click()
    esperar(page); time.sleep(1.5)
    print("  → Exportando fuente.xls")
    with page.expect_download(timeout=30000) as dl:
        f.get_by_role("link", name="Exportar").click()
    backup_y_guardar(dl.value, "fuente.xls")


def descargar_rubro(page):
    """rubro.xls — pivote a 'Rubro'."""
    navegar_hasta_mpl(page)
    f = fl(page)
    print("  → Pivotando a 'Rubro'")
    f.get_by_role("button", name="Rubro").click()
    esperar(page); time.sleep(1.5)
    print("  → Exportando rubro.xls")
    with page.expect_download(timeout=30000) as dl:
        f.get_by_role("link", name="Exportar").click()
    backup_y_guardar(dl.value, "rubro.xls")


def descargar_generica(page):
    """
    generica.xls — pivote a 'Genérica'.
    Nota codegen: en una sesión apareció un clic extra en
    'Nivel de Gobierno M:' antes del Departamento — es un
    artefacto de la sesión, no es necesario. La ruta estándar
    funciona igual.
    """
    navegar_hasta_mpl(page)
    f = fl(page)
    print("  → Pivotando a 'Genérica'")
    f.get_by_role("button", name="Genérica").click()
    esperar(page); time.sleep(1.5)
    print("  → Exportando generica.xls")
    with page.expect_download(timeout=30000) as dl:
        f.get_by_role("link", name="Exportar").click()
    backup_y_guardar(dl.value, "generica.xls")


def descargar_ranking(page):
    """
    ranking.xls — baja hasta : LAMBAYEQUE, clic en 'Municipalidad'
    SIN seleccionar ninguna fila → lista las 38 municipalidades → Exportar.
    Confirmado con codegen: tras seleccionar LAMBAYEQUE se exporta
    directamente sin pivotar (el nivel queda en Municipalidad).
    """
    print(f"  → Cargando {URL_BASE}")
    page.goto(URL_BASE)
    esperar(page)

    f = fl(page)

    # TOTAL
    f.get_by_role("cell", name="TOTAL", exact=True).click()
    esperar(page); time.sleep(1)

    # Nivel de Gobierno → M: GOBIERNOS LOCALES
    print("  → Nivel de Gobierno | M: GOBIERNOS LOCALES")
    f.get_by_role("button", name="Nivel de Gobierno").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name="M: GOBIERNOS LOCALES").click()
    esperar(page); time.sleep(1)

    # Gob.Loc./Mancom. → M: MUNICIPALIDADES
    print("  → Gob.Loc./Mancom. | M: MUNICIPALIDADES")
    f.get_by_role("button", name="Gob.Loc./Mancom.").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name="M: MUNICIPALIDADES").click()
    esperar(page); time.sleep(1)

    # Departamento → : LAMBAYEQUE
    print("  → Departamento | : LAMBAYEQUE")
    f.get_by_role("button", name="Departamento").click()
    esperar(page); time.sleep(1)
    f.get_by_role("cell", name=": LAMBAYEQUE").click()
    esperar(page); time.sleep(1)

    # Municipalidad SIN seleccionar fila → queda el listado de 38
    print("  → Botón 'Municipalidad' (sin seleccionar fila)")
    f.get_by_role("button", name="Municipalidad").click()
    esperar(page); time.sleep(1.5)

    print("  → Exportando ranking.xls")
    with page.expect_download(timeout=30000) as dl:
        f.get_by_role("link", name="Exportar").click()
    backup_y_guardar(dl.value, "ranking.xls")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
TAREAS = [
    ("fuente.xls",   descargar_fuente),
    ("rubro.xls",    descargar_rubro),
    ("generica.xls", descargar_generica),
    ("ranking.xls",  descargar_ranking),
]

def main():
    print("=" * 60)
    print("  Descarga XLS — Consulta Amigable de INGRESOS")
    print(f"  Municipalidad Provincial de Lambayeque · {ANIO}")
    print(f"  Destino: {CARPETA_DESTINO.resolve()}")
    print("=" * 60)

    CARPETA_DESTINO.mkdir(exist_ok=True)

    exitosos = []
    fallidos  = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page    = browser.new_page()

        for i, (nombre, fn) in enumerate(TAREAS, 1):
            print(f"\n[{i}/{len(TAREAS)}] {nombre}")
            print("-" * 40)
            try:
                fn(page)
                exitosos.append(nombre)
            except Exception as e:
                print(f"  [ERROR] {e}")
                fallidos.append(nombre)

                # Captura para diagnóstico
                captura = Path(f"error_{nombre}.png")
                try:
                    page.screenshot(path=str(captura), full_page=True)
                    print(f"  [DIAGNÓSTICO] Captura: {captura.resolve()}")
                except Exception:
                    pass

                resp = input("\n  ¿Continuar con el siguiente archivo? [s/N]: ").strip().lower()
                if resp != "s":
                    print("  Deteniendo el script.")
                    break

        # ── Resumen ──────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  RESUMEN")
        print("=" * 60)
        for n in exitosos:
            print(f"  ✓  {n}")
        for n in fallidos:
            print(f"  ✗  {n}  ← revisar manualmente")

        if not fallidos:
            print(
                "\n  Todos los archivos descargados correctamente.\n"
                "  Próximo paso:\n"
                "    git add xls/\n"
                f"    git commit -m \"Actualización {ANIO}\"\n"
                "    git push"
            )
        else:
            print(f"\n  {len(fallidos)} archivo(s) fallaron.")
            print(f"  Descarga manual: {URL_BASE}")

        input("\nPresiona ENTER para cerrar el navegador...")
        browser.close()


if __name__ == "__main__":
    main()
