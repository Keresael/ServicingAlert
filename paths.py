"""Helper per la risoluzione dei percorsi dei file runtime.

Le funzioni funzionano sia in ambiente di sviluppo (cartella progetto)
sia quando l'applicazione e' impacchettata come eseguibile Windows con
PyInstaller (``sys.frozen``), dove i file ``officina.db`` e
``config.ini`` vengono creati nella cartella del ``.exe``.
"""

from __future__ import annotations

import os
import sys


def get_base_dir() -> str:
    """Restituisce la directory base per i file runtime (db, config)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_db_path() -> str:
    """Percorso completo del database SQLite ``officina.db``."""
    return os.path.join(get_base_dir(), "officina.db")


def get_config_path() -> str:
    """Percorso completo del file di configurazione ``config.ini``."""
    return os.path.join(get_base_dir(), "config.ini")
