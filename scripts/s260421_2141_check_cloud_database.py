#!/usr/bin/env python3
"""
Probe the cloud PostgreSQL database using CLOUD_DB_* environment variables.

Loads ``.env`` from the project root (parent of ``scripts/``), connects with
SQLAlchemy, and prints non-secret diagnostics (database name, role, table
list). Exits with code 1 if the connection fails or required variables are
missing.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError


def _project_root() -> Path:
    """Return repository root (directory containing ``scripts/``)."""
    return Path(__file__).resolve().parent.parent


def _load_env(env_path: Path) -> None:
    """
    Load environment variables from a ``.env`` file.

    Uses override=True so file values win over inherited shell variables.

    Args:
        env_path: Path to the ``.env`` file.
    """
    if not env_path.is_file():
        print(f"error: env file not found: {env_path}", file=sys.stderr)
        sys.exit(1)
    load_dotenv(env_path, override=True)


def build_cloud_sqlalchemy_url() -> str:
    """
    Build a SQLAlchemy PostgreSQL URL from CLOUD_DB_* variables.

    Supports:
    - ``CLOUD_DB_URL`` as a full ``postgresql://`` or ``postgres://`` DSN.
    - ``CLOUD_DB_URL`` as ``host`` or ``host:port`` with separate user,
      password, and database name.

    Returns:
        str: URL using the ``postgresql+psycopg2`` driver.

    Raises:
        ValueError: If required variables are missing for the chosen form.
    """
    raw_url = os.environ.get("CLOUD_DB_URL", "").strip()
    user = os.environ.get("CLOUD_DB_USERNAME", "").strip()
    password = os.environ.get("CLOUD_DB_PASSWORD")
    dbname = os.environ.get("CLOUD_DB_NAME", "").strip()

    if raw_url.startswith("postgresql://") or raw_url.startswith(
        "postgres://"
    ):
        url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        return url

    if not all([user, dbname, raw_url]):
        raise ValueError(
            "Missing CLOUD_DB_USERNAME, CLOUD_DB_NAME, or CLOUD_DB_URL "
            "(or use a full postgresql:// URL in CLOUD_DB_URL)."
        )

    if ":" in raw_url:
        host_part, port_part = raw_url.rsplit(":", 1)
        try:
            port = int(port_part)
        except ValueError:
            host_part, port = raw_url, 5432
    else:
        host_part, port = raw_url, 5432

    if password:
        auth = f"{user}:{quote_plus(password)}"
    else:
        auth = user

    return (
        f"postgresql+psycopg2://{auth}@{host_part}:{port}/{dbname}"
    )


def run_checks(engine_url: str) -> None:
    """
    Connect and print database diagnostics.

    Args:
        engine_url: SQLAlchemy database URL.

    Raises:
        OperationalError: If the database rejects the connection.
    """
    safe = make_url(engine_url)
    print(
        "target:",
        f"host={safe.host} port={safe.port} database={safe.database} "
        f"user={safe.username}",
    )

    engine = create_engine(engine_url)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT current_database(), current_user, "
                "split_part(version(), ',', 1)"
            )
        ).fetchone()
        print("current_database:", row[0])
        print("current_user:", row[1])
        print("server:", row[2])

        tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "ORDER BY table_name"
            )
        ).fetchall()
        names = [t[0] for t in tables]
        print("public table count:", len(names))
        if names:
            print("public tables:")
            for name in names:
                print(f"  - {name}")


def main() -> None:
    """Parse CLI args, load env, and run cloud DB checks."""
    parser = argparse.ArgumentParser(
        description="Check connectivity to the cloud PostgreSQL database.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_project_root() / ".env",
        help="Path to .env (default: project root .env)",
    )
    args = parser.parse_args()

    _load_env(args.env_file)

    try:
        url = build_cloud_sqlalchemy_url()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        run_checks(url)
    except OperationalError as exc:
        print(f"error: connection failed: {exc.orig}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
