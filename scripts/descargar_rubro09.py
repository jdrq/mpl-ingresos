"""
descargar_rubro09.py
-------------------------------
Descarga los 5 archivos .xls de Consulta Amigable (MEF) que alimentan
historico-rubro09.html — mismo patrón robusto de descargar_rubro08.py:
reintentos con polling, escalada a doble clic, checkpoint de fila
(radio input:checked) y checkpoint de breadcrumb antes de exportar.

MODO DE USO (desde la raíz del repo):
    python scripts/descargar_rubro09.py

Nota de arquitectura: derechos_adm.xls cubre 5 de los 9 conceptos del
JSON en un solo archivo -- el portal muestra esas 5 filas juntas en el
mismo nivel "Detalle Sub-Genérica" (2: DERECHOS Y TASAS ADMINISTRATIVOS),
sin necesidad de un archivo por cada una. Por eso son 5 archivos, no 9.
"""

from playwright.sync_api import sync_playwright
import time
import subprocess
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------------------------
CARPETA_DESTINO = Path("xlsrubro09")
ANIO            = "2026"
URL_BASE        = (
    f"https://apps5.mineco.gob.pe/transparenciaingresos/"
    f"Navegador/default.aspx?y={ANIO}"
)
FRAME_SELECTOR = "#frame0"

# Pasos comunes: TOTAL → ... → Municipalidad (MPL).
# (el clic en "TOTAL" se hace aparte, ver procesar_archivo)
PASOS_MPL = [
    ("Nivel de Gobierno", "M: GOBIERNOS LOCALES"),
    ("Gob.Loc./Mancom.",  "M: MUNICIPALIDADES"),
    ("Departamento",      ": LAMBAYEQUE"),
    ("Municipalidad",     "140301-301238: MUNICIPALIDAD"),
]

ARCHIVOS = [
    {"nombre": "venta_bienes.xls",
     "pasos": [("Rubro", "09: RECURSOS DIRECTAMENTE"),
               ("Genérica", "3: VENTA DE BIENES Y"),
               ("Sub-Genérica", "1: VENTA DE BIENES")],
     "boton_final_sin_fila": "Detalle Sub-Genérica"},

    {"nombre": "derechos_adm.xls",
     "pasos": [("Rubro", "09: RECURSOS DIRECTAMENTE"),
               ("Genérica", "3: VENTA DE BIENES Y"),
               ("Sub-Genérica", "2: DERECHOS Y TASAS")],
     "boton_final_sin_fila": "Detalle Sub-Genérica"},

    {"nombre": "otro_prest_servicios.xls",
     "pasos": [("Rubro", "09: RECURSOS DIRECTAMENTE"),
               ("Genérica", "3: VENTA DE BIENES Y"),
               ("Sub-Genérica", ": VENTA DE SERVICIOS")],
     "boton_final_sin_fila": "Detalle Sub-Genérica"},

    {"nombre": "infr_transito.xls",
     "pasos": [("Rubro", "09: RECURSOS DIRECTAMENTE"),
               ("Genérica", ": OTROS INGRESOS"),
               ("Sub-Genérica", "2: MULTAS Y SANCIONES NO"),
               ("Detalle Sub-Genérica", "1: MULTAS Y SANCIONES NO")],
     "boton_final_sin_fila": "Específica"},

    {"nombre": "intereses.xls",
     "pasos": [("Rubro", "09: RECURSOS DIRECTAMENTE"),
               ("Genérica", ": OTROS INGRESOS"),
               ("Sub-Genérica", ": RENTAS DE LA PROPIEDAD"),
               ("Detalle Sub-Genérica", ": RENTAS DE LA PROPIEDAD FINANCIERA")],
     "boton_final_sin_fila": "Específica"},
]

NOMBRES_ESPERADOS = [a["nombre"] for a in ARCHIVOS]


