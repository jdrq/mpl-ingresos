"""
actualizar_json_rubro09.py
-------------------------------
Lee los 5 archivos .xls descargados por
    descargar_rubro09.py
y actualiza automáticamente el corte "hasta la fecha" (2026) en
    data/historico_conceptos_rubro09.json

Mismo patrón que actualizar_json_rubro08.py: parseo con regex (sin
pandas/lxml), muestra viejo vs nuevo, pide confirmación, y si confirmas
hace git add + commit + push automático. Actualiza 'anual' y 'enesep'
del año 2026 (campo renombrado desde 'eneago' el 01-sep-2026, cuando el
corte histórico pasó de Ene-Ago a Ene-Sep).

MODO DE USO (desde la raíz del repo):
    python scripts/actualizar_json_rubro09.py

Reglas de extracción (confirmadas y validadas con Juan el 20-ago-2026):
  venta_bienes.xls          → "1: VENTA DE BIENES AGRICOLAS Y FORESTALES"       → Venta de Bienes Agrícolas
  derechos_adm.xls          → "1: DERECHOS ADMINISTRATIVOS GENERALES"           → Registros y Licencias
  derechos_adm.xls          → "5: ... VIVIENDA Y CONSTRUCCION"                  → Derechos Admin. de Construcción
  derechos_adm.xls          → "8: ... TRANSPORTES Y COMUNICACIONES"             → Derechos Admin. de Transportes y Com.
  derechos_adm.xls          → "9: ... INDUSTRIA Y COMERCIO"                     → Derechos Admin. de Industria y Comercio
  derechos_adm.xls          → "10: OTROS DERECHOS ADMINISTRATIVOS"              → Otros Derechos Administrativos
  otro_prest_servicios.xls  → "9: OTROS INGRESOS POR PRESTACION DE SERVICIOS"   → Otros Ingresos por Prest. de Servicios
  infr_transito.xls         → "5: DE TRANSPORTE"                                → Infracciones Reglamento de Tránsito
  intereses.xls             → "1: INTERESES"                                    → Intereses

Nota: derechos_adm.xls cubre 5 de los 9 conceptos en un solo archivo -- el
portal muestra esas filas juntas en el mismo nivel de detalle.
"""

import re
import json
import subprocess
from datetime import datetime
from pathlib import Path

CARPETA_RUBRO09 = Path("xlsrubro09")
JSON_PATH       = Path("data") / "historico_conceptos_rubro09.json"


def leer_filas(archivo):
    with open(archivo, encoding="latin-1") as f:
        html = f.read()
    filas_html = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    filas = []
    for fh in filas_html:
        celdas = re.findall(r"<td[^>]*>(.*?)</td>", fh, re.S)
        celdas = [re.sub(r"<.*?>", "", c).strip() for c in celdas]
        if celdas:
            filas.append(celdas)
    return filas


def num(texto):
    try:
        return round(float(texto.replace(",", "").strip()))
    except (ValueError, AttributeError):
        return None


def buscar_fila(filas, patron_exacto=None, contiene=None):
    for fila in filas:
        if len(fila) < 4:
            continue
        c0 = fila[0].upper()
        if patron_exacto and c0.startswith(patron_exacto.upper()):
            return num(fila[3])
        if contiene and contiene.upper() in c0:
            return num(fila[3])
    return None


# Reglas: (archivo, [(concepto_json, patron_exacto, contiene)])
REGLAS = [
    ("venta_bienes.xls", [
        ("VENTA_BIENES_AGRICOLAS", None, "VENTA DE BIENES AGRICOLAS Y FORESTALES"),
    ]),
    ("derechos_adm.xls", [
        ("REGISTROS_LICENCIAS",                    None, "DERECHOS ADMINISTRATIVOS GENERALES"),
        ("DERECHOS_CONSTRUCCION",                   None, "DERECHOS ADMINISTRATIVOS DE VIVIENDA Y CONSTRUCCION"),
        ("DERECHOS_TRANSPORTES_COMUNICACIONES",      None, "DERECHOS ADMINISTRATIVOS DE TRANSPORTES Y COMUNICACIONES"),
        ("DERECHOS_INDUSTRIA_COMERCIO",              None, "DERECHOS ADMINISTRATIVOS DE INDUSTRIA Y COMERCIO"),
        ("OTROS_DERECHOS_ADMINISTRATIVOS",           None, "OTROS DERECHOS ADMINISTRATIVOS"),
    ]),
    ("otro_prest_servicios.xls", [
        ("OTROS_INGRESOS_SERVICIOS", None, "OTROS INGRESOS POR PRESTACION DE SERVICIOS"),
    ]),
    ("infr_transito.xls", [
        ("INFRACCIONES_TRANSITO", "5: DE TRANSPORTE", None),
    ]),
    ("intereses.xls", [
        ("INTERESES", "1: INTERESES", None),
    ]),
]


