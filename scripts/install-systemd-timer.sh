#!/usr/bin/env bash
# Instala o timer systemd como user-service.
# Idempotente: pode rodar varias vezes sem efeito colateral.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$USER_UNIT_DIR"
cp "$SCRIPT_DIR/garmin-relatorio-ingest.service" "$USER_UNIT_DIR/"
cp "$SCRIPT_DIR/garmin-relatorio-ingest.timer" "$USER_UNIT_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now garmin-relatorio-ingest.timer

echo
echo "Timer ativo. Verifique com:"
echo "  systemctl --user list-timers garmin-relatorio-ingest.timer"
echo
echo "Para rodar manualmente uma vez (sem esperar o timer):"
echo "  systemctl --user start garmin-relatorio-ingest.service"
echo
echo "Logs:"
echo "  journalctl --user -u garmin-relatorio-ingest.service -e"
echo "  tail -f $HOME/Documentos/garmin-relatorio/backend/data/cron.log"
