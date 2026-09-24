# -*- coding: utf-8 -*-
"""Guard: ningun numero VISIBLE del sitio pasa de MAX_DP decimales.

Regla fijada por Carlos el 2026-09-24: maximo 2 decimales en todo lo que se renderiza.

⚠️ Un grep literal de `\\d+\\.\\d{3,}` sobre el HTML NO sirve como guard. Medido ese mismo
dia: **13,678 coincidencias en crudo contra 226 realmente visibles** -- el 98.3% son
arreglos de datos de Plotly, llaves de ordenamiento `data-s` y el payload `data-mxn` /
`data-usd` del toggle de moneda. Un guard que dispara 13,678 veces se desactiva el primer
dia. Asi que primero se quita el payload y solo despues se busca. Misma leccion que el
guard de "GBM" contra los blobs base64.

Excepciones, todas estrechas y con razon:
  * TIPO DE CAMBIO a 4 decimales -- convencion documentada del sitio (`USD/MXN 17.5290`),
    y el glosario la explica con un ejemplo literal.
  * PROBABILIDADES en [0.995, 1): redondear 0.997 o 0.9999 imprime **1.00**, que afirma
    CERTEZA. Eso no es perder precision, es decir algo falso.
  * Archivos `.ai.txt` y `.csv`: consumo tecnico, no visual.
"""
import os, re, sys

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
MAX_DP = 2
NUM = re.compile(r"(?<![\d.])(\d+\.\d{%d,})(?![\d])" % (MAX_DP + 1))
PAYLOAD = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>|"
                     r"data-s='[^']*'|data-(?:mxn|usd)=\"[^\"]*\")", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
FX_CTX = re.compile(r"(USD\s*/\s*MXN|USD/MXN|tipo de cambio|exchange rate|decimals)", re.I)


def visible(t):
    t = PAYLOAD.sub(" ", t)
    return TAG.sub(" ", t)


def allowed(val, ctx):
    v = float(val)
    if 0.995 <= v < 1.0:                      # redondearia a 1.00 = afirmar certeza
        return "prob~1"
    if len(val.split(".")[1]) == 4 and FX_CTX.search(ctx):
        return "FX 4dp"
    return None


bad, ok = [], []
for fn in sorted(os.listdir(DOCS)):
    if not fn.endswith(".html"):
        continue
    t = visible(open(os.path.join(DOCS, fn), encoding="utf-8", errors="replace").read())
    for m in NUM.finditer(t):
        ctx = re.sub(r"\s+", " ", t[max(0, m.start() - 60):m.end() + 20])
        why = allowed(m.group(1), ctx)
        (ok if why else bad).append((fn, m.group(1), why or ctx))

print("=" * 96)
print("GUARD DE DECIMALES -- techo %d, solo texto visible" % MAX_DP)
print("=" * 96)
for fn, v, why in ok:
    print("  permitido  %-30s %-10s (%s)" % (fn, v, why))
if bad:
    print()
    for fn, v, ctx in bad[:20]:
        print("  ** EXCEDE ** %-28s %-22s ...%s..." % (fn, v, ctx[:70]))
    print("\n%d numero(s) visible(s) con mas de %d decimales" % (len(bad), MAX_DP))
    sys.exit(1)
print("\nOK: 0 numeros visibles exceden %d decimales (%d excepciones permitidas)"
      % (MAX_DP, len(ok)))
