"""Thread daemon in background per il controllo periodico delle scadenze.

Logica di notifica: l'email viene inviata solo se ``invio_automatico == 1``
e si verifica almeno una delle condizioni:

- scadenza temporale: ``(data_scadenza - oggi) <= giorni_preavviso``
- scadenza chilometrica: ``(km_scadenza - km_attuali) <= soglia_km_preavviso``

Un cooldown anti-spam (configurabile, default 30 giorni) evita reinvii
basandosi sul campo ``ultimo_invio_email``.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta
from typing import Callable

import database as db
from config import load_config
from mailer import invia_promemoria

FORMATO_TIMESTAMP = "%Y-%m-%d %H:%M:%S"


def verifica_scadenze(veicolo: dict, oggi: date | None = None) -> tuple[bool, list[str]]:
    """Verifica le condizioni di scadenza temporale e chilometrica.

    Restituisce una tupla ``(da_notificare, motivi)``.
    """
    oggi = oggi or date.today()
    motivi: list[str] = []

    try:
        data_scadenza = date.fromisoformat(str(veicolo["data_scadenza"]))
    except (TypeError, ValueError):
        data_scadenza = None
    if data_scadenza is not None:
        giorni_preavviso = (
            int(veicolo["giorni_preavviso"])
            if veicolo["giorni_preavviso"] is not None
            else 30
        )
        giorni_mancanti = (data_scadenza - oggi).days
        if giorni_mancanti <= giorni_preavviso:
            motivi.append(f"scadenza temporale tra {giorni_mancanti} giorni")

    soglia = (
        int(veicolo["soglia_km_preavviso"])
        if veicolo["soglia_km_preavviso"] is not None
        else 1000
    )
    km_mancanti = int(veicolo["km_scadenza"]) - int(veicolo["km_attuali"])
    if km_mancanti <= soglia:
        motivi.append(f"scadenza chilometrica tra {km_mancanti} km")

    return bool(motivi), motivi


def in_cooldown(
    ultimo_invio: str | None,
    cooldown_giorni: int,
    adesso: datetime | None = None,
) -> bool:
    """True se l'ultimo invio e' avvenuto meno di ``cooldown_giorni`` fa."""
    if not ultimo_invio:
        return False
    try:
        ultimo = datetime.strptime(str(ultimo_invio), FORMATO_TIMESTAMP)
    except (TypeError, ValueError):
        return False
    adesso = adesso or datetime.now()
    return (adesso - ultimo).total_seconds() < cooldown_giorni * 86400


def esegui_controllo_automatico() -> list[dict]:
    """Controlla tutti i veicoli e invia i promemoria dovuti.

    Per ogni veicolo con ``invio_automatico == 1`` in scadenza (e non in
    cooldown) invia l'email e registra ``ultimo_invio_email``. Un errore
    su un singolo veicolo non interrompe il controllo degli altri.

    Restituisce la lista degli esiti per il logging in GUI.
    """
    cfg = load_config()
    oggi = date.today()
    risultati: list[dict] = []

    for veicolo in db.get_veicoli():
        if not veicolo.get("invio_automatico"):
            continue
        da_notificare, motivi = verifica_scadenze(veicolo, oggi)
        if not da_notificare:
            continue
        if in_cooldown(veicolo.get("ultimo_invio_email"), cfg.cooldown_giorni):
            continue
        try:
            invia_promemoria(cfg, veicolo)
            db.imposta_ultimo_invio(
                veicolo["id"], datetime.now().strftime(FORMATO_TIMESTAMP)
            )
            risultati.append(
                {"veicolo": veicolo, "stato": "inviata", "dettaglio": ", ".join(motivi)}
            )
        except Exception as exc:
            risultati.append(
                {"veicolo": veicolo, "stato": "errore", "dettaglio": str(exc)}
            )

    return risultati


class SchedulerThread(threading.Thread):
    """Thread daemon che esegue il controllo a intervalli configurabili.

    L'intervallo (in ore) viene riletto dalla configurazione a ogni ciclo,
    quindi le modifiche nelle Impostazioni hanno effetto senza riavvio.
    """

    def __init__(
        self,
        on_risultati: Callable[[list[dict], datetime], None] | None = None,
        get_intervallo_ore: Callable[[], float] | None = None,
        primo_controllo_ritardo: float = 10.0,
    ) -> None:
        super().__init__(daemon=True, name="SchedulerManutenzioni")
        self._on_risultati = on_risultati
        self._get_intervallo_ore = get_intervallo_ore or (lambda: 6.0)
        self._primo_controllo_ritardo = primo_controllo_ritardo
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self.prossimo_controllo: datetime | None = None

    def run(self) -> None:
        self._attendi(self._primo_controllo_ritardo)
        while not self._stop_event.is_set():
            risultati = esegui_controllo_automatico()
            intervallo_secondi = max(60.0, float(self._get_intervallo_ore()) * 3600.0)
            self.prossimo_controllo = datetime.now() + timedelta(
                seconds=intervallo_secondi
            )
            if self._on_risultati is not None:
                try:
                    self._on_risultati(risultati, self.prossimo_controllo)
                except Exception:
                    pass
            self._attendi(intervallo_secondi)

    def _attendi(self, secondi: float) -> None:
        """Attesa interrompibile: reagisce a ``stop()`` e ``forza_controllo()``."""
        scadenza = time.monotonic() + max(0.0, secondi)
        while not self._stop_event.is_set() and not self._wake_event.is_set():
            residuo = scadenza - time.monotonic()
            if residuo <= 0:
                break
            self._wake_event.wait(min(1.0, residuo))
        self._wake_event.clear()

    def stop(self) -> None:
        """Richiede l'arresto del thread (non bloccante)."""
        self._stop_event.set()
        self._wake_event.set()

    def forza_controllo(self) -> None:
        """Anticipa il prossimo controllo, interrompendo l'attesa corrente."""
        self._wake_event.set()
