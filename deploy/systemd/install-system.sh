#!/usr/bin/env bash
#
# Устанавливает Albion как СИСТЕМНЫЕ службы systemd (старт при загрузке до
# входа любого пользователя). Требует root — запускать с sudo:
#
#   sudo deploy/systemd/install-system.sh
#
# Скрипт идемпотентен: можно запускать повторно после правок юнитов.
#
# ВНИМАНИЕ: системные службы занимают те же порты (8000/9000), что и
# пользовательские, поэтому пользовательские здесь же отключаются.

set -euo pipefail

RUN_USER="${ALBION_USER:-alexice}"
LINK="/home/${RUN_USER}/albion"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Нужны права root: sudo $0" >&2
    exit 1
fi

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SRC_DIR}/../.." && pwd)"
UNITS="${SRC_DIR}/system"

if [[ ! -f "${PROJECT_DIR}/backend/main.py" ]]; then
    echo "Не вижу backend/main.py рядом: ${PROJECT_DIR}" >&2
    exit 1
fi

echo "Проект:  ${PROJECT_DIR}"
echo "Симлинк: ${LINK}"

# systemd не принимает пробелы и скобки в WorkingDirectory — нужен симлинк.
if [[ "$(readlink -f "${LINK}" 2>/dev/null || true)" != "${PROJECT_DIR}" ]]; then
    ln -sfn "${PROJECT_DIR}" "${LINK}"
    echo "  создан симлинк ${LINK}"
else
    echo "  симлинк уже верный"
fi

install -m 644 "${UNITS}/albion-backend.service" /etc/systemd/system/
install -m 644 "${UNITS}/albion-frontend.service" /etc/systemd/system/
echo "Юниты скопированы в /etc/systemd/system/"

systemctl daemon-reload
systemctl enable --now albion-backend.service albion-frontend.service
echo "Службы включены и запущены"

# Освобождаем порты: пользовательские копии больше не нужны.
if [[ -d "/home/${RUN_USER}/.config/systemd/user" ]]; then
    sudo -u "${RUN_USER}" XDG_RUNTIME_DIR="/run/user/$(id -u "${RUN_USER}")" \
        systemctl --user disable --now \
        albion-backend.service albion-frontend.service 2>/dev/null \
        && echo "Пользовательские службы отключены" \
        || echo "Пользовательские службы не были включены"
fi

echo
systemctl --no-pager --lines=0 status albion-backend.service albion-frontend.service || true
echo
echo "Готово. Логи: journalctl -u albion-backend -f"
