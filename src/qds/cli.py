"""Egységes parancssori belépési pont a QDS szkriptekhez.

Miért: token nélkül (vagy elérhetetlen backendnél) eddig nyers
``FileNotFoundError`` traceback jelent meg. A felhasználónak viszont az kell,
hogy lássa: *mi hiányzik* és *mit tegyen* — ráadásul úgy, hogy a szkript
exit kódja is értelmes legyen (CI-barát).

Használat a szkriptek végén::

    if __name__ == "__main__":
        sys.exit(qds.cli.run(main))
"""

import sys

#: Exit kódok — a szkriptek ezeket adják vissza.
EXIT_OK = 0
EXIT_USAGE = 1        # rossz argumentum / felhasználói hiba
EXIT_CONFIG = 2       # hiányzó token vagy konfiguráció
EXIT_CONNECTION = 3   # IBM kapcsolat / backend hiba
EXIT_DATA = 4         # hiányzó vagy hibás adatfájl


def run(main_fn, argv=None):
    """Lefuttatja a ``main_fn(argv)``-t, és a várt hibákat szépen lekezeli.

    Args:
        main_fn: ``main(argv)`` szignatúrájú függvény, ami exit kódot ad vissza.
        argv: opcionális argumentumlista (alapból ``sys.argv[1:]``).

    Returns:
        int: exit kód.
    """
    try:
        return main_fn(argv) or EXIT_OK
    except FileNotFoundError as exc:
        print(f"HIÁNYZÓ FÁJL: {exc}", file=sys.stderr)
        return EXIT_DATA
    except PermissionError as exc:
        print(f"JOGOSULTSÁGI HIBA: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except ValueError as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ConnectionError as exc:
        print(f"KAPCSOLATI HIBA: {exc}", file=sys.stderr)
        return EXIT_CONNECTION
    except KeyboardInterrupt:
        print("\nMegszakítva.", file=sys.stderr)
        return 130
