"""Entry point di ServicingAlert.

Applicazione desktop per la gestione delle scadenze di manutenzione dei
veicoli (temporali e chilometriche) con invio automatico di email di
promemoria ai clienti tramite scheduler in background.
"""

from __future__ import annotations

import customtkinter as ctk

from config import ensure_config
from database import init_db
from gui import App


def main() -> None:
    try:
        init_db()
        ensure_config()
    except Exception as exc:
        raise SystemExit(f"Errore durante l'inizializzazione: {exc}")

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
