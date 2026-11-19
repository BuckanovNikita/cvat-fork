# CVAT fork

Форк — полный исходный код CVAT (`cvat-ai/cvat`), соединённый с историей upstream
одним merge-коммитом: корень репозитория совпадает с корнем upstream, изменения
форка — обычные коммиты поверх, новый релиз забирается через `git merge <тег>`.
Форк добавляет отображение прогресса задач по стадиям и состояниям, расширенные
права участников организации на issues и комментарии и страницу Team Analytics,
которая работает внутри бэкенда CVAT (`cvat/apps/team_analytics/`).

## Сборка образов

Форк поставляется двумя собственными образами, каждый собирается своим скриптом,
и ни один Dockerfile форка не начинается с образа `cvat/`. Образ UI
(`build-ui.sh`) собирается по `Dockerfile.ui` upstream. Образ сервера форка
собирается с нуля из дерева форка по `Dockerfile.server` — переносу
`Dockerfile` upstream на Debian 12 с Python 3.12 из официального образа Python
([ADR 0007](docs/adr/0007-the-fork-builds-its-images-from-public-bases-the-server-on-debian-12.md));
сам `Dockerfile` upstream форк не меняет и не использует.

Сборка по умолчанию — без переменных: скрипты берут публичные базовые образы,
публичные индексы пакетов и github.com.

```bash
IMAGE=cvat/server:v2.82.0-fork MAKE_JOBS=5 ./build-server.sh
IMAGE=cvat/ui:v2.82.0-fork ./build-ui.sh
```

Всё, что нужно сети контура, — аргумент Dockerfile с публичным значением по
умолчанию; те же имена скрипты читают из окружения и передают в сборку только
заданные переменные ([ADR 0008](docs/adr/0008-the-fork-is-the-original-for-two-repositories.md)).

| Параметр | Что задаёт | По умолчанию |
| --- | --- | --- |
| `BASE_IMAGE` | база, на которой собирается образ сервера | `python:3.12-slim-bookworm` |
| `RUST_IMAGE` | образ с Rust для колеса Datumaro | `rust:1.85-slim-bookworm` |
| `GOLANG_IMAGE` | образ Go для smokescreen | `golang:1.27.2` |
| `APT_REMOTE` | зеркало apt для Debian | пусто — источники базового образа |
| `APT_SECURITY_REMOTE` | зеркало security-раздела apt | пусто — `APT_REMOTE` |
| `PIP_INDEX` | индекс Python-пакетов | пусто — PyPI |
| `GO_PROXY` | прокси Go-модулей | пусто — `proxy.golang.org` |
| `CARGO_INDEX` | индекс crates.io | пусто — crates.io |
| `GITHUB_PROXY` | зеркало github.com для архивов исходников | пусто — github.com |
| `NODE_IMAGE` | база стадии сборки UI | `node:24.19.0-slim` |
| `NGINX_IMAGE` | база стадии раздачи UI | `nginxinc/nginx-unprivileged:1.31.7-alpine3.24-slim` |
| `NPM_REGISTRY` | реестр npm, yarn и corepack | пусто — реестр каждого инструмента |

Пустое значение параметра ничего не настраивает: сборка оставляет настройку
базового образа для apt, pip, go, cargo и npm или публичный адрес инструмента по
умолчанию, поэтому в файлах форка не бывает адресов контура.

Базовые образы не требуется закреплять по digest: у `BASE_IMAGE`, `RUST_IMAGE`,
`GOLANG_IMAGE` и `NODE_IMAGE` ссылка может быть и тегом, и тегом с digest —
сборка принимает любую. `build-server.sh` перед сборкой стягивает три базы и
пишет в лог digest, в который разрешилась каждая ссылка, — при стягивании и ещё
раз в итоговой строке; `build-ui.sh` печатает базу, на которой собран образ.
Сборке нужна сеть: она стягивает базы и компилирует FFmpeg, поэтому идёт долго;
`MAKE_JOBS` задаёт число параллельных задач компиляции. Образ получает тег,
только если прошли шесть проверок (BUILD-1). Для переноса в контур без сети —
`SAVE=1`, архив образа. Запросы Team Analytics к ClickHouse выполняет отдельный
воркер (`run worker team_analytics`) — Deployment Helm-чарта на том же образе
сервера; сам API-сервер отвечает из кэша. Проверки вживую выполняются на
тестовом стенде в Kubernetes.

## Развёртывание

Чарты форка лежат в самом репозитории: `helm-chart/` разворачивает CVAT,
`helm-chart-nuclio/` — nuclio, отдельным релизом
([ADR 0008](docs/adr/0008-the-fork-is-the-original-for-two-repositories.md)).
Зависимости `helm-chart/` лежат тарболлами в `helm-chart/charts/` и зафиксированы
в `helm-chart/Chart.lock`, поэтому `helm template` и `helm install` не
обращаются к helm-репозиториям и работают без сети; у `helm-chart-nuclio/`
зависимостей нет.

```bash
helm install cvat ./helm-chart --values <файл значений>
helm install nuclio ./helm-chart-nuclio --values <файл значений>
```

Образы, реестры и адрес панели nuclio задаются значениями
`helm-chart-nuclio/values.yaml`; адреса и учётные данные контура в чарты не
входят и приходят своим файлом значений при установке.

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
  (Team Analytics внутри бэкенда),
  [ADR 0007](docs/adr/0007-the-fork-builds-its-images-from-public-bases-the-server-on-debian-12.md)
  (образы из базовых образов, публичных по умолчанию, сервер на Debian 12) и
  [ADR 0008](docs/adr/0008-the-fork-is-the-original-for-two-repositories.md)
  (форк — оригинал для двух репозиториев: два чарта и параметры сборки).

`README.md` в корне — файл upstream, и форк его не меняет: любой релиз, который
его трогает, давал бы конфликт при слиянии. Поэтому текст форка лежит здесь, в
`README.fork.md`; это оговорённое исключение из правила, что README пишется
по-русски (ADR 0005).

[INFRA_MIGRATION.md](INFRA_MIGRATION.md) описывает миграцию инфраструктуры проверки
на Kubernetes и её итог: Compose-файлы и скрипты удалены, проверки перенесены на
тестовый стенд.
