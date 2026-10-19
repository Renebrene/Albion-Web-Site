#!/usr/bin/env bash
# Настройка PostgreSQL 16 для Albion по результатам замеров.
#
# Запускать от root (или через sudo) на сервере с БД:
#   sudo deploy/postgresql-tuning.sh
#
# Что меняется:
#   • shared_preload_libraries = 'pg_stat_statements' — профилирование запросов;
#   • idle_in_transaction_session_timeout = '60s'     — защита от зависших транзакций;
#   • maintenance_work_mem = '128MB'                  — запас для VACUUM/индексов;
#   • effective_cache_size = '8GB'                    — подсказка планировщику.
#
# Что НЕ меняется намеренно:
#   • shared_buffers — 128 МБ достаточно: обе базы занимают ~86 МБ;
#   • max_connections — 100; под нагрузкой наблюдался пик 19 соединений;
#   • work_mem — 4 МБ; этого хватает, temp-файлов нет.
#
# Внимание: ALTER SYSTEM SET shared_preload_libraries требует перезапуска
# кластера. В этом же кластере есть другие базы, поэтому выбирайте окно
# обслуживания. Скрипт идемпотентен.

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите скрипт через sudo: sudo $0" >&2
  exit 1
fi

PSQL=(sudo -u postgres psql -v ON_ERROR_STOP=1)
ALBION_DB="${ALBION_DB_NAME:-albion}"

echo "== PostgreSQL: текущие значения =="
"${PSQL[@]}" -Atc "
  SELECT name || ' = ' || setting || coalesce(' ' || unit, '')
  FROM pg_settings
  WHERE name IN ('shared_preload_libraries','idle_in_transaction_session_timeout',
                 'maintenance_work_mem','effective_cache_size',
                 'shared_buffers','work_mem','max_connections')
  ORDER BY name;
"

current_preload="$("${PSQL[@]}" -Atc "SHOW shared_preload_libraries")"
if [[ -n "$current_preload" && "$current_preload" != "pg_stat_statements" ]]; then
  echo
  echo "ОШИБКА: shared_preload_libraries уже содержит: $current_preload" >&2
  echo "Добавьте pg_stat_statements вручную, чтобы не перезаписать настройку." >&2
  exit 1
fi

echo
echo "== Применяем настройки =="
"${PSQL[@]}" -c "ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';"
"${PSQL[@]}" -c "ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';"
"${PSQL[@]}" -c "ALTER SYSTEM SET maintenance_work_mem = '128MB';"
"${PSQL[@]}" -c "ALTER SYSTEM SET effective_cache_size = '8GB';"

pending="$("${PSQL[@]}" -Atc "SELECT pending_restart FROM pg_settings WHERE name = 'shared_preload_libraries'")"
if [[ "$pending" == "t" ]]; then
  echo
  echo "== Перезапуск PostgreSQL (нужен для shared_preload_libraries) =="
  systemctl restart postgresql
else
  "${PSQL[@]}" -c "SELECT pg_reload_conf();" >/dev/null
fi

echo
echo "== Создаём расширение pg_stat_statements в базе $ALBION_DB =="
"${PSQL[@]}" -d "$ALBION_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

echo
echo "== Проверка =="
"${PSQL[@]}" -Atc "
  SELECT name || ' = ' || setting || coalesce(' ' || unit, '') ||
         ' (pending_restart=' || pending_restart || ')'
  FROM pg_settings
  WHERE name IN ('shared_preload_libraries','idle_in_transaction_session_timeout',
                 'maintenance_work_mem','effective_cache_size')
  ORDER BY name;
"
"${PSQL[@]}" -d "$ALBION_DB" -Atc "
  SELECT 'pg_stat_statements installed: ' || extversion
  FROM pg_extension WHERE extname = 'pg_stat_statements';
"

echo
echo "Готово."
