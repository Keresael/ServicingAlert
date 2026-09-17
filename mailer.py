"""Gestione della connessione SMTP, formattazione del messaggio e invio.

Supporta connessioni STARTTLS (porta 587) e SSL implicito (porta 465).
Il template dell'email di promemoria e' fisso e conforme alle specifiche.
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

from config import AppConfig

OGGETTO_TEMPLATE = "Promemoria Manutenzione Programmata - Targa: {targa}"

CORPO_TEMPLATE = """Gentile {nome_cliente},
Le ricordiamo che il Suo veicolo necessita del tagliando di manutenzione programmata.

Dettagli Veicolo:
- Targa: {targa}
- Numero Telaio: {telaio}
- Scadenza Chilometrica: {km_scadenza} km (Ultimi rilevati: {km_attuali} km)
- Scadenza Temporale: entro il {data_scadenza}

La invitiamo a contattare la nostra officina per concordare un appuntamento.

Cordiali saluti,
{nome_officina}
"""


def costruisci_oggetto(targa: str) -> str:
    """Costruisce l'oggetto dell'email di promemoria."""
    return OGGETTO_TEMPLATE.format(targa=targa)


def costruisci_corpo(veicolo: dict[str, Any], nome_officina: str) -> str:
    """Costruisce il corpo testuale del promemoria per il veicolo."""
    return CORPO_TEMPLATE.format(nome_officina=nome_officina, **veicolo)


def _connetti_e_login(cfg: AppConfig) -> smtplib.SMTP:
    """Apre la connessione SMTP (STARTTLS o SSL) ed effettua il login."""
    timeout = 30
    contesto = ssl.create_default_context()
    if cfg.usa_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            cfg.smtp_host, cfg.smtp_porta, timeout=timeout, context=contesto
        )
    else:
        server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=timeout)
        server.ehlo()
        server.starttls(context=contesto)
        server.ehlo()
    server.login(cfg.mittente, cfg.password)
    return server


def invia_email(cfg: AppConfig, destinatario: str, oggetto: str, corpo: str) -> None:
    """Invia un'email in testo semplice; solleva eccezione in caso di errore."""
    messaggio = MIMEText(corpo, "plain", "utf-8")
    messaggio["Subject"] = oggetto
    messaggio["From"] = formataddr((cfg.nome_officina, cfg.mittente))
    messaggio["To"] = destinatario
    with _connetti_e_login(cfg) as server:
        server.send_message(messaggio)


def invia_promemoria(cfg: AppConfig, veicolo: dict[str, Any]) -> None:
    """Costruisce e invia l'email di promemoria manutenzione per il veicolo."""
    oggetto = costruisci_oggetto(veicolo["targa"])
    corpo = costruisci_corpo(veicolo, cfg.nome_officina)
    invia_email(cfg, veicolo["email_cliente"], oggetto, corpo)


def test_connessione(cfg: AppConfig) -> tuple[bool, str]:
    """Verifica i parametri SMTP aprendo una connessione con login.

    Restituisce una tupla ``(successo, messaggio)`` adatta alla GUI.
    """
    try:
        with _connetti_e_login(cfg) as server:
            stato, _ = server.noop()
        return True, (
            f"Connessione riuscita a {cfg.smtp_host}:{cfg.smtp_porta} "
            f"(NOOP {stato}). Credenziali valide."
        )
    except Exception as exc:
        return False, f"Connessione fallita: {exc}"
