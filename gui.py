"""Interfaccia grafica utente (customtkinter) e gestione eventi.

Comprende la finestra principale con tabella veicoli, log attivita' e
scheduler in background, piu' i dialoghi modali: nuovo/modifica veicolo,
aggiornamento rapido km, impostazioni SMTP/scheduler con test connessione,
conferma eliminazione e conferma invio email manuale.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk

import database as db
from config import AppConfig, load_config, save_config
from mailer import invia_promemoria, test_connessione
from scheduler import SchedulerThread, esegui_controllo_automatico

_FORMATI_DATA: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y %m %d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %m %Y",
)


def parsa_data_flessibile(valore: str) -> date:
    """Interpreta una data nei formati comuni e la normalizza in ``date``.

    Accetta: YYYY-MM-DD, YYYY MM DD, DD/MM/YYYY, DD-MM-YYYY, DD MM YYYY.
    Solleva ``ValueError`` se nessun formato viene riconosciuto.
    """
    pulito = " ".join(valore.strip().split())
    for formato in _FORMATI_DATA:
        try:
            return datetime.strptime(pulito, formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data non riconosciuta: {valore!r}")


COLONNE: list[tuple[str, int]] = [
    ("Cliente", 140),
    ("Email", 185),
    ("Targa", 85),
    ("Telaio", 125),
    ("Km Att.", 70),
    ("Km Scad.", 80),
    ("Scadenza", 95),
    ("GG Preav.", 75),
    ("Soglia KM", 75),
    ("Ultimo Invio", 130),
    ("Auto", 55),
    ("Azioni", 210),
]


class App(ctk.CTk):
    """Finestra principale dell'applicazione."""

    def __init__(self) -> None:
        super().__init__()
        self.title("ServicingAlert – Gestione Manutenzioni Veicoli")
        self.geometry("1400x780")
        self.minsize(1180, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._invii_in_corso: set[int] = set()

        self.scheduler = SchedulerThread(
            on_risultati=self._on_scheduler_risultati,
            get_intervallo_ore=lambda: load_config().intervallo_ore,
            primo_controllo_ritardo=10.0,
        )

        self._costruisci_layout()
        self._aggiorna_tabella()
        self.scheduler.start()
        self._log("Applicazione avviata – scheduler in background attivo.")

    def _costruisci_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        barra = ctk.CTkFrame(self, corner_radius=0)
        barra.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        ctk.CTkLabel(
            barra, text="🔧 ServicingAlert", font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left", padx=(10, 20), pady=10)

        ctk.CTkButton(
            barra, text="➕  Nuovo Veicolo", width=140, command=self._nuovo_veicolo
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            barra, text="⟳  Controlla Ora", width=130, command=self._controlla_ora
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            barra,
            text="⚙  Impostazioni",
            width=130,
            fg_color="#5d6d7e",
            hover_color="#46545f",
            command=self._apri_impostazioni,
        ).pack(side="left", padx=4)

        self.switch_scheduler = ctk.CTkSwitch(
            barra, text="Scheduler", command=self._toggle_scheduler
        )
        self.switch_scheduler.select()
        self.switch_scheduler.pack(side="right", padx=10)

        self.label_prossimo = ctk.CTkLabel(barra, text="Prossimo controllo: –")
        self.label_prossimo.pack(side="right", padx=10)

        self.frame_tabella = ctk.CTkScrollableFrame(
            self,
            label_text="Elenco Veicoli",
            label_font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.frame_tabella.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)

        pannello_log = ctk.CTkFrame(self)
        pannello_log.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 10))
        pannello_log.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            pannello_log, text="Log Attività", font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 0))
        self.text_log = ctk.CTkTextbox(pannello_log, height=130, wrap="word", state="disabled")
        self.text_log.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))

    @staticmethod
    def _configura_colonne(frame: ctk.CTkFrame) -> None:
        for indice, (_titolo, larghezza) in enumerate(COLONNE):
            frame.grid_columnconfigure(
                indice, minsize=larghezza, weight=1 if indice < 2 else 0
            )

    def _aggiorna_tabella(self) -> None:
        for widget in self.frame_tabella.winfo_children():
            widget.destroy()

        intestazione = ctk.CTkFrame(
            self.frame_tabella, fg_color=("gray78", "gray28"), corner_radius=6
        )
        intestazione.grid(row=0, column=0, columnspan=len(COLONNE), sticky="ew", pady=(2, 6))
        self._configura_colonne(intestazione)
        for indice, (titolo, _larghezza) in enumerate(COLONNE):
            ctk.CTkLabel(
                intestazione, text=titolo, font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=0, column=indice, sticky="ew", padx=4, pady=6)

        veicoli = db.get_veicoli()
        if not veicoli:
            ctk.CTkLabel(
                self.frame_tabella,
                text="Nessun veicolo in archivio.\nUsa '➕ Nuovo Veicolo' per iniziare.",
                text_color=("gray40", "gray60"),
                justify="center",
            ).grid(row=1, column=0, columnspan=len(COLONNE), pady=24)
            return

        for riga, veicolo in enumerate(veicoli, start=1):
            self._crea_riga(riga, veicolo)

    def _crea_riga(self, riga: int, veicolo: dict[str, Any]) -> None:
        riga_frame = ctk.CTkFrame(
            self.frame_tabella, fg_color=("gray92", "gray17"), corner_radius=6
        )
        riga_frame.grid(row=riga, column=0, columnspan=len(COLONNE), sticky="ew", pady=2)
        self._configura_colonne(riga_frame)

        valori = [
            veicolo["nome_cliente"],
            veicolo["email_cliente"],
            veicolo["targa"],
            veicolo["telaio"],
            f"{veicolo['km_attuali']:,}".replace(",", "."),
            f"{veicolo['km_scadenza']:,}".replace(",", "."),
            veicolo["data_scadenza"],
            veicolo["giorni_preavviso"],
            veicolo["soglia_km_preavviso"],
            veicolo["ultimo_invio_email"] or "–",
        ]
        for colonna, valore in enumerate(valori):
            ctk.CTkLabel(riga_frame, text=str(valore), anchor="w").grid(
                row=0, column=colonna, sticky="ew", padx=4, pady=6
            )

        switch = ctk.CTkSwitch(riga_frame, text="", width=48)
        if veicolo["invio_automatico"]:
            switch.select()
        switch.configure(
            command=lambda v=veicolo, s=switch: self._toggle_invio_automatico(v, s)
        )
        switch.grid(row=0, column=10, padx=4, pady=6)

        azioni = ctk.CTkFrame(riga_frame, fg_color="transparent")
        azioni.grid(row=0, column=11, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(
            azioni, text="Km", width=44, command=lambda v=veicolo: self._aggiorna_km(v)
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            azioni, text="✉", width=36, command=lambda v=veicolo: self._invio_manuale(v)
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            azioni,
            text="✎",
            width=36,
            fg_color="#2874a6",
            hover_color="#1b4f72",
            command=lambda v=veicolo: self._modifica_veicolo(v),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            azioni,
            text="🗑",
            width=36,
            fg_color="#b03a2e",
            hover_color="#7b241c",
            command=lambda v=veicolo: self._elimina_veicolo(v),
        ).pack(side="left", padx=2)

    def _dopo_salvataggio(self, messaggio: str) -> None:
        self._log(messaggio)
        self._aggiorna_tabella()

    def _toggle_invio_automatico(self, veicolo: dict[str, Any], switch: ctk.CTkSwitch) -> None:
        abilitato = bool(switch.get())
        db.imposta_invio_automatico(veicolo["id"], abilitato)
        stato = "abilitato" if abilitato else "disabilitato"
        self._log(f"Invio automatico {stato} per la targa {veicolo['targa']}.")

    def _nuovo_veicolo(self) -> None:
        DialogoVeicolo(self, veicolo=None, on_saved=self._dopo_salvataggio)

    def _modifica_veicolo(self, veicolo: dict[str, Any]) -> None:
        DialogoVeicolo(self, veicolo=veicolo, on_saved=self._dopo_salvataggio)

    def _aggiorna_km(self, veicolo: dict[str, Any]) -> None:
        DialogoKm(self, veicolo=veicolo, on_saved=self._dopo_salvataggio)

    def _elimina_veicolo(self, veicolo: dict[str, Any]) -> None:
        """Apre il dialogo modale di conferma eliminazione."""
        DialogoConfermaEliminazione(
            self, veicolo, on_conferma=self._elimina_veicolo_confermata
        )

    def _elimina_veicolo_confermata(self, veicolo: dict[str, Any]) -> None:
        db.elimina_veicolo(veicolo["id"])
        self._dopo_salvataggio(f"Veicolo con targa {veicolo['targa']} eliminato.")

    def _invio_manuale(self, veicolo: dict[str, Any]) -> None:
        """Apre il dialogo modale con riepilogo destinatario prima dell'invio."""
        DialogoInvioManuale(self, veicolo, on_conferma=self._invio_manuale_confermato)

    def _invio_manuale_confermato(self, veicolo: dict[str, Any]) -> None:
        """Invia subito il promemoria per il veicolo (in un thread separato)."""
        if veicolo["id"] in self._invii_in_corso:
            return
        self._invii_in_corso.add(veicolo["id"])
        self._log(f"Invio promemoria manuale per la targa {veicolo['targa']}...")

        def lavoro() -> None:
            try:
                cfg = load_config()
                invia_promemoria(cfg, veicolo)
                db.imposta_ultimo_invio(
                    veicolo["id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                self.after(
                    0,
                    self._dopo_salvataggio,
                    f"✉ Promemoria inviato a {veicolo['email_cliente']} "
                    f"(targa {veicolo['targa']}).",
                )
            except Exception as exc:
                self.after(
                    0,
                    self._log,
                    f"❌ Invio manuale fallito ({veicolo['targa']}): {exc}",
                )
            finally:
                self._invii_in_corso.discard(veicolo["id"])

        threading.Thread(
            target=lavoro, daemon=True, name=f"InvioManuale-{veicolo['targa']}"
        ).start()

    def _toggle_scheduler(self) -> None:
        if self.switch_scheduler.get():
            self.scheduler = SchedulerThread(
                on_risultati=self._on_scheduler_risultati,
                get_intervallo_ore=lambda: load_config().intervallo_ore,
                primo_controllo_ritardo=2.0,
            )
            self.scheduler.start()
            self._log("Scheduler attivato.")
        else:
            self.scheduler.stop()
            self._log("Scheduler disattivato.")

    def _controlla_ora(self) -> None:
        if self.scheduler.is_alive():
            self.scheduler.forza_controllo()
            self._log("Controllo manuale richiesto: lo scheduler lo eseguirà a breve.")
        else:
            self._log("Controllo manuale avviato (scheduler disattivato).")
            threading.Thread(target=self._controllo_una_tantum, daemon=True).start()

    def _controllo_una_tantum(self) -> None:
        risultati = esegui_controllo_automatico()
        prossimo = datetime.now() + timedelta(hours=load_config().intervallo_ore)
        self._on_scheduler_risultati(risultati, prossimo)

    def _on_scheduler_risultati(self, risultati: list[dict], prossimo: datetime) -> None:
        """Callback dello scheduler (thread worker): marshalling verso la GUI."""

        def aggiorna() -> None:
            if not risultati:
                self._log("Controllo automatico completato: nessuna notifica da inviare.")
            for esito in risultati:
                veicolo = esito["veicolo"]
                if esito["stato"] == "inviata":
                    self._log(
                        f"✉ Promemoria automatico inviato a {veicolo['email_cliente']} "
                        f"(targa {veicolo['targa']}) – {esito['dettaglio']}."
                    )
                else:
                    self._log(
                        f"❌ Invio automatico fallito (targa {veicolo['targa']}): "
                        f"{esito['dettaglio']}"
                    )
            self._aggiorna_tabella()
            self.label_prossimo.configure(text=f"Prossimo controllo: {prossimo:%d/%m/%Y %H:%M}")

        self.after(0, aggiorna)

    def _apri_impostazioni(self) -> None:
        DialogoImpostazioni(self, on_saved=self._log)

    def _log(self, messaggio: str) -> None:
        self.text_log.configure(state="normal")
        self.text_log.insert("end", f"[{datetime.now():%d/%m/%Y %H:%M:%S}] {messaggio}\n")
        self.text_log.see("end")
        self.text_log.configure(state="disabled")

    def _on_close(self) -> None:
        self.scheduler.stop()
        self.destroy()


class DialogoConfermaEliminazione(ctk.CTkToplevel):
    """Dialogo modale di conferma per l'eliminazione di un veicolo."""

    def __init__(
        self,
        master: ctk.CTk,
        veicolo: dict[str, Any],
        on_conferma: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(master)
        self.veicolo = veicolo
        self.on_conferma = on_conferma
        self.title("Conferma Eliminazione")
        self.geometry("480x270")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.bind("<Escape>", lambda _evento: self.destroy())

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(
            frame,
            text="⚠️  Attenzione",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#c0392b",
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            frame,
            text=(
                f"Sei sicuro di voler eliminare il veicolo con targa "
                f"{veicolo['targa']}?\nL'operazione non è reversibile."
            ),
            justify="left",
            anchor="w",
            wraplength=420,
        ).pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(
            frame,
            text=(
                f"Cliente: {veicolo['nome_cliente']}  –  "
                f"Email: {veicolo['email_cliente']}"
            ),
            text_color=("gray30", "gray70"),
            anchor="w",
            wraplength=420,
            justify="left",
        ).pack(fill="x")

        pulsanti = ctk.CTkFrame(frame, fg_color="transparent")
        pulsanti.pack(side="bottom", fill="x", pady=(12, 0))
        ctk.CTkButton(
            pulsanti,
            text="🗑  Conferma Eliminazione",
            fg_color="#b03a2e",
            hover_color="#7b241c",
            command=self._conferma,
        ).pack(side="right")
        btn_annulla = ctk.CTkButton(
            pulsanti,
            text="Annulla",
            width=100,
            fg_color="gray",
            hover_color="gray25",
            command=self.destroy,
        )
        btn_annulla.pack(side="right", padx=(0, 8))
        btn_annulla.focus_set()

    def _conferma(self) -> None:
        self.on_conferma(self.veicolo)
        self.destroy()


class DialogoInvioManuale(ctk.CTkToplevel):
    """Dialogo modale con riepilogo destinatario prima dell'invio manuale."""

    def __init__(
        self,
        master: ctk.CTk,
        veicolo: dict[str, Any],
        on_conferma: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(master)
        self.veicolo = veicolo
        self.on_conferma = on_conferma
        self.title("Invio Email Manuale")
        self.geometry("480x330")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.bind("<Escape>", lambda _evento: self.destroy())

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(
            frame,
            text="✉  Invio Promemoria Manuale",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            frame,
            text="Verifica i dati del destinatario prima di procedere con l'invio:",
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(6, 10))

        riepilogo = ctk.CTkFrame(frame)
        riepilogo.pack(fill="x")
        riepilogo.grid_columnconfigure(1, weight=1)
        righe = [
            ("Nome cliente", veicolo["nome_cliente"]),
            ("Email destinatario", veicolo["email_cliente"]),
            ("Targa", veicolo["targa"]),
        ]
        for riga, (etichetta, valore) in enumerate(righe):
            ctk.CTkLabel(
                riepilogo,
                text=etichetta,
                anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(row=riga, column=0, sticky="w", padx=12, pady=6)
            ctk.CTkLabel(riepilogo, text=str(valore), anchor="w").grid(
                row=riga, column=1, sticky="w", padx=12, pady=6
            )

        pulsanti = ctk.CTkFrame(frame, fg_color="transparent")
        pulsanti.pack(side="bottom", fill="x", pady=(14, 0))
        ctk.CTkButton(
            pulsanti, text="📤  Invia Email", command=self._conferma
        ).pack(side="right")
        ctk.CTkButton(
            pulsanti,
            text="Annulla",
            width=100,
            fg_color="gray",
            hover_color="gray25",
            command=self.destroy,
        ).pack(side="right", padx=(0, 8))

    def _conferma(self) -> None:
        self.on_conferma(self.veicolo)
        self.destroy()


class DialogoVeicolo(ctk.CTkToplevel):
    """Dialogo modale per inserimento/modifica di un veicolo."""

    CAMPI: list[tuple[str, str]] = [
        ("nome_cliente", "Nome Cliente *"),
        ("email_cliente", "Email Cliente *"),
        ("targa", "Targa *"),
        ("telaio", "Numero Telaio *"),
        ("km_attuali", "Km Attuali *"),
        ("km_scadenza", "Km Scadenza *"),
        ("data_scadenza", "Data Scadenza *"),
        ("giorni_preavviso", "Giorni di Preavviso"),
        ("soglia_km_preavviso", "Soglia Km di Preavviso"),
    ]

    def __init__(
        self,
        master: ctk.CTk,
        veicolo: dict[str, Any] | None,
        on_saved: Callable[[str], None],
    ) -> None:
        super().__init__(master)
        self.veicolo = veicolo
        self.on_saved = on_saved
        self.title("Modifica Veicolo" if veicolo else "Nuovo Veicolo")
        self.geometry("450x650")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.bind("<Escape>", lambda _evento: self.destroy())

        self.entries: dict[str, ctk.CTkEntry] = {}
        self._costruisci_form()

    def _costruisci_form(self) -> None:
        pulsanti = ctk.CTkFrame(self, fg_color="transparent")
        pulsanti.pack(side="bottom", fill="x", padx=16, pady=(0, 12))

        frame = ctk.CTkScrollableFrame(self)
        frame.pack(fill="both", expand=True, padx=12, pady=(10, 4))

        for chiave, etichetta in self.CAMPI:
            ctk.CTkLabel(frame, text=etichetta, anchor="w").pack(fill="x", pady=(4, 0))
            entry = ctk.CTkEntry(frame)
            entry.pack(fill="x")
            self.entries[chiave] = entry

        if self.veicolo:
            for chiave, entry in self.entries.items():
                entry.insert(0, str(self.veicolo[chiave]))
        else:
            self.entries["giorni_preavviso"].insert(0, "30")
            self.entries["soglia_km_preavviso"].insert(0, "1000")
            self.entries["data_scadenza"].configure(
                placeholder_text="GG/MM/AAAA o AAAA-MM-GG"
            )

        self.switch_invio = ctk.CTkSwitch(frame, text="Invio automatico email")
        if self.veicolo is None or self.veicolo["invio_automatico"]:
            self.switch_invio.select()
        self.switch_invio.pack(pady=(12, 8), anchor="w")

        ctk.CTkButton(
            pulsanti, text="💾  Salva Veicolo", command=self._salva
        ).pack(side="right")
        ctk.CTkButton(
            pulsanti,
            text="Annulla",
            width=100,
            fg_color="gray",
            hover_color="gray25",
            command=self.destroy,
        ).pack(side="right", padx=(0, 8))

    def _etichetta(self, chiave: str) -> str:
        return dict(self.CAMPI).get(chiave, chiave)

    def _int_con_default(
        self, valore: str, default: int, errori: list[str], nome: str
    ) -> int:
        if not valore:
            return default
        try:
            return int(valore)
        except ValueError:
            errori.append(f"- '{nome}' deve essere un numero intero")
            return default

    def _raccogli_dati(self) -> dict[str, Any]:
        grezzi = {chiave: entry.get().strip() for chiave, entry in self.entries.items()}
        errori: list[str] = []

        for chiave in ("nome_cliente", "email_cliente", "targa", "telaio"):
            if not grezzi[chiave]:
                errori.append(f"- '{self._etichetta(chiave)}' è obbligatorio")

        if grezzi["email_cliente"] and (
            "@" not in grezzi["email_cliente"]
            or "." not in grezzi["email_cliente"].split("@")[-1]
        ):
            errori.append("- L'email del cliente non è valida")

        try:
            km_attuali = int(grezzi["km_attuali"])
            km_scadenza = int(grezzi["km_scadenza"])
        except ValueError:
            errori.append("- Km attuali e km scadenza devono essere numeri interi")
            km_attuali = km_scadenza = 0

        if not grezzi["data_scadenza"]:
            errori.append("- 'Data Scadenza' è obbligatorio")
            data_scadenza = ""
        else:
            try:
                data_scadenza = parsa_data_flessibile(
                    grezzi["data_scadenza"]
                ).isoformat()
            except ValueError:
                errori.append(
                    "- Data di scadenza non riconosciuta: usa un formato valido, "
                    "es. 23/12/2026, 23-12-2026 oppure 2026-12-23"
                )
                data_scadenza = ""

        giorni_preavviso = self._int_con_default(
            grezzi["giorni_preavviso"], 30, errori, "Giorni di Preavviso"
        )
        soglia_km = self._int_con_default(
            grezzi["soglia_km_preavviso"], 1000, errori, "Soglia Km di Preavviso"
        )

        if errori:
            raise ValueError("\n".join(errori))

        return {
            "nome_cliente": grezzi["nome_cliente"],
            "email_cliente": grezzi["email_cliente"],
            "targa": grezzi["targa"].upper(),
            "telaio": grezzi["telaio"],
            "km_attuali": km_attuali,
            "km_scadenza": km_scadenza,
            "data_scadenza": data_scadenza,
            "giorni_preavviso": giorni_preavviso,
            "soglia_km_preavviso": soglia_km,
            "invio_automatico": 1 if self.switch_invio.get() else 0,
        }

    def _salva(self) -> None:
        try:
            dati = self._raccogli_dati()
        except ValueError as exc:
            messagebox.showerror("Dati non validi", str(exc), parent=self)
            return
        try:
            if self.veicolo:
                db.aggiorna_veicolo(self.veicolo["id"], **dati)
                messaggio = f"Veicolo con targa {dati['targa']} aggiornato."
            else:
                db.aggiungi_veicolo(**dati)
                messaggio = f"Veicolo con targa {dati['targa']} aggiunto."
        except db.TargaDuplicataError as exc:
            messagebox.showerror("Targa duplicata", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile salvare il veicolo:\n{exc}", parent=self)
            return
        self.on_saved(messaggio)
        self.destroy()


class DialogoKm(ctk.CTkToplevel):
    """Dialogo rapido per l'aggiornamento dei km attuali di un veicolo."""

    def __init__(
        self,
        master: ctk.CTk,
        veicolo: dict[str, Any],
        on_saved: Callable[[str], None],
    ) -> None:
        super().__init__(master)
        self.veicolo = veicolo
        self.on_saved = on_saved
        self.title(f"Aggiorna km – {veicolo['targa']}")
        self.geometry("340x180")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=16, pady=12)

        km_formattati = f"{veicolo['km_attuali']:,}".replace(",", ".")
        ctk.CTkLabel(frame, text=f"Km attuali rilevati: {km_formattati} km", anchor="w").pack(fill="x")
        self.entry_km = ctk.CTkEntry(frame, placeholder_text="Nuovo totale km")
        self.entry_km.pack(fill="x", pady=6)
        self.entry_km.focus_set()
        self.bind("<Return>", lambda _evento: self._salva())
        self.bind("<Escape>", lambda _evento: self.destroy())

        pulsanti = ctk.CTkFrame(frame, fg_color="transparent")
        pulsanti.pack(fill="x", pady=6)
        ctk.CTkButton(pulsanti, text="💾  Salva", command=self._salva).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            pulsanti,
            text="Annulla",
            width=90,
            fg_color="gray",
            hover_color="gray25",
            command=self.destroy,
        ).pack(side="left")

    def _salva(self) -> None:
        try:
            km = int(self.entry_km.get().strip())
            if km < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Dati non validi", "Inserire un numero intero di km valido.", parent=self
            )
            return
        db.aggiorna_km(self.veicolo["id"], km)
        self.on_saved(
            f"Km aggiornati per la targa {self.veicolo['targa']}: "
            f"{km:,} km.".replace(",", ".")
        )
        self.destroy()


class DialogoImpostazioni(ctk.CTkToplevel):
    """Finestra di configurazione parametri SMTP e preferenze scheduler."""

    def __init__(self, master: ctk.CTk, on_saved: Callable[[str], None]) -> None:
        super().__init__(master)
        self.on_saved = on_saved
        self.title("Impostazioni – SMTP & Scheduler")
        self.geometry("470x660")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.bind("<Escape>", lambda _evento: self.destroy())

        self.cfg = load_config()
        self.entries: dict[str, ctk.CTkEntry] = {}
        self._costruisci_form()

    def _costruisci_form(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=16, pady=10)

        campi = [
            ("smtp_host", "SMTP Host", str(self.cfg.smtp_host), ""),
            ("smtp_porta", "SMTP Porta", str(self.cfg.smtp_porta), "es. 587 (STARTTLS) o 465 (SSL)"),
            ("mittente", "Mittente (email officina)", self.cfg.mittente, ""),
            ("password", "Password / App Password", self.cfg.password, ""),
            ("nome_officina", "Nome Officina", self.cfg.nome_officina, ""),
            ("intervallo_ore", "Intervallo di controllo (ore)", str(self.cfg.intervallo_ore), ""),
            ("cooldown_giorni", "Cooldown anti-spam (giorni)", str(self.cfg.cooldown_giorni), ""),
        ]
        for chiave, etichetta, valore, placeholder in campi:
            ctk.CTkLabel(frame, text=etichetta, anchor="w").pack(fill="x", pady=(6, 0))
            entry = ctk.CTkEntry(
                frame, placeholder_text=placeholder, show="*" if chiave == "password" else ""
            )
            entry.insert(0, valore)
            entry.pack(fill="x")
            self.entries[chiave] = entry

        self.var_ssl = ctk.CTkCheckBox(
            frame, text="Usa connessione SSL implicita (SMTPS, porta 465).\n"
            "Se deselezionato: STARTTLS (porta 587)."
        )
        if self.cfg.usa_ssl:
            self.var_ssl.select()
        self.var_ssl.pack(pady=(12, 4), anchor="w")

        self.label_test = ctk.CTkLabel(frame, text="", wraplength=410, justify="left")
        self.label_test.pack(fill="x", pady=(4, 0))

        pulsanti = ctk.CTkFrame(frame, fg_color="transparent")
        pulsanti.pack(fill="x", pady=12)
        self.btn_test = ctk.CTkButton(
            pulsanti,
            text="🔌  Test Connessione",
            fg_color="#5d6d7e",
            hover_color="#46545f",
            command=self._test_connessione,
        )
        self.btn_test.pack(side="left", padx=(0, 8))
        ctk.CTkButton(pulsanti, text="💾  Salva", command=self._salva).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            pulsanti,
            text="Annulla",
            width=90,
            fg_color="gray",
            hover_color="gray25",
            command=self.destroy,
        ).pack(side="left")

    def _raccogli_cfg(self) -> AppConfig:
        valori = {chiave: entry.get().strip() for chiave, entry in self.entries.items()}
        errori: list[str] = []

        if not valori["smtp_host"]:
            errori.append("- L'host SMTP è obbligatorio")
        if not valori["mittente"] or "@" not in valori["mittente"]:
            errori.append("- Il mittente deve essere un'email valida")

        try:
            porta = int(valori["smtp_porta"])
            if not 1 <= porta <= 65535:
                raise ValueError
        except ValueError:
            errori.append("- La porta SMTP deve essere un intero tra 1 e 65535")
            porta = 587

        try:
            intervallo = float(valori["intervallo_ore"].replace(",", "."))
            if intervallo <= 0:
                raise ValueError
        except ValueError:
            errori.append("- L'intervallo di controllo deve essere un numero > 0 (ore)")
            intervallo = 6.0

        try:
            cooldown = int(valori["cooldown_giorni"])
            if cooldown < 0:
                raise ValueError
        except ValueError:
            errori.append("- Il cooldown deve essere un intero >= 0 (giorni)")
            cooldown = 30

        if errori:
            raise ValueError("\n".join(errori))

        return AppConfig(
            smtp_host=valori["smtp_host"],
            smtp_porta=porta,
            mittente=valori["mittente"],
            password=valori["password"],
            usa_ssl=bool(self.var_ssl.get()),
            nome_officina=valori["nome_officina"] or "Officina Meccanica",
            intervallo_ore=intervallo,
            cooldown_giorni=cooldown,
        )

    def _test_connessione(self) -> None:
        try:
            cfg = self._raccogli_cfg()
        except ValueError as exc:
            messagebox.showerror("Dati non validi", str(exc), parent=self)
            return
        self.btn_test.configure(state="disabled", text="Test in corso...")
        self.label_test.configure(text="")

        def lavoro() -> None:
            ok, messaggio = test_connessione(cfg)
            self.after(0, self._mostra_esito_test, ok, messaggio)

        threading.Thread(target=lavoro, daemon=True, name="TestSMTP").start()

    def _mostra_esito_test(self, ok: bool, messaggio: str) -> None:
        self.btn_test.configure(state="normal", text="🔌  Test Connessione")
        self.label_test.configure(
            text=("✅ " if ok else "❌ ") + messaggio,
            text_color="#2e7d32" if ok else "#c0392b",
        )

    def _salva(self) -> None:
        try:
            cfg = self._raccogli_cfg()
        except ValueError as exc:
            messagebox.showerror("Dati non validi", str(exc), parent=self)
            return
        save_config(cfg)
        self.on_saved("Impostazioni salvate.")
        self.destroy()
