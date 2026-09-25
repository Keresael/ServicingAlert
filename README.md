# 🔧 ServicingAlert

A desktop app for auto repair shops that keeps an eye on all the vehicles'
maintenance schedules and reminds customers when it's time for a service —
without anyone having to track it by hand.

## What it does

- Keeps a **vehicle registry** (customer, plate, VIN, mileage, due dates) in a
  local SQLite database.
- **Sends reminder emails to customers** when a vehicle gets close to its due
  date — either by time (e.g. "in 30 days") or by mileage (e.g. "under 1000 km").
- Sending is **automatic**: a background check runs every few hours and fires
  off the reminders that are due, with no input needed.
- Has **anti-spam** built in: each customer gets at most one reminder per cycle
  (configurable cooldown), and sending can be disabled per vehicle.

## How it works

Everything is local — there's no server, it all runs on the shop's machine.

- Data lives in `officina.db`, a SQLite file created automatically next to the
  executable (or in the project folder while developing).
- A **background thread** periodically scans the vehicles: for each one it
  compares the due date and mileage against the configured thresholds, decides
  whether to notify, and — if outside the cooldown — sends the email over
  **SMTP**. Host, port, sender and password are set once in Settings, with a
  connection test to make sure the credentials are right.
- **Configuration** (SMTP, shop name, check interval, cooldown) is stored in
  `config.ini`, right next to the data.
- A **GUI** (customtkinter) ties it all together: registry, quick mileage
  update, manual reminder send, activity log and settings.

## A look at the modules

| File           | Role                                                              |
|----------------|-------------------------------------------------------------------|
| `main.py`      | Startup: initializes database, config and GUI                     |
| `gui.py`       | Graphical interface and event handling                            |
| `database.py`  | SQLite: schema and vehicle operations                             |
| `mailer.py`    | SMTP connection and email composition                             |
| `scheduler.py` | Background thread that decides when to send                       |
| `config.py`    | Reads/writes `config.ini`                                         |
| `paths.py`     | Resolves where db and config live (development / packaged build)  |

> `officina.db` and `config.ini` are created by themselves on first run, so the
> app can be moved to any writable folder and just pick up from there.