# LocalDB viewer

A tiny Flask web app to connect to PostgreSQL, browse tables, and run SQL. Single file, SQLite-backed connection memory.

## Run

```sh
./run.sh                # POSIX / git-bash
run.bat                 # Windows
docker compose up -d    # background
```

Open http://localhost:5000.

## Features

- Connect to any PostgreSQL database.
- Saved connections persist across restarts (SQLite at `ldv.db`, or `./data/ldv.db` in Docker).
- Sortable, sticky-header tables. NULLs, booleans, and numbers styled distinctly.
- Run arbitrary SQL (Ctrl/Cmd+Enter to submit). Results capped at 500 rows.

## Config

| Env var      | Default              | Purpose                          |
|--------------|----------------------|----------------------------------|
| `PORT`       | `5000`               | HTTP port                        |
| `LDV_DB`     | `ldv.db`             | SQLite file for saved connections|
| `LDV_SECRET` | `dev-only-change-me` | Flask session key                |

## Notes

Local dev tool. Passwords are stored plaintext in SQLite — don't expose this beyond your machine.
