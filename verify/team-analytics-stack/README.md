# Тестовый стенд Team Analytics

Одноразовый CVAT v2.82.0 с аналитикой в собственном пространстве имён локального
кластера `docker-desktop`. Поднимается и удаляется одной командой; на нём проверяются
все тикеты Team Analytics (ADR 0003).

```bash
verify/team-analytics-stack/run.sh up      # поднять, загрузить учётные записи, проверить событие
verify/team-analytics-stack/run.sh down    # удалить всё созданное (успешно и когда ничего нет)
verify/team-analytics-stack/run.sh cycle   # up, затем down (и когда up упал)
```

Остальные подкоманды (`seed`, `check-event`, `forward`, `status`, `fetch-chart`) описаны в
шапке `run.sh`. Ручных шагов нет.

## Что нужно от машины

- Docker Desktop с включённым Kubernetes (контекст `docker-desktop`), `kubectl`, `helm` 3,
  `curl`, `python3`, `ss`, `setsid`.
- Доступ в сеть при первом запуске: архив исходников upstream (codeload.github.com),
  репозитории чартов зависимостей (charts.bitnami.com, helm.vector.dev,
  grafana.github.io, nuclio.github.io, helm.traefik.io), Docker Hub для одобренных
  образов. Grafana при каждом старте скачивает плагин ClickHouse; проверки от Grafana не
  зависят.
- Образы, которые `run.sh` скачивает сам, по одному и с `nice` (одобрены владельцем,
  список в `stack.env`, `TA_APPROVED_PULLS`): `cvat/server:v2.82.0`,
  `apache/kvrocks:2.15.0`, `cvat/clickhouse:23.12.2-debian-11-r0`,
  `cvat/postgresql:15.2.0-debian-11-r0`, `redis:7.2.11`, `grafana/grafana:10.1.5`,
  `busybox:1.36.1`.
- Образы, которые должны уже быть локально (никогда не скачиваются):
  `openpolicyagent/opa:1.12.2`, `timberio/vector:0.26.0-alpine`, прокси
  `nginx:1.27-alpine` (`TA_PROXY_IMAGE`), образ UI (`TA_UI_IMAGE`, собирается
  `./build-ui.sh`) и образ сервиса (`TA_SERVICE_IMAGE`, собирается
  `./build-team-analytics-service.sh`). Любой другой образ в рендере чарта — отказ установки.
- Для проверки страницы — headless Chrome (`TA_BROWSER_BIN`, по умолчанию `google-chrome`)
  и Node.js 22 или новее.
- Свободный порт хоста 8490 (`TA_HOST_PORT`), зарезервированный за стендом в таблице
  портов k8s-infra. Занятый порт — отказ, чужой процесс не трогается.

## Что создаётся

- Пространство имён `cvat-ta-it-<TA_RUN_ID>` (по умолчанию `<TA_RUN_ID>` = `$USER`) с
  меткой `app.kubernetes.io/managed-by=cvat-fork-team-analytics-stack`, `ResourceQuota` и
  `LimitRange` (`namespace.yaml`). Пропавшее пространство создаётся заново; старше
  `TA_MAX_REUSE_HOURS` (36 ч) — пересоздаётся, потому что чистильщик кластера удаляет
  пространства через 48 ч. Чужое пространство с тем же именем не трогается.
- Релиз чарта CVAT из upstream-коммита `02bd74f…` (`stack.env`) со значениями
  `values.yaml`: аналитика включена, из воркеров только utils и webhooks. Чарт лежит в
  кэше `${XDG_CACHE_HOME:-~/.cache}/cvat-fork/team-analytics/`, вне импорта `cvat/`;
  версии зависимостей закреплены `Chart.lock` и `chart-deps.sha256` (дата и источник —
  `docs/evidence/2026-11-13-team-analytics-test-stack.md`).
- Обратный прокси `ta-proxy` (`proxy.yaml`): `/api`, `/admin`, `/static`, `/django-rq`,
  `/profiler` — бэкенд CVAT; `/analytics` — Grafana за проверкой доступа CVAT;
  `/team-analytics-api` — сервис Team Analytics; всё остальное — UI. Адрес:
  `http://localhost:8490` через `kubectl port-forward`.
- Сервис Team Analytics из манифестов `team-analytics/k8s/` (кроме Ingress — маршрут здесь
  даёт прокси) с образом `TA_SERVICE_IMAGE` и обновлением раз в `TA_REFRESH_INTERVAL_S`
  (60 с).
- Учётные записи (`accounts.json`, пароль `TA_SEED_PASSWORD`): администратор `ta-admin`;
  организация `ta-org-a` с владельцем `ta-owner`, `ta-maintainer`, `ta-supervisor`,
  `ta-worker`; `ta-outsider` не состоит нигде; организация `ta-org-b` с владельцем
  `ta-owner-b` и `ta-maintainer-b`. После загрузки каждая роль читается обратно через API.
- Проверка события: `ta-worker` отправляет клиентское событие через `POST /api/events`, и
  стенд ждёт его в таблице `events` ClickHouse вместе с новым полем payload.
- Проверка рабочего времени (`run.sh check-tracer`, часть `up`): владельцы организаций
  создают через API проект `ta-tracer` с задачей и заданиями, исполнители отправляют
  события в своих заданиях (`ta-worker` 90 мин и `ta-supervisor` 30 мин в `ta-org-a`,
  `ta-maintainer-b` 60 мин в `ta-org-b`; `stack_api.py`, `WORK`). Обновление никто не
  запускает: стенд ждёт, пока его выполнит расписание сервиса, сверяет цифры и отказы для
  каждой роли, затем `browser_check.cjs` в headless Chrome входит как `ta-maintainer`
  (ссылка в шапке, цифры на странице) и как `ta-worker` (ссылки нет, прямой переход —
  «not available», запрос к сервису — 403). `TA_SCREENSHOT_DIR` сохраняет снимки экрана.

Ничего кластерного не создаётся (рендер проверяется на каждом запуске), хранилище —
класс по умолчанию. `down` удаляет пространство имён целиком, включая тома, которые чарт
помечает к сохранению, и останавливает только свой `port-forward` (PID и время старта).
