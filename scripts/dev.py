"""Start embedded PostgreSQL, migrate, seed, and run the API server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pgembed

ROOT = Path(__file__).resolve().parents[1]
PGDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "courier-guider-pgdata"
ENV_FILE = ROOT / ".env"


def to_asyncpg_url(uri: str) -> str:
    return uri.replace("postgresql://", "postgresql+asyncpg://", 1)


def update_env_database_url(database_url: str) -> None:
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    updated = False
    for index, line in enumerate(lines):
        if line.startswith("DATABASE_URL="):
            lines[index] = f"DATABASE_URL={database_url}"
            updated = True
            break

    if not updated:
        lines.append(f"DATABASE_URL={database_url}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_step(label: str, *args: str) -> None:
    print(f"\n==> {label}")
    subprocess.run(args, cwd=ROOT, check=True, env=os.environ.copy())


def start_postgres():
    import time

    from pgembed.utils import PostmasterInfo

    PGDATA.mkdir(parents=True, exist_ok=True)
    log_file = PGDATA / "log"
    if log_file.exists() and log_file.is_file():
        try:
            log_file.unlink()
        except OSError:
            pass

    try:
        return pgembed.get_server(str(PGDATA))
    except Exception as exc:
        print(f"Initial PostgreSQL startup raised: {exc}")
        print("Waiting for PostgreSQL recovery to finish...")

    for _ in range(90):
        info = PostmasterInfo.read_from_pgdata(PGDATA)
        if info is not None and info.is_running() and info.status == "ready":
            print(f"PostgreSQL ready at {info.get_uri()}")
            return info
        time.sleep(2)

    raise RuntimeError("PostgreSQL did not become ready in time")


def main() -> None:
    print("Starting embedded PostgreSQL (pgembed)...")
    postgres = start_postgres()
    database_url = to_asyncpg_url(postgres.get_uri())
    os.environ["DATABASE_URL"] = database_url
    update_env_database_url(database_url)
    print(f"Database ready: {database_url}")

    from app.config import get_settings

    get_settings.cache_clear()

    run_step("Running migrations", sys.executable, "-m", "alembic", "upgrade", "head")
    try:
        run_step("Seeding providers and knowledge", sys.executable, "scripts/seed.py")
    except subprocess.CalledProcessError:
        print("Warning: seed step failed; continuing with existing data.")
    try:
        run_step("Reseeding knowledge base", sys.executable, "scripts/reseed_knowledge.py")
    except subprocess.CalledProcessError:
        print("Warning: knowledge reseed failed; continuing.")

    print("\n==> Starting API server on http://127.0.0.1:8000")
    import uvicorn

    # reload=False keeps pgembed alive on Windows (reloader would orphan the DB process)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
