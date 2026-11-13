# Сервис Team Analytics в Kubernetes

Манифесты добавляют сервис Team Analytics к установке CVAT v2.82.0 из upstream Helm-чарта
(ADR 0003). Ставятся в пространство имён релиза чарта:

```bash
./build-team-analytics-service.sh            # образ cvat/team-analytics:v2.82.0 (IMAGE= меняет тег)
kubectl apply -k team-analytics/k8s -n <пространство имён релиза>
```

| Файл | Что это |
|---|---|
| `config.yaml` | ConfigMap `team-analytics`: адрес CVAT, технические учётные записи, интервал обновления |
| `deployment.yaml` | Deployment `team-analytics`: образ сервиса, переменные из ConfigMap и из Secret чарта |
| `service.yaml` | Service `team-analytics`, порт 8000 |
| `ingress.yaml` | Маршрут `/team-analytics-api` на сервис рядом с Ingress чарта; хост и класс должны совпадать с `ingress.hostname` и `ingress.className` чарта |

Образ не публикуется в реестр: на узле он должен быть локальным (`imagePullPolicy:
IfNotPresent`), для закрытого контура — `SAVE=1 ./build-team-analytics-service.sh` и
`docker load`.

## Переменные окружения

ClickHouse: `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_DB` (база с таблицей `events`),
`CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`. Берутся из Secret чарта `cvat-analytics-secret` —
той же учётной записью пользуется CVAT. Пользователю нужно право `CREATE DATABASE` для
базы итогов.

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `TEAM_ANALYTICS_CVAT_URL` | `http://localhost:8080` (в `config.yaml`: `http://cvat-backend-service:8080`) | бэкенд CVAT, у которого сервис проверяет пользователя и его роль |
| `TEAM_ANALYTICS_CVAT_TIMEOUT_S` | `5` | таймаут запроса к CVAT, секунды |
| `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS` | пусто | имена пользователей CVAT через запятую: технические учётные записи |
| `TEAM_ANALYTICS_REFRESH_INTERVAL_S` | `600` | интервал обновления сохранённых итогов, секунды |
| `TEAM_ANALYTICS_REFRESH_WINDOW_HOURS` | `48` | сколько последних часов пересчитывает каждое обновление |
| `TEAM_ANALYTICS_LOOKBACK_S` | `300` | сколько секунд до окна читается для расчётов |
| `TEAM_ANALYTICS_DB` | `team_analytics` | база итогов (создаётся сервисом при старте) |
| `TEAM_ANALYTICS_LISTEN_HOST`, `TEAM_ANALYTICS_LISTEN_PORT` | `0.0.0.0`, `8000` | адрес HTTP-сервера в поде |

Имя Service бэкенда зависит от имени релиза (`<релиз>-backend-service`); для релиза не
`cvat` поменяйте `TEAM_ANALYTICS_CVAT_URL`.
