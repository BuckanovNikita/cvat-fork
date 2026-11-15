# CVAT fork

Форк — полный исходный код CVAT (`cvat-ai/cvat`), соединённый с историей upstream
одним merge-коммитом: корень репозитория совпадает с корнем upstream, изменения
форка — обычные коммиты поверх, новый релиз забирается через `git merge <тег>`.
Форк добавляет отображение прогресса задач по стадиям и состояниям, расширенные
права участников организации на issues и комментарии и страницу Team Analytics,
которая работает внутри бэкенда CVAT (`cvat/apps/team_analytics/`).

Форк поставляется двумя собственными образами, каждый собирается своим скриптом,
и ни один Dockerfile форка не начинается с образа `cvat/`. Образ UI
(`build-ui.sh`) собирается по `Dockerfile.ui` upstream. Образ сервера форка
собирается с нуля из дерева форка по `Dockerfile.server` — переносу
`Dockerfile` upstream на Debian 12 с Python 3.12 из официального образа Python
([ADR 0007](docs/adr/0007-the-fork-builds-its-images-from-public-bases-the-server-on-debian-12.md));
сам `Dockerfile` upstream форк не меняет и не использует:

```bash
IMAGE=cvat/server:v2.82.0-fork MAKE_JOBS=5 ./build-server.sh
```

Сборке нужна сеть: она скачивает закреплённые по digest базовые образы и пакеты
Python и компилирует FFmpeg, поэтому идёт долго; `MAKE_JOBS` задаёт число
параллельных задач компиляции. Стоковый образ сервера больше не нужен,
переменной `BASE_IMAGE` у скрипта нет. Образ получает тег, только если прошли
шесть проверок (BUILD-1). Для переноса в контур без сети — `SAVE=1`, архив
образа. Запросы Team Analytics к ClickHouse выполняет отдельный воркер
(`run worker team_analytics`) — Deployment Helm-чарта на том же образе сервера;
сам API-сервер отвечает из кэша. Проверки вживую выполняются на тестовом стенде
в Kubernetes.

Team Analytics — страница, её API и её настройки — доступна только
администраторам: с выбранной организацией администратор видит её цифры, без
неё — цифры всего экземпляра. Владельцы и мейнтейнеры организаций, как и все
остальные, получают 403. Список технических учётных записей (Technical
accounts list) один на экземпляр; его ведут администраторы в окне «Team
Analytics settings» на странице. Переменная окружения
`TEAM_ANALYTICS_TECHNICAL_ACCOUNTS` больше не задаёт список: если она осталась,
при запуске выводится одно предупреждение, что она не действует. После обновления
список пуст, и администратор заполняет его заново
([шаг обновления](docs/upstream-upgrade.md#an-instance-on-a-fork-version-that-read-team_analytics_technical_accounts)).

Перед обновлением CVAT используйте:

- [Спецификацию изменений форка](docs/fork-specification.md): поведение, которое
  нужно сохранить, полный список изменённых файлов upstream, точки интеграции и
  сценарии приёмки.
- [Порядок обновления upstream](docs/upstream-upgrade.md): получение тега
  релиза, слияние, перенос изменений `Dockerfile` upstream в
  `Dockerfile.server`, сборка образов и проверка результата.
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
  (полный форк), [ADR 0006](docs/adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)
  (Team Analytics внутри бэкенда) и
  [ADR 0007](docs/adr/0007-the-fork-builds-its-images-from-public-bases-the-server-on-debian-12.md)
  (образы из публичных базовых образов, сервер на Debian 12).

`README.md` в корне — файл upstream, и форк его не меняет: любой релиз, который
его трогает, давал бы конфликт при слиянии. Поэтому текст форка лежит здесь, в
`README.fork.md`; это оговорённое исключение из правила, что README пишется
по-русски (ADR 0005).

[INFRA_MIGRATION.md](INFRA_MIGRATION.md) описывает миграцию инфраструктуры проверки
на Kubernetes и её итог: Compose-файлы и скрипты удалены, проверки перенесены на
тестовый стенд.
