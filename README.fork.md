# CVAT fork

Форк — полный исходный код CVAT (`cvat-ai/cvat`), соединённый с историей upstream
одним merge-коммитом: корень репозитория совпадает с корнем upstream, изменения
форка — обычные коммиты поверх, новый релиз забирается через `git merge <тег>`.
Форк добавляет отображение прогресса задач по стадиям и состояниям, расширенные
права участников организации на issues и комментарии и страницу Team Analytics,
которая работает внутри бэкенда CVAT (`cvat/apps/team_analytics/`).

Форк поставляется двумя собственными образами, каждый собирается своим скриптом:
образ UI (`build-ui.sh`) и образ сервера форка (`build-server.sh`) — стоковый
сервер того же релиза, поверх которого скопированы изменённые и добавленные
форком файлы из `cvat/` и `backend_entrypoint.d/` (исправленные политики,
приложение Team Analytics и его подключение). Запросы Team Analytics к
ClickHouse выполняет отдельный воркер (`run worker team_analytics`) — Deployment
Helm-чарта на том же образе сервера; сам API-сервер отвечает из кэша. Проверки
вживую выполняются на тестовом стенде в Kubernetes.

Перед обновлением CVAT используйте:

- [Спецификацию изменений форка](docs/fork-specification.md): поведение, которое
  нужно сохранить, полный список изменённых файлов upstream, точки интеграции и
  сценарии приёмки.
- [Порядок обновления upstream](docs/upstream-upgrade.md): получение тега
  релиза, слияние, пересборка образа сервера и проверка результата.
- [Базовый снимок от 2026-11-13](docs/evidence/2026-11-13-fork-baseline.md):
  исходные ревизии и границы проверки на момент снимка.
- [Права на issues и комментарии](docs/fork-specification.md#iam-1-organization-issue-and-comment-permissions)
  и [сборка и доставка политик](docs/fork-specification.md#build-1-packaging-and-policy-delivery):
  что меняет патч, как политики попадают на сервер и как это проверяется.

Team Analytics:

- [Раздел TA-1 спецификации форка](docs/fork-specification.md#ta-1-team-analytics):
  поведение, доступ, настройки, карта затронутых файлов upstream и сценарии
  приёмки.
- [Проверки Team Analytics при обновлении](docs/upstream-upgrade.md#team-analytics):
  тесты расчётов, два набора тестов фронтенда и полный прогон на тестовом стенде.
- [Тестовый стенд](verify/team-analytics-stack/README.md).
- [Итоговый прогон от 2026-11-14](docs/evidence/2026-11-14-team-analytics-final-run.md)
  (ещё на отдельном сервисе) и
  [переход на полный форк от 2026-11-15](docs/evidence/2026-11-15-full-fork-conversion.md).
- Решения: [ADR 0005](docs/adr/0005-a-full-source-fork-joined-to-upstream-history.md)
  (полный форк) и [ADR 0006](docs/adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)
  (Team Analytics внутри бэкенда).

`README.md` в корне — файл upstream, и форк его не меняет: любой релиз, который
его трогает, давал бы конфликт при слиянии. Поэтому текст форка лежит здесь, в
`README.fork.md`; это оговорённое исключение из правила, что README пишется
по-русски (ADR 0005).

[INFRA_MIGRATION.md](INFRA_MIGRATION.md) описывает миграцию инфраструктуры проверки
на Kubernetes и её итог: Compose-файлы и скрипты удалены, проверки перенесены на
тестовый стенд.