# --------------------------------------------------------------------
# CLIC CON REINTENTO (polling + escalada a doble clic)
# --------------------------------------------------------------------
def clic_con_reintento(fl, page, rol=None, nombre=None, intentos=3,
                        verificar=None, exacto=True, espera_verificacion=12):
    locator = fl.get_by_role(rol, name=nombre, exact=exacto)
    for intento in range(intentos):
        try:
            if intento == 0:
                locator.click(timeout=10000)
            else:
                locator.click(timeout=10000)
                time.sleep(0.3)
                locator.click(timeout=10000)
        except Exception as e:
            print(f"  [AVISO] '{nombre}' no fue accionable a tiempo "
                  f"({e.__class__.__name__}), reintentando...")
            time.sleep(2)
            continue

        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        if verificar is None:
            time.sleep(0.8)
            return

        for _ in range(espera_verificacion):
            try:
                if verificar():
                    return
            except Exception:
                pass
            time.sleep(1)

        print(f"  [REINTENTO clic {intento + 1}/{intentos}] '{nombre}' "
              f"no surtió efecto tras {espera_verificacion}s, reintentando...")

    raise RuntimeError(
        f"El clic en '{nombre}' no surtió efecto tras {intentos} intentos "
        f"(ni con doble clic, ni con {espera_verificacion}s de espera cada uno). "
        f"Revisar manualmente."
    )


# --------------------------------------------------------------------
# PROCESAR UN ARCHIVO COMPLETO
# --------------------------------------------------------------------
def procesar_archivo(page, config):
    page.goto(URL_BASE)
    fl = page.frame_locator(FRAME_SELECTOR)

    clic_con_reintento(fl, page, "cell", "TOTAL", intentos=2)

    todos_los_pasos = PASOS_MPL + config["pasos"]

    for etiqueta_boton, texto_fila in todos_los_pasos:
        clic_con_reintento(
            fl, page, rol="button", nombre=etiqueta_boton, intentos=2,
            verificar=lambda tf=texto_fila: fl.get_by_role("cell", name=tf).first.is_visible()
        )
        time.sleep(1)

        confirmado = False
        for intento in range(3):
            if intento == 0:
                fl.get_by_role("cell", name=texto_fila).click()
            else:
                fl.get_by_role("cell", name=texto_fila).click()
                time.sleep(0.3)
                fl.get_by_role("cell", name=texto_fila).click()
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            time.sleep(1)

            for _ in range(15):
                try:
                    fila = fl.locator(f"tr:has-text('{texto_fila}')").first
                    if fila.locator("input:checked").count() > 0:
                        confirmado = True
                        break
                except Exception:
                    pass
                time.sleep(1)

            if confirmado:
                break
            print(f"  [REINTENTO {intento + 1}/3] '{texto_fila}' no se "
                  f"marcó, volviendo a clickear (doble clic)...")

        if not confirmado:
            raise RuntimeError(
                f"El nivel '{texto_fila}' no quedó marcado (radio) tras "
                f"3 intentos. Revisar manualmente."
            )

    # Último clic de la cadena, sin fila después (revela el desglose final)
    if config.get("boton_final_sin_fila"):
        clic_con_reintento(fl, page, rol="button",
                            nombre=config["boton_final_sin_fila"], intentos=2)

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    time.sleep(1.5)

    # Checkpoint post-pivote: SOLO si hubo boton_final_sin_fila (ver nota
    # en descargar_rubro08.py sobre por qué el breadcrumb no es señal
    # confiable si no se avanzó de nivel). Los 5 archivos de Rubro 09
    # siempre tienen boton_final_sin_fila, así que siempre se valida.
    if config.get("boton_final_sin_fila"):
        ultimo_texto = todos_los_pasos[-1][1].rstrip(":")
        confirmado_final = False
        for _ in range(15):
            try:
                breadcrumb = fl.locator(".History").inner_text(timeout=3000)
                if ultimo_texto in breadcrumb:
                    confirmado_final = True
                    break
            except Exception:
                pass
            time.sleep(1)
        if not confirmado_final:
            raise RuntimeError(
                f"Después del clic final, el nivel '{ultimo_texto}' ya no "
                f"aparece en el breadcrumb tras 15s. Archivo NO exportado, "
                f"revisar manualmente."
            )

    # Exportar, con reintento si el primer clic no dispara la descarga.
    descarga = None
    for intento in range(2):
        try:
            with page.expect_download(timeout=15000) as descarga_info:
                if intento == 0:
                    fl.get_by_role("link", name="Exportar").click()
                else:
                    print("  [REINTENTO Exportar] no se disparó la "
                          "descarga, reintentando con doble clic...")
                    fl.get_by_role("link", name="Exportar").click()
                    time.sleep(0.3)
                    fl.get_by_role("link", name="Exportar").click()
            descarga = descarga_info.value
            break
        except Exception:
            if intento == 1:
                raise RuntimeError(
                    "El clic en 'Exportar' no disparó la descarga tras "
                    "2 intentos. Revisar manualmente."
                )

    destino = CARPETA_DESTINO / config["nombre"]
    descarga.save_as(destino)
    print(f"  [OK] {config['nombre']} guardado en {destino.resolve()}")


