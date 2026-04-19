#!/usr/bin/env bash
# Pair with scripts/cleanup/260419_personalized_data_card_purge.sql.
# Runs the SQL purge via psql, then removes orphaned image files for Alan
# and every other user. Safe to re-run (idempotent).
#
# Requires DB_URL, DB_USERNAME, DB_NAME to be set in the environment (the
# same vars start_app.sh exports).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Running SQL purge..."
psql -h "${DB_URL:-localhost}" -U "${DB_USERNAME:-alan}" -d "${DB_NAME:-delta}" \
     -f "$SCRIPT_DIR/260419_personalized_data_card_purge.sql"

echo "Removing orphaned image files under data/images/ ..."
rm -f "$PROJECT_ROOT"/data/images/*_u*_dish*.jpg || true

echo "Done."
