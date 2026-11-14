# CVAT fork

Форк хранит отфильтрованные исходники CVAT в `cvat/`, изменения отображения
прогресса задач, расширенные права участников организации на issues и комментарии и
страницу Team Analytics с отдельным сервисом (`team-analytics/`).
Форк поставляется тремя образами, каждый собирается своим скриптом: образ UI
(`build-ui.sh`), образ сервера форка — стоковый сервер того же релиза, в котором
заменены только две политики, исправленные прямо в импорте (`build-server.sh`,
ADR 0004), и образ сервиса Team Analytics (`build-team-analytics-service.sh`).
Проверки вживую выполняются на тестовом стенде в Kubernetes.

Перед обновлением CVAT используйте:

- [Спецификацию изменений форка](docs/fork-specification.md): поведение, которое
  нужно сохранить, точки интеграции и сценарии приёмки.
- [Порядок обновления upstream](docs/upstream-upgrade.md): сравнение с исходным
  релизом, обновление subtree вместе с политиками, пересборка образа сервера и
  проверка результата.
- [Базовый снимок от 2026-11-13](docs/evidence/2026-11-13-fork-baseline.md):
  ревизии, полный список отличий внутри subtree и границы проверки.
- [Права на issues и комментарии](docs/fork-specification.md#iam-1-organization-issue-and-comment-permissions)
  и [сборка и доставка политик](docs/fork-specification.md#build-1-packaging-and-policy-delivery):
  что меняет патч, как политики попадают на сервер и как это проверяется.

Team Analytics:

- [Раздел TA-1 спецификации форка](docs/fork-specification.md#ta-1-team-analytics):
  поведение, карта затронутых файлов upstream и сценарии приёмки.
- [Проверки Team Analytics при обновлении](docs/upstream-upgrade.md#team-analytics):
  три набора тестов и полный прогон на тестовом стенде.
- [Тестовый стенд](verify/team-analytics-stack/README.md) и
  [манифесты сервиса](team-analytics/k8s/README.md).
- [Итоговый прогон от 2026-11-14](docs/evidence/2026-11-14-team-analytics-final-run.md).

[INFRA_MIGRATION.md](INFRA_MIGRATION.md) описывает миграцию инфраструктуры проверки
на Kubernetes и её итог: Compose-файлы и скрипты удалены, проверки перенесены на
тестовый стенд.
