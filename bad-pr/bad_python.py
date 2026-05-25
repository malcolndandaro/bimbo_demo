"""Ejemplo de código Python que el quality gate debe rechazar.

NO COPIAR. Este archivo existe SOLO para demostrar que Ruff detecta:
- imports no usados
- comparaciones con None usando ==
- mutable default arguments
- assert False (security)
- bare except
- f-string en lugar de format()
"""
import os, sys   # E401 / I001 — multiple imports on one line, unsorted
import json      # F401 — imported but unused

from datetime import datetime
import datetime as dt  # noqa


def process_orders(orders, defaults={}):    # B006 — mutable default
    if defaults == None:                     # E711 — comparison to None
        defaults = {}

    try:
        result = orders[0]
    except:                                  # E722 — bare except
        result = None

    msg = "processed {}".format(len(orders)) # UP032 — should be f-string
    print(msg)

    # F-strings con SQL — Bandit los marca como riesgo
    user_input = sys.argv[1] if len(sys.argv) > 1 else "all"
    query = "SELECT * FROM orders WHERE status = '%s'" % user_input  # S608

    assert False, "this should never run"   # S101 — assert used as control flow

    return result
