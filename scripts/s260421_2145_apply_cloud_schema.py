#!/usr/bin/env python3
"""
Apply dish_healthiness DDL to the cloud database from CLOUD_DB_* in .env.

Runs, in order:

1. ``backend/sql/create_tables.sql`` — dish_image_query_prod_dev indexes and
   constraints, personalized_food_descriptions, nutrition_foods,
   nutrition_myfcd_nutrients (all idempotent).
2. ``backend/sql/cloud_deploy_patch.sql`` — extra columns and indexes to match
   local delta where needed for deployment.

Requires ``psql`` on PATH. Exits non-zero on failure.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


def _project_root() -> Path:
    """Return repository root."""
    return Path(__file__).resolve().parent.parent


def _load_env(env_path: Path) -> None:
    """Load ``.env`` with file values overriding the shell."""
    if not env_path.is_file():
        print(f"error: env file not found: {env_path}", file=sys.stderr)
        sys.exit(1)
    load_dotenv(env_path, override=True)


def _psql_target() -> tuple[str, str, str, str, str]:
    """
    Return (host, port, username, password, database) for psql.

    Returns:
        Connection parameters from CLOUD_DB_* or a full DSN in CLOUD_DB_URL.
    """
    raw_url = os.environ.get("CLOUD_DB_URL", "").strip()
    user = os.environ.get("CLOUD_DB_USERNAME", "").strip()
    password = os.environ.get("CLOUD_DB_PASSWORD") or ""
    dbname = os.environ.get("CLOUD_DB_NAME", "").strip()

    if raw_url.startswith("postgresql://") or raw_url.startswith(
        "postgres://"
    ):
        parsed = urlparse(raw_url)
        host = parsed.hostname or "localhost"
        port = str(parsed.port or 5432)
        user = (parsed.username or user or "").strip()
        dbname = (parsed.path or "").lstrip("/") or dbname
        if parsed.password:
            password = parsed.password
        return host, port, user, password, dbname

    if not all([user, dbname, raw_url]):
        print(
            "error: set CLOUD_DB_USERNAME, CLOUD_DB_NAME, CLOUD_DB_URL "
            "or a full postgresql:// URL in CLOUD_DB_URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    if ":" in raw_url:
        host_part, port_part = raw_url.rsplit(":", 1)
        try:
            port = str(int(port_part))
        except ValueError:
            host_part, port = raw_url, "5432"
    else:
        host_part, port = raw_url, "5432"

    return host_part, port, user, password, dbname


def _run_psql(
    host: str,
    port: str,
    user: str,
    password: str,
    database: str,
    sql_file: Path,
) -> None:
    """
    Execute a SQL file with psql and ON_ERROR_STOP.

    Args:
        host: PostgreSQL host.
        port: Port string.
        user: Role name.
        password: Password (may be empty).
        database: Database name.
        sql_file: Path to ``.sql`` file.
    """
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    cmd = [
        "psql",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(sql_file),
    ]
    print("running:", sql_file.name)
    subprocess.run(cmd, env=env, check=True)


def main() -> None:
    """Parse args and apply SQL files to cloud."""
    parser = argparse.ArgumentParser(
        description="Apply create_tables.sql + cloud patch via psql.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_project_root() / ".env",
        help="Path to .env",
    )
    args = parser.parse_args()

    _load_env(args.env_file)
    host, port, user, password, dbname = _psql_target()

    print(
        "cloud:",
        f"{host}:{port}/{dbname} user={user}",
    )

    root = _project_root()
    files = [
        root / "backend" / "sql" / "create_tables.sql",
        root / "backend" / "sql" / "cloud_deploy_patch.sql",
    ]
    for path in files:
        if not path.is_file():
            print(f"error: missing {path}", file=sys.stderr)
            sys.exit(1)
        _run_psql(host, port, user, password, dbname, path)

    print("done.")


if __name__ == "__main__":
    main()
