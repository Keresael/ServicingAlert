# 🔧 ServicingAlert

Un'applicazione desktop per officine meccaniche che tiene d'occhio le
manutenzioni di tutti i veicoli e ricorda ai clienti quando è il momento del
tagliando — senza che qualcuno debba pensarci a mano.

## Cosa fa

- Tiene un **archivio dei veicoli** (cliente, targa, telaio, chilometraggio,
  scadenze) in un database SQLite locale.
- **Invia email di promemoria ai clienti** quando un veicolo si avvicina alla
  scadenza, sia per tempo (es. "tra 30 giorni") sia per chilometraggio
  (es. "sotto i 1000 km").
- L'invio è **automatico**: un controllo in background gira ogni poche ore e
  spedisce i promemoria dovuti, senza interazione.
- Ha un **anti-spam** integrato: ogni cliente riceve al massimo un promemoria
  per ciclo (cooldown configurabile), e l'invio si può disattivare per il
  singolo veicolo.

## Come funziona

L'intera logica è locale: non c'è server, tutto gira sulla macchina
dell'officina.

- I dati vivono in `officina.db`, un file SQLite creato automaticamente accanto
  all'eseguibile (o nella cartella del progetto in sviluppo).
- Un **thread in background** controlla periodicamente i veicoli: per ognuno
  confronta la data di scadenza e i km rispetto alle soglie configurate, decide
  se notificare e — fuori dal cooldown — invia l'email via **SMTP**. Host,
  porta, mittente e password si impostano una volta nelle Impostazioni, con un
  test di connessione per verificare che le credenziali siano giuste.
- La **configurazione** (SMTP, nome officina, intervallo di controllo, cooldown)
  è salvata in `config.ini`, sempre accanto ai dati.
- Una **GUI** (customtkinter) raccoglie tutto: archivio, modifica rapida dei km,
  invio manuale del promemoria, log attività e impostazioni.

## Un'occhiata ai moduli

| File          | Ruolo                                                        |
|---------------|--------------------------------------------------------------|
| `main.py`     | Avvio: inizializza database, config e GUI                    |
| `gui.py`      | Interfaccia grafica ed eventi                                 |
| `database.py` | SQLite: schema e operazioni sui veicoli                       |
| `mailer.py`   | Connessione SMTP e composizione delle email                   |
| `scheduler.py`| Thread in background che decide quando inviare                |
| `config.py`   | Lettura/scrittura di `config.ini`                             |
| `paths.py`    | Risolve dove stanno database e config (sviluppo / eseguibile) |

> I file `officina.db` e `config.ini` nascono autonomamente alla prima
> esecuzione, quindi l'app si può spostare in una cartella scrivibile e
> riparte da lì.