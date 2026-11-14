# Тестовый стенд Team Analytics

Одноразовый CVAT v2.82.0 с аналитикой в собственном пространстве имён локального
кластера `docker-desktop`. Поднимается и удаляется одной командой; на нём проверяются
все тикеты Team Analytics (ADR 0003).

```bash
IMAGE=cvat/server:v2.82.0-fork-policies ./build-server.sh                # образы из текущей версии
IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh
IMAGE=cvat/team-analytics:v2.82.0 ./build-team-analytics-service.sh
verify/team-analytics-stack/run.sh up      # поднять, загрузить данные, выполнить проверки
verify/team-analytics-stack/run.sh down    # удалить всё созданное (успешно и когда ничего нет)
verify/team-analytics-stack/run.sh cycle   # up, затем down (и когда up упал)
```

Это теги по умолчанию (`TA_SERVER_IMAGE`, `TA_UI_IMAGE`, `TA_SERVICE_IMAGE` в `stack.env`);
образы должны быть собраны из проверяемой версии, иначе проверки политик и страницы не
пройдут. Остальные подкоманды (`seed`, `check-event`, `check-tracer`, `check-task-progress`, `check-final`,
`check-policies`, `check-issues`, `check-issue-policies`, `forward`, `status`, `preflight`, `build-chart`, `render`, `check-render`,
`check-bundle`, `render-ingress`, `check-ingress`, `seed-access`, `check-access`,
`check-ingress-gone`) описаны в шапке `run.sh`; `preflight` выполняет всё, что `up` делает до
первого изменения в кластере, и ничего не создаёт и не скачивает. Ручных шагов нет.

## Что нужно от машины

- Docker Desktop с включённым Kubernetes (контекст `docker-desktop`), `kubectl`, `helm` 3,
  `curl`, `python3`, `ss`, `setsid`.
- Доступ в сеть при первой сборке чарта и при каждом изменении чарта или `Chart.lock`:
  репозитории чартов зависимостей (charts.bitnami.com, helm.vector.dev,
  grafana.github.io, nuclio.github.io, helm.traefik.io); Docker Hub для одобренных
  образов. Grafana при каждом старте скачивает плагин ClickHouse; проверки от Grafana не
  зависят.
- Образы, которые `run.sh` скачивает сам, по одному и с `nice` (одобрены владельцем,
  список в `stack.env`, `TA_APPROVED_PULLS`): `apache/kvrocks:2.15.0`,
  `cvat/clickhouse:23.12.2-debian-11-r0`, `cvat/postgresql:15.2.0-debian-11-r0`,
  `redis:7.2.11`, `grafana/grafana:10.1.5`, `busybox:1.36.1`. Стоковый
  `cvat/server:v2.82.0` остаётся в списке одобренных, но стенд его не запускает: он нужен
  локально как основа образа сервера форка и образа сервиса (скрипты сборки его не
  скачивают) и для набора тестов сервиса. Рендер, в котором он есть, — отказ установки.
- Образы, которые должны уже быть локально (никогда не скачиваются): образ сервера форка
  (`TA_SERVER_IMAGE`, собирается `./build-server.sh`, ADR 0004; без него `up` и `preflight`
  останавливаются первым же шагом, до сборки чарта и до кластера),
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
- Релиз чарта CVAT из импорта (`cvat/helm-chart` и компонент `cvat/components/analytics`,
  на который ссылается его `analytics`) со значениями `values.yaml`: аналитика включена,
  из воркеров только utils и webhooks; сервер, все воркеры и инициализатор работают на
  образе сервера форка (`TA_SERVER_IMAGE`). Helm собирает зависимости в копии чарта в
  рабочем каталоге `${XDG_CACHE_HOME:-~/.cache}/cvat-fork/team-analytics/` (`TA_CACHE_DIR`;
  импорт не меняется), каталог сборки назван по хешу файлов чарта и `Chart.lock`.
  Версии зависимостей закреплены `Chart.lock` и `chart-deps.sha256` (дата и источник —
  `docs/evidence/2026-11-13-team-analytics-test-stack.md`); архив с другим хешем — отказ.
- Проверка политик (`run.sh check-policies`, часть `up` сразу после `port-forward`): стенд
  забирает бандл политик, который сервер отдаёт OPA (`/api/auth/rules`), и проверяет
  `issues.rego` и `comments.rego` каждый отдельно: файл должен совпадать с файлом импорта
  байт в байт (`verify/policy_bundle.sh check`) и содержать отметку патча
  `Local patch (role floor)`. Если хоть одна из двух политик стоковая — отказ.
- Обратный прокси `ta-proxy` (`proxy.yaml`): `/api`, `/admin`, `/static`, `/django-rq`,
  `/profiler` — бэкенд CVAT; `/analytics` — Grafana за проверкой доступа CVAT;
  `/team-analytics-api` — сервис Team Analytics; всё остальное — UI. Адрес:
  `http://localhost:8490` через `kubectl port-forward`.
- Сервис Team Analytics из манифестов `team-analytics/k8s/` с образом `TA_SERVICE_IMAGE` и
  обновлением раз в `TA_REFRESH_INTERVAL_S` (60 с). Адрес стенда по-прежнему даёт прокси.
- Ingress сервиса (`team-analytics/k8s/ingress.yaml`, `run.sh render-ingress`) рядом с
  прокси: класс кластера `TA_INGRESS_CLASS` (`nginx`, ingress-nginx из k8s-infra), хост
  `TA_INGRESS_HOST` (`<пространство имён>.k8s.docker.internal`, его покрывает сертификат
  платформы по умолчанию). Объект в пространстве имён стенда и удаляется вместе с ним. Имя
  на машине не разрешается: `run.sh check-ingress` (часть `up` после загрузки учётных
  записей) обращается к контроллеру на `127.0.0.1:443` под этим именем, с проверкой
  сертификата. Свой порт не нужен — 80 и 443 общие, по таблице портов k8s-infra. Запрос
  `status` с сессией `ta-maintainer` — 200, без сессии — 401 `not_authenticated`.
  `run.sh check-ingress-gone` после `down`: ни один Ingress не называет этот хост, контроллер
  отвечает 404.
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
- Проверка прогресса задач (`run.sh check-task-progress`, часть `up` после проверки рабочего
  времени; `task_progress.py`, `task_progress_browser.cjs`). Сначала стенд убеждается, что UI
  работает на образе `TA_UI_IMAGE`. Затем `ta-admin` в личном пространстве создаёт через API
  две новые задачи: в первой по одному заданию на каждую пару этапа и состояния (этапы и
  состояния сверяются со схемой API сервера), во второй одно задание annotation / new.
  Каждое задание читается обратно. Headless Chrome входит как `ta-admin` и открывает список
  задач с фильтром по этим задачам. На карточке каждой задачи проверяются подписи легенды
  со счётчиками, цвет, вес и подсказка каждого сегмента (таблица UI-2 в
  `docs/fork-specification.md`) и общее число заданий. Проверяется, что нет корзины
  «not available» и стоковых подписей. Текст легенды должен читаться на карточке
  (контраст не ниже 4.5:1).
- Итоговый прогон (`run.sh check-final`, последняя часть `up`; `final_run.py`,
  `final_browser.cjs`). Организация `ta-org-c` (`ta-owner-c`, `ta-worker-c` и
  техническая учётная запись `ta-bot`, `TA_TECHNICAL_ACCOUNTS`). На каждом запуске
  создаётся новый проект, и `ta-worker-c` в headless Chrome работает в его задании:
  рисует, перетаскивает, вставляет, размножает, меняет класс, удаляет, листает кадры и
  сохраняет. Каждая новая запись ищется в ClickHouse. Запись детектора отправляется
  через API (функции модели на стенде нет). `ta-bot` сохраняет рамки через API.
  Затем сверяются цифры сервиса и страницы. В `ta-org-v` (`ta-owner-v`) один раз
  загружаются синтетические события: 100 исполнителей, 40 проектов с длинными
  именами, десять недель истории. По ним сверяются цифры, тренды и длина страницы,
  проверяются фильтры, полный вид, сравнение и узкое окно. Затем каждая учётная запись
  обращается к каждому адресу сервиса. Наконец сервис останавливается, и стенд проверяет
  панель ошибки и то, что разметка рисуется и сохраняется; после этого сервис
  запускается снова.
- Матрица прав на issues и комментарии (`run.sh check-issues`, часть `up` после итогового
  прогона; `issue_matrix.py`). Свои учётные записи (`issue_accounts.json`, загружаются тем
  же `seed_users.py`): организация `ta-org-i` с `ta-owner-i`, `ta-maintainer-i`,
  `ta-supervisor-i`, `ta-worker-i`, `ta-worker-i2` (глобальная роль `worker`) и
  `ta-norole-i` без глобальной роли; `ta-outsider-i` не состоит нигде; организация
  `ta-org-j` с `ta-owner-j` и `ta-worker-j`. Глобальные роли выставляет `ta-admin` через
  `PATCH /api/users/<id>` и читает обратно. Задание без исполнителя с issue владельца и двумя
  комментариями, второе задание у `ta-norole-i`, задание в `ta-org-j`. Каждая строка матрицы
  выполняется через API, владелец читает результат обратно; стенд сам решает, прошла ли
  матрица, и пишет её в `issue-matrix.json` в каталоге состояния. Те же ожидания без
  сервера, против политик импорта или стокового тега: `run.sh check-issue-policies
  [patched|stock]` (локальный образ OPA, без сети).
- Случаи доступа (`run.sh check-access [CASE]`, последняя часть `up`; `access_cases.py`,
  учётные записи — `access_accounts.json`, загружает `seed_access.py`). Каждый случай сам
  решает, пройден ли он, и печатает `[access] PASS` или `[access] FAIL`.
  `removed-member`: `ta-leaver`, мейнтейнер `ta-org-r`, читает организацию, владелец
  `ta-owner-r` удаляет его через API CVAT, и после срока кэша ответов CVAT в сервисе
  (`ANSWER_TTL` в `access.py`, минута, не настраивается — случай ждёт его с запасом) тот же
  сеанс получает 403 `forbidden` с организацией и без неё; каждый запуск возвращает
  членство. `group-admin`: `ta-group-admin` в группе `admin` без флагов суперпользователя
  читает весь экземпляр (как `ta-admin`) и `ta-org-a` (как её владелец), `status` с полями
  администратора. `personal-workspace`: `ta-solo` (не состоит нигде) работает 20 мин в
  задании личного пространства (один раз на стенд); у администратора без организации строка
  с этим временем и проект есть, ни в одной организации их нет. `header-credentials`: для
  пяти пар учётная запись — организация `status` и `overview` с заголовком `Authorization`
  (`Basic` и персональный токен `Bearer`, удаляется после случая) дают те же решения, что
  cookie сеанса; неверный пароль и неизвестный токен — 401.

Ничего кластерного не создаётся (рендер проверяется на каждом запуске: кластерные объекты,
образы вне одобренного списка, принудительное скачивание и серверный образ, отличный от
образа форка, — отказ установки), хранилище —
класс по умолчанию. `down` удаляет пространство имён целиком, включая тома, которые чарт
помечает к сохранению, и останавливает только свой `port-forward` (PID и время старта).