def git_push_automatico():
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    mensaje = f"Actualizar corte Rubro 09 - {fecha_hoy}"

    print("\n" + "=" * 60)
    print("  GIT — Publicando en GitHub Pages")
    print("=" * 60)

    pasos = [
        ("git add",    ["git", "add", str(JSON_PATH)]),
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
                print("sin cambios (el JSON ya estaba subido, no hay nada nuevo)")
                return
            print("FALLÓ")
            detalle = salida.strip() or "sin detalle"
            print(f"  [ERROR {nombre_paso}] {detalle}")
            print("  ⚠ Revisa el error y sube manualmente si hace falta:")
            print(f'     git add {JSON_PATH.as_posix()}')
            print(f'     git commit -m "{mensaje}"')
            print("     git push")
            return

    print(f"\n  ✅ GitHub Pages actualizado — commit: \"{mensaje}\"")


def main():
    if not JSON_PATH.exists():
        print(f"❌ No se encontró {JSON_PATH.resolve()}")
        print("   Ejecuta este script desde la raíz del repo mpl-ingresos.")
        return

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    print("=" * 60)
    print("  Actualizar corte 2026 — Rubro 09")
    print(f"  Leyendo desde: {CARPETA_RUBRO09.resolve()}")
    print("=" * 60)

    cambios = {}
    faltantes = []

    for archivo, reglas in REGLAS:
        ruta = CARPETA_RUBRO09 / archivo
        if not ruta.exists():
            print(f"\n⚠️  {archivo} no encontrado en {CARPETA_RUBRO09} — se omite.")
            faltantes.append(archivo)
            continue

        filas = leer_filas(ruta)
        print(f"\n📄 {archivo}")
        for concepto, patron_exacto, contiene in reglas:
            valor_nuevo = buscar_fila(filas, patron_exacto, contiene)
            if valor_nuevo is None:
                print(f"   ⚠️  No se encontró la fila esperada para {concepto} — se omite.")
                continue
            valor_viejo = data.get(concepto, {}).get("enesep", {}).get("2026")
            label = data.get(concepto, {}).get("label", concepto)
            flecha = "→" if valor_viejo != valor_nuevo else "= (sin cambio)"
            print(f"   {label:45s} S/ {valor_viejo:>12,}  {flecha}  S/ {valor_nuevo:>12,}"
                  if valor_viejo is not None else
                  f"   {label:45s} (sin valor previo) {flecha} S/ {valor_nuevo:>12,}")
            cambios[concepto] = valor_nuevo

    if not cambios:
        print("\nNo hay cambios para aplicar.")
        return

    print("\n" + "=" * 60)
    if faltantes:
        print(f"  ⚠️  {len(faltantes)} archivo(s) no encontrados: {', '.join(faltantes)}")
        print("     Esos conceptos NO se actualizarán.")
    resp = input(f"\n¿Aplicar estos {len(cambios)} cambios a {JSON_PATH}? [s/N]: ").strip().lower()
    if resp != "s":
        print("Cancelado. No se modificó el JSON.")
        return

    for concepto, valor in cambios.items():
        data[concepto]["anual"]["2026"] = valor
        data[concepto]["enesep"]["2026"] = valor

    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {JSON_PATH} actualizado con {len(cambios)} concepto(s).")

    git_push_automatico()


if __name__ == "__main__":
    main()
