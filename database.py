"""Inizializzazione SQLite e funzioni CRUD per la tabella ``veicoli``.

Ogni operazione apre una connessione a breve durata: questo rende il
modulo utilizzabile in sicurezza sia dal thread GUI sia dal thread
dello scheduler in background.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from paths import get_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS veicoli (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_cliente         TEXT NOT NULL,
    email_cliente        TEXT NOT NULL,
    targa                TEXT UNIQUE NOT NULL,
    telaio               TEXT NOT NULL,
    km_attuali           INTEGER NOT NULL,
    km_scadenza          INTEGER NOT NULL,
    data_scadenza        DATE NOT NULL,
    giorni_preavviso     INTEGER DEFAULT 30,
    soglia_km_preavviso  INTEGER DEFAULT 1000,
    invio_automatico     INTEGER DEFAULT 1,
    ultimo_invio_email   DATETIME NULL
);
"""

_CAMPI_MODIFICABILI = {
    "nome_cliente",
    "email_cliente",
    "targa",
    "telaio",
    "km_attuali",
    "km_scadenza",
    "data_scadenza",
    "giorni_preavviso",
    "soglia_km_preavviso",
    "invio_automatico",
}


class TargaDuplicataError(Exception):
    """Sollevata quando si salva un veicolo con targa gia' presente."""


@contextmanager
def _connessione() -> Iterator[sqlite3.Connection]:
    """Apre una connessione monouso con commit/rollback automatici."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Crea il database e la tabella ``veicoli`` se non esistono."""
    with _connessione() as conn:
        conn.execute(_SCHEMA)


def aggiungi_veicolo(
    nome_cliente: str,
    email_cliente: str,
    targa: str,
    telaio: str,
    km_attuali: int,
    km_scadenza: int,
    data_scadenza: str,
    giorni_preavviso: int = 30,
    soglia_km_preavviso: int = 1000,
    invio_automatico: int = 1,
) -> int:
    """Inserisce un nuovo veicolo e ne restituisce l'id."""
    with _connessione() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO veicoli (
                    nome_cliente, email_cliente, targa, telaio,
                    km_attuali, km_scadenza, data_scadenza,
                    giorni_preavviso, soglia_km_preavviso, invio_automatico
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nome_cliente,
                    email_cliente,
                    targa,
                    telaio,
                    km_attuali,
                    km_scadenza,
                    data_scadenza,
                    giorni_preavviso,
                    soglia_km_preavviso,
                    invio_automatico,
                ),
            )
        except sqlite3.IntegrityError as exc:
            if "targa" in str(exc).lower():
                raise TargaDuplicataError(
                    f"Esiste gia' un veicolo con la targa '{targa}'."
                ) from exc
            raise
        return int(cur.lastrowid)


def get_veicoli() -> list[dict[str, Any]]:
    """Restituisce tutti i veicoli ordinati per targa."""
    with _connessione() as conn:
        righe = conn.execute("SELECT * FROM veicoli ORDER BY targa").fetchall()
    return [dict(riga) for riga in righe]


def get_veicolo(veicolo_id: int) -> dict[str, Any] | None:
    """Restituisce il veicolo con l'id indicato (o None)."""
    with _connessione() as conn:
        riga = conn.execute(
            "SELECT * FROM veicoli WHERE id = ?", (veicolo_id,)
        ).fetchone()
    return dict(riga) if riga else None


def aggiorna_veicolo(veicolo_id: int, **campi: Any) -> None:
    """Aggiorna i campi forniti di un veicolo esistente."""
    da_aggiornare = {k: v for k, v in campi.items() if k in _CAMPI_MODIFICABILI}
    if not da_aggiornare:
        return
    assegnazioni = ", ".join(f"{nome} = ?" for nome in da_aggiornare)
    parametri = list(da_aggiornare.values()) + [veicolo_id]
    with _connessione() as conn:
        try:
            conn.execute(f"UPDATE veicoli SET {assegnazioni} WHERE id = ?", parametri)
        except sqlite3.IntegrityError as exc:
            if "targa" in str(exc).lower():
                raise TargaDuplicataError(
                    f"Esiste gia' un veicolo con la targa "
                    f"'{da_aggiornare.get('targa')}'."
                ) from exc
            raise


def aggiorna_km(veicolo_id: int, km_attuali: int) -> None:
    """Aggiornamento rapido dei chilometri attuali."""
    with _connessione() as conn:
        conn.execute(
            "UPDATE veicoli SET km_attuali = ? WHERE id = ?",
            (km_attuali, veicolo_id),
        )


def imposta_invio_automatico(veicolo_id: int, abilitato: bool) -> None:
    """Abilita (1) o disabilita (0) l'invio automatico per il veicolo."""
    with _connessione() as conn:
        conn.execute(
            "UPDATE veicoli SET invio_automatico = ? WHERE id = ?",
            (1 if abilitato else 0, veicolo_id),
        )


def imposta_ultimo_invio(veicolo_id: int, quando: str) -> None:
    """Registra data/ora dell'ultimo invio (formato YYYY-MM-DD HH:MM:SS)."""
    with _connessione() as conn:
        conn.execute(
            "UPDATE veicoli SET ultimo_invio_email = ? WHERE id = ?",
            (quando, veicolo_id),
        )


def elimina_veicolo(veicolo_id: int) -> None:
    """Elimina definitivamente il veicolo indicato."""
    with _connessione() as conn:
        conn.execute("DELETE FROM veicoli WHERE id = ?", (veicolo_id,))


def conta_veicoli() -> int:
    """Numero totale di veicoli in archivio."""
    with _connessione() as conn:
        (totale,) = conn.execute("SELECT COUNT(*) FROM veicoli").fetchone()
    return int(totale)
