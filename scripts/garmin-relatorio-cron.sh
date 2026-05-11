#!/usr/bin/env bash
# Wrapper para ingest diario via cron/systemd timer.
# Roda `garmin-relatorio cron-ingest` no diretorio do backend usando uv.
# Loga em backend/data/cron.log (alem do stdout que o cron captura).

set -uo pipefail

PROJECT_DIR="${GARMIN_RELATORIO_DIR:-$HOME/Documentos/garmin-relatorio}"
DAYS="${GARMIN_RELATORIO_DAYS:-7}"

cd "$PROJECT_DIR/backend" || {
  echo "Diretorio do projeto nao encontrado: $PROJECT_DIR" >&2
  exit 1
}

# uv precisa estar no PATH. Tenta caminho comum se nao estiver.
if ! command -v uv >/dev/null 2>&1; then
  for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    if [ -x "$candidate" ]; then
      export PATH="$(dirname "$candidate"):$PATH"
      break
    fi
  done
fi

exec uv run garmin-relatorio cron-ingest --days "$DAYS"
