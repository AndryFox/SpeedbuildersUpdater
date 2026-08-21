# SpeedbuildersUpdater

Bot Discord per la community **Fear Games**, dedicato alla gestione dei record di speedbuilding (World Records e WR Rounds). Automatizza l'invio, la revisione e la pubblicazione dei record, mantenendo aggiornate le classifiche del server tramite webhook.

## Funzionalità principali

- **Sottomissione record**: gli utenti inviano uno screenshot nel canale dedicato taggando l'amministratore; il bot instrada automaticamente lo screen in un canale di revisione con bottoni interattivi (Accept / Reject / Wr Round / Sim Wr).
- **Revisione tramite modal**: l'amministratore compila un modulo (build, tempo, giocatore) direttamente da Discord; il record viene salvato su database e la classifica pubblica aggiornata in automatico via webhook.
- **Classifiche automatiche**:
  - Ranking World Records per numero di record detenuti, con ruoli/badge assegnati in base al conteggio (da "Newbie" a "Greatest of All Time").
  - Ranking WR Rounds, con storico squadre/tempi.
- **Sistema di alias giocatori**: normalizza username diversi che si riferiscono alla stessa persona (`config.ALIASES`).
- **Gestione tornei**: invio messaggi di annuncio torneo e assegnazione/rimozione ruoli via comando.
- **Comando `/wrs`**: consente a ogni utente di consultare (in privato) tutti i record detenuti da un giocatore, con autocomplete sui nomi.
- **Keep-alive server**: piccolo server Flask in thread separato, usato per mantenere il bot attivo su hosting tipo Render.

## Struttura del progetto

| File | Descrizione |
|---|---|
| `main.py` | Entry point: inizializza il bot, gli intent, gli eventi (`on_message`, `on_ready`, ecc.) e il keep-alive server |
| `config.py` | Configurazione: token, ID canali/ruoli, alias giocatori, URL webhook (da variabili d'ambiente) |
| `database_utils.py` | Pool di connessioni PostgreSQL (asyncpg) e query sui record (World Records) |
| `rankings.py` | Generazione e aggiornamento delle classifiche (WRs e Rounds) |
| `tourneys.py` | Comandi slash per la gestione dei tornei e dei ruoli |
| `ui_components.py` | Modal e View di Discord (moduli di inserimento/modifica record, bottoni di revisione) |
| `requirements.txt` | Dipendenze Python |

## Requisiti

- Python 3.10+
- Un database PostgreSQL (per la persistenza dei record)
- Un bot Discord registrato su [Discord Developer Portal](https://discord.com/developers/applications), con l'intent `MESSAGE CONTENT` abilitato

## Installazione

```bash
git clone https://github.com/AndryFox/SpeedbuildersUpdater.git
cd SpeedbuildersUpdater
pip install -r requirements.txt
```

## Configurazione

Crea un file `.env` nella root del progetto con le seguenti variabili:

```env
DISCORD_TOKEN=il_token_del_tuo_bot
DATABASE_URL=postgresql://utente:password@host:porta/nome_db
WORLD_RECORDS_WEBHOOK_URL=https://discord.com/api/webhooks/...
RANKINGS_WEBHOOK_URL=https://discord.com/api/webhooks/...
TOURNEY_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Inoltre, in `config.py` vanno adattati agli ID del proprio server Discord:

- gli ID dei canali (`REVIEW_CHANNEL_ID`, `SUBMISSION_CHANNEL_ID`, `WR_CHANNEL_ID`, ecc.)
- `MIO_ID`, l'ID Discord dell'amministratore con permessi sui comandi riservati
- `ROLE_IDS`, la mappa tra soglie di record e ruoli del server
- `ALIASES`, per unificare eventuali username duplicati dello stesso giocatore

### Database

Il bot si aspetta almeno queste due tabelle su PostgreSQL:

```sql
CREATE TABLE WorldRecords (
    build_name TEXT NOT NULL,
    player_name TEXT NOT NULL,
    time DOUBLE PRECISION NOT NULL
);

CREATE TABLE BuildMessages (
    build_name TEXT PRIMARY KEY,
    message_id BIGINT NOT NULL
);
```

## Avvio

```bash
python main.py
```

Al primo avvio, usa i comandi `/setup_rankings` e `/setup_rounds` per pubblicare i messaggi iniziali delle classifiche, poi copia gli ID dei messaggi generati in `RANKING_WR_MSG_ID` e `RANKING_ROUNDS_MSG_ID` in `config.py`. Allo stesso modo, `/setup_tourney` genera l'ID da inserire in `TOURNEY_MESSAGE_ID`.

## Comandi principali

| Comando | Descrizione | Permessi |
|---|---|---|
| `/wrs` | Consulta i record di un giocatore | Tutti |
| `/manual_submit` | Invia un record in revisione per conto di un altro utente | Admin |
| `/addrole` / `/removerole` | Assegna o rimuove un ruolo | Admin |
| `/setup_tourney` | Pubblica il messaggio iniziale del torneo | Admin |
| `/setup_rankings` / `/setup_rounds` | Pubblica i messaggi iniziali delle classifiche | Admin |

## Stack tecnologico

- [discord.py](https://discordpy.readthedocs.io/) — interazione con l'API Discord
- [asyncpg](https://github.com/MagicStack/asyncpg) — accesso asincrono a PostgreSQL
- [Flask](https://flask.palletsprojects.com/) — keep-alive server per l'hosting
- [python-dotenv](https://github.com/theskumar/python-dotenv) — gestione delle variabili d'ambiente
