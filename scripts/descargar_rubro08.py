"""
descargar_rubro08.py
-------------------------------
Descarga los 6 archivos .xls de Consulta Amigable (MEF) que alimentan
historico-rubro08.html — versión robusta con reintentos y checkpoints.

MODO DE USO (desde la raíz del repo):
    python scripts/descargar_rubro08.py

VERSIÓN 2 (mejorada tras fallo en producción — timeout en "cell ALCABALA"):
El script original hacía clic apenas el botón aparecía disponible, sin
confirmar que el postback anterior había terminado. Cuando el servidor del
MEF respondía lento, el clic llegaba "en el aire": el botón todavía no
había vuelto a quedar accionable, Playwright lo esperaba 30s a ciegas, y
al fallar el 2º archivo el navegador ya había quedado en un estado roto
para los 4 siguientes ("Target page, context or browser has been closed").

Esta versión adopta el mismo patrón que ya funciona bien en el script de
GORE Lambayeque (descargar_xls_mef.py, sesiones 13-14):
  1. clic_con_reintento(): hace polling (hasta 12s, revisando cada 1s) en
     vez de un solo chequeo temprano. Si el clic no surtió efecto, reintenta
     - y desde el 2º intento escala a DOBLE clic.
  2. Checkpoint de fila: después de clickear una fila, confirma que su
     radio (input:checked) quedó realmente marcado antes de seguir. Si no
     se marca, reintenta hasta 3 veces.
  3. "Exportar" con reintento: si el primer clic no dispara la descarga en
     15s, reintenta con doble clic antes de rendirse.
  4. Si un archivo falla, el script YA NO detiene todo el lote — sigue con
     el siguiente (antes, un fallo en el 2º dejaba el navegador roto para
     los 4 restantes: "Target page, context or browser has been closed").
"""

from playwright.sync_api import sync_playwright
import time
import subprocess
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------------------------
CARPETA_DESTINO = Path("xlsrubro08")
ANIO            = "2026"
URL_BASE        = (
    f"https://apps5.mineco.gob.pe/transparenciaingresos/"
    f"Navegador/default.aspx?y={ANIO}"
)
FRAME_SELECTOR = "#frame0"

# Pasos comunes a los 6 archivos: TOTAL → ... → Municipalidad (MPL).
# (el clic en "TOTAL" se hace aparte, ver procesar_archivo)
PASOS_MPL = [
    ("Nivel de Gobierno", "M: GOBIERNOS LOCALES"),
    ("Gob.Loc./Mancom.",  "M: MUNICIPALIDADES"),
    ("Departamento",      ": LAMBAYEQUE"),
    ("Municipalidad",     "140301-301238: MUNICIPALIDAD"),
]

# Cada archivo: pasos propios después de llegar a la MPL, y opcionalmente
# un último clic a un botón SIN fila después (revela el desglose final).
ARCHIVOS = [
    {"nombre": "predial.xls",
     "pasos": [("Rubro", ": IMPUESTOS MUNICIPALES"),
               ("Genérica", "1: IMPUESTOS Y CONTRIBUCIONES"),
               ("Sub-Genérica", ": IMPUESTO A LA PROPIEDAD"),
               ("Detalle Sub-Genérica", "1: IMPUESTO SOBRE LA"),
               ("Específica", ": PREDIAL")],
     "boton_final_sin_fila": "Detalle Específica"},

    {"nombre": "alcabala.xls",
     "pasos": [("Rubro", ": IMPUESTOS MUNICIPALES"),
               ("Genérica", "1: IMPUESTOS Y CONTRIBUCIONES"),
               ("Sub-Genérica", ": IMPUESTO A LA PROPIEDAD"),
               ("Detalle Sub-Genérica", "1: IMPUESTO SOBRE LA"),
               ("Específica", ": ALCABALA")],
     "boton_final_sin_fila": "Detalle Específica"},

    {"nombre": "patri_vehicular.xls",
     "pasos": [("Rubro", ": IMPUESTOS MUNICIPALES"),
               ("Genérica", "1: IMPUESTOS Y CONTRIBUCIONES"),
               ("Sub-Genérica", ": IMPUESTO A LA PROPIEDAD"),
               ("Detalle Sub-Genérica", "2: IMPUESTO SOBRE LA")],
     "boton_final_sin_fila": None},

    {"nombre": "imp_selec_espe.xls",
     "pasos": [("Rubro", ": IMPUESTOS MUNICIPALES"),
               ("Genérica", "1: IMPUESTOS Y CONTRIBUCIONES"),
               ("Sub-Genérica", "3: IMPUESTOS A LA PRODUCCION")],
     "boton_final_sin_fila": None},

    {"nombre": "sanc_tributarias.xls",
     "pasos": [("Rubro", ": IMPUESTOS MUNICIPALES"),
               ("Genérica", "1: IMPUESTOS Y CONTRIBUCIONES"),
               ("Sub-Genérica", ": OTROS INGRESOS IMPOSITIVOS")],
     "boton_final_sin_fila": "Detalle Sub-Genérica"},

    {"nombre": "intereses.xls",
     "pasos": [("Rubro", ": IMPUESTOS MUNICIPALES"),
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
                        verificar=None, exacto=True, espera_verificacion=18):
    """
    Hace clic con reintentos automáticos, escalando a DOBLE CLIC desde el
    2º intento. Usa polling (revisa cada 1s hasta `espera_verificacion`
    segundos) en vez de un solo chequeo — así no confunde "el servidor
    está tardando" con "el clic no sirvió".

    verificar: función sin argumentos que retorna True si el clic surtió
    efecto. Si no se pasa, solo se espera el postback y se asume éxito.
    """
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
        # 1) Clic en el botón de la cadena (con reintento + verificación
        #    de que la fila esperada se hizo visible).
        clic_con_reintento(
            fl, page, rol="button", nombre=etiqueta_boton, intentos=3,
            verificar=lambda tf=texto_fila: fl.get_by_role("cell", name=tf).first.is_visible()
        )
        time.sleep(1)  # margen extra: el servidor del MEF a veces es lento

        # 2) Clic en la fila, con checkpoint: confirma que el radio quedó
        #    REALMENTE marcado antes de avanzar. Hasta 3 intentos,
        #    escalando a doble clic desde el 2º.
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
                            nombre=config["boton_final_sin_fila"], intentos=3)

    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    time.sleep(1.5)

    # Checkpoint post-pivote: SOLO aplica si hubo un boton_final_sin_fila,
    # que es lo que realmente "avanza de nivel" y actualiza el breadcrumb.
    # Si el archivo exporta directo tras seleccionar la última fila (sin un
    # clic más a la cadena), el breadcrumb NUNCA llega a mostrar ese texto
    # -- eso ya lo advertía el comentario original: "el breadcrumb NO es
    # buena señal acá, ese resumen solo aparece una vez que se avanza al
    # SIGUIENTE nivel, no apenas se selecciona la fila actual". En ese
    # caso el checkpoint de radio (input:checked) que ya pasamos arriba es
    # la confirmación suficiente, y no hace falta revisar el breadcrumb.
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
# GIT — commit + push automático (solo si 6/6 exitosos)
# --------------------------------------------------------------------
def git_push_automatico():
    """
    Ejecuta git add xlsrubro08/ → commit → push. Solo se llama si los 6
    archivos se descargaron bien (todo o nada, mismo criterio que el
    script diario). Nunca lanza excepción -- el fallo es informativo.
    """
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    mensaje = f"Descargar XLS Rubro 08 - {fecha_hoy}"

    print("\n" + "=" * 60)
    print("  GIT — Subiendo xlsrubro08/ a GitHub")
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

    print(f"\n  ✅ xlsrubro08/ subido a GitHub — commit: \"{mensaje}\"")
    print("     Siguiente paso: python scripts/actualizar_json_rubro08.py")


# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Descarga XLS — Rubro 08 (Impuestos Municipales)")
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
                time.sleep(2)  # pequeño respiro entre archivos para el servidor MEF
            except Exception as e:
                print(f"  [ERROR] {e}")
                fallidos.append(config["nombre"])
                try:
                    page.screenshot(path=f"error_{config['nombre']}.png", full_page=True)
                    print(f"  [DIAGNÓSTICO] Captura guardada: error_{config['nombre']}.png")
                except Exception:
                    pass
                # A diferencia de antes: NO se detiene todo el script — se
                # sigue con el siguiente archivo (el patrón de reintentos
                # ya resolvió la mayoría de fallos transitorios; si uno
                # falla de verdad, no tiene por qué arrastrar a los demás).

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
