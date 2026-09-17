"""Gestione della configurazione applicativa tramite ``config.ini``.

I parametri SMTP, il nome dell'officina e le preferenze dello scheduler
vengono salvati in un file esterno (nessun hardcoding). In assenza del
file vengono usati i valori predefiniti.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass

from paths import get_config_path


@dataclass
class AppConfig:
    """Parametri applicativi (SMTP, officina, scheduler)."""

    smtp_host: str = "smtp.gmail.com"
    smtp_porta: int = 587
    mittente: str = ""
    password: str = ""
    usa_ssl: bool = False
    nome_officina: str = "Officina Meccanica"
    intervallo_ore: float = 6.0
    cooldown_giorni: int = 30


def _int(valore: object, default: int) -> int:
    try:
        return int(str(valore).strip())
    except (TypeError, ValueError):
        return default


def _float(valore: object, default: float) -> float:
    try:
        return float(str(valore).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def load_config() -> AppConfig:
    """Carica la configurazione; i valori mancanti tornano ai default."""
    parser = configparser.ConfigParser()
    percorso = get_config_path()
    if os.path.exists(percorso):
        parser.read(percorso, encoding="utf-8")

    def leggi(sezione: str, chiave: str, default: object) -> object:
        try:
            return parser[sezione][chiave]
        except (KeyError, TypeError):
            return default

    return AppConfig(
        smtp_host=str(leggi("smtp", "host", AppConfig.smtp_host)),
        smtp_porta=_int(leggi("smtp", "porta", AppConfig.smtp_porta), AppConfig.smtp_porta),
        mittente=str(leggi("smtp", "mittente", AppConfig.mittente)),
        password=str(leggi("smtp", "password", AppConfig.password)),
        usa_ssl=str(leggi("smtp", "usa_ssl", "0")).strip().lower() in ("1", "true", "yes", "si", "sì"),
        nome_officina=str(leggi("officina", "nome_officina", AppConfig.nome_officina)),
        intervallo_ore=_float(
            leggi("scheduler", "intervallo_ore", AppConfig.intervallo_ore),
            AppConfig.intervallo_ore,
        ),
        cooldown_giorni=_int(
            leggi("scheduler", "cooldown_giorni", AppConfig.cooldown_giorni),
            AppConfig.cooldown_giorni,
        ),
    )


def save_config(cfg: AppConfig) -> None:
    """Scrive la configurazione nel file ``config.ini``."""
    parser = configparser.ConfigParser()
    parser["smtp"] = {
        "host": cfg.smtp_host,
        "porta": str(cfg.smtp_porta),
        "mittente": cfg.mittente,
        "password": cfg.password,
        "usa_ssl": "1" if cfg.usa_ssl else "0",
    }
    parser["officina"] = {"nome_officina": cfg.nome_officina}
    parser["scheduler"] = {
        "intervallo_ore": str(cfg.intervallo_ore),
        "cooldown_giorni": str(cfg.cooldown_giorni),
    }
    with open(get_config_path(), "w", encoding="utf-8") as file:
        parser.write(file)


def ensure_config() -> None:
    """Crea ``config.ini`` con i valori predefiniti se non esiste."""
    if not os.path.exists(get_config_path()):
        save_config(AppConfig())
