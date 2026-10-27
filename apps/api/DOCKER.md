# Docker

Copy `.env.example` to `.env` and set `DATABASE_URL` to your Neon **DEV branch** URL, never the main/production branch. Keep `apps/api/.env` local; it is gitignored.

From the repository root:

```sh
docker compose up --build
```

This runs the API against the database configured by `DATABASE_URL`.

Optional services:

```sh
docker compose --profile ai up
docker compose exec ollama ollama pull qwen3:8b

docker compose --profile local-db up
```

The local database uses the `sowo` user, password, and database name. To point the API at it, set `DATABASE_URL=postgresql+psycopg://sowo:sowo@db:5432/sowo` in `apps/api/.env`.

View API logs and stop the stack:

```sh
docker compose logs -f api
docker compose down
```

Add `-v` to `docker compose down` to wipe the named data volumes.