# --------------------------------------------------------------------
# GIT — commit + push automático (solo si 5/5 exitosos)
# --------------------------------------------------------------------
def git_push_automatico():
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    mensaje = f"Descargar XLS Rubro 09 - {fecha_hoy}"

    print("\n" + "=" * 60)
    print("  GIT — Subiendo xlsrubro09/ a GitHub")
    print("=" * 60)

    pasos = [
        ("git add",    ["git", "add", str(CARPETA_DESTINO)]),
        ("git commit", ["git", "commit", "-m", mensaje]),
        ("git push",   ["git", "push"]),
    ]

    for nombre_paso, cmd in pasos:
        print(f"  → {nombre_paso}...", end=" ", flush=True)
        resultado = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        if resultado.returncode == 0:
            print("OK")
            if nombre_paso == "git commit" and resultado.stdout.strip():
                print(f"     {resultado.stdout.strip().splitlines()[0]}")
        else:
            salida = resultado.stdout + resultado.stderr
            sin_cambios = (
                "nothing to commit" in salida
                or "nothing added to commit" in salida
                or "no changes added to commit" in salida
            )
            if nombre_paso == "git commit" and sin_cambios:
                print("sin cambios (los xls no cambiaron respecto al último commit)")
                return
            print("FALLÓ")
            print(f"  [ERROR {nombre_paso}] {salida.strip() or 'sin detalle'}")
            print("  ⚠ Sube manualmente si hace falta:")
            print(f"     git add {CARPETA_DESTINO.as_posix()}/")
            print(f'     git commit -m "{mensaje}"')
            print("     git push")
            return

    print(f"\n  ✅ xlsrubro09/ subido a GitHub — commit: \"{mensaje}\"")
    print("     Siguiente paso: python scripts/actualizar_json_rubro09.py")


# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Descarga XLS — Rubro 09 (Recursos Directamente Recaudados)")
    print(f"  Municipalidad Provincial de Lambayeque · {ANIO}")
    print(f"  Destino: {CARPETA_DESTINO.resolve()}")
    print("=" * 60)

    CARPETA_DESTINO.mkdir(exist_ok=True)

    exitosos = []
    fallidos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()

        for i, config in enumerate(ARCHIVOS, 1):
            print(f"\n[{i}/{len(ARCHIVOS)}] {config['nombre']}")
            print("-" * 40)
            try:
                procesar_archivo(page, config)
                exitosos.append(config["nombre"])
            except Exception as e:
                print(f"  [ERROR] {e}")
                fallidos.append(config["nombre"])
                try:
                    page.screenshot(path=f"error_{config['nombre']}.png", full_page=True)
                    print(f"  [DIAGNÓSTICO] Captura guardada: error_{config['nombre']}.png")
                except Exception:
                    pass

        input("\nPresiona ENTER para cerrar el navegador...")
        browser.close()

    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    for n in exitosos:
        print(f"  ✓  {n}")
    for n in fallidos:
        print(f"  ✗  {n}  ← revisar manualmente")

    print(f"\nArchivos guardados en: {CARPETA_DESTINO.resolve()}")

    if not fallidos:
        git_push_automatico()
    else:
        print("\n" + "=" * 60)
        print("  ⛔ GIT — NO SE SUBIÓ NADA AL REPOSITORIO")
        print("=" * 60)
        print(f"  {len(fallidos)} de {len(ARCHIVOS)} archivo(s) fallaron: {', '.join(fallidos)}")
        print("  Corrige el/los archivo(s) marcado(s) y vuelve a ejecutar el script.")


if __name__ == "__main__":
    main()
