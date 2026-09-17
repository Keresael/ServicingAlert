# 🔧 ServicingAlert – Gestione Manutenzioni Veicoli

Applicazione desktop in **Python 3.10+** per officine meccaniche: monitora le
scadenze di manutenzione dei veicoli (temporali e chilometriche) e invia
automaticamente email di promemoria ai clienti tramite uno scheduler in
background.

## Funzionalità

- 🚗 **Archivio veicoli** su SQLite (`officina.db`): inserimento, modifica,
  aggiornamento rapido km, eliminazione
- 🔔 **Notifiche automatiche** su scadenza temporale (`giorni_preavviso`) o
  chilometrica (`soglia_km_preavviso`)
- 🕒 **Scheduler in background** (thread daemon) con intervallo di controllo
  configurabile in ore
- 🔕 **Anti-spam**: switch di abilitazione/disabilitazione invio per singolo
  veicolo + cooldown di 30 giorni (configurabile)
- ✉️ **Configurazione SMTP** (STARTTLS/SSL, App-Password) salvata in
  `config.ini`, con pulsante di test connessione
- 📨 **Invio manuale** del promemoria per il singolo veicolo
- 📋 **Log attività** direttamente nella GUI

## Struttura del progetto

| File | Descrizione |
|------|-------------|
| `main.py` | Entry point: inizializza DB, config e GUI |
| `gui.py` | Interfaccia grafica (customtkinter) e gestione eventi |
| `database.py` | Inizializzazione SQLite e funzioni CRUD |
| `mailer.py` | Connessione SMTP, formattazione messaggio e invio |
| `scheduler.py` | Thread in background per il controllo delle scadenze |
| `config.py` | Lettura/scrittura `config.ini` |
| `paths.py` | Risoluzione percorsi (sviluppo / eseguibile Windows PyInstaller) |
| `requirements.txt` | Dipendenze |

## Installazione ed esecuzione

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

## Configurazione iniziale

1. Avvia l'applicazione e apri **⚙ Impostazioni**.
2. Inserisci SMTP Host, Porta (587 per STARTTLS, 465 per SSL), email mittente
   e **App Password** (per Gmail: Account Google → Sicurezza → Password app).
3. Premi **🔌 Test Connessione** e poi **💾 Salva**.
4. Imposta l'intervallo di controllo (ore) e il cooldown anti-spam (giorni).

I file `config.ini` e `officina.db` vengono creati automaticamente nella
cartella dell'applicazione.

## Logica di notifica

L'email viene inviata **solo se** il veicolo ha `invio_automatico = 1` e si
verifica almeno una di queste condizioni:

- scadenza temporale: giorni rimanenti fino a `data_scadenza` ≤ `giorni_preavviso`
- scadenza chilometrica: `km_scadenza - km_attuali` ≤ `soglia_km_preavviso`

L'invio viene saltato se l'ultimo è avvenuto meno di `cooldown_giorni` giorni
fa; a invio avvenuto con successo viene registrata data/ora in
`ultimo_invio_email`.

## Build eseguibile Windows (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name ServicingAlert main.py
```

L'eseguibile risolve `officina.db` e `config.ini` accanto al file `.exe`
(vedi `paths.py`): copia il binario in una cartella scrivibile prima di
avviarlo.
