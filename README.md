# SmartGate

Self-hosted шлюз для split-routing домашнего и офисного трафика в условиях DPI-блокировок. Заблокированные направления идут через зарубежный exit, остальной трафик — напрямую через локального провайдера. Клиенты не настраиваются вручную: шлюз сам раздаёт маршруты, DNS и default gateway.

## Статус

Архитектура и deployment UX зафиксированы. CLI `smartgate`, installer и Ansible-роли ещё не реализованы.

Текущая production-схема использует BIRD и OSPF на голом железе. FRR, Docker, Shadowsocks, VRF и gRPC из старых заготовок в production не применяются. Перед использованием смотрите [ARCHITECTURE.md](ARCHITECTURE.md).

## Документация

- [ARCHITECTURE.md](ARCHITECTURE.md) — текущая и целевая архитектура, проблемы, миграция, ADR.
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — развёртывание с нуля, профили, cutover, recovery.
- [docs/MANAGEMENT.md](docs/MANAGEMENT.md) — Ansible как движок, CLI как продукт, спецификация команд.

## Целевой сценарий

```text
smartgate init       # мастер, smartgate.yaml, inventory, ключи
smartgate doctor     # preflight без изменений
smartgate plan       # ansible --check --diff
smartgate apply      # применить с бэкапом и dead-man switch
smartgate verify     # egress, DNS, split-routing, SSH
smartgate lan cutover
```

Golden path — `home-single`: один edge, один exit, one-arm, edge DHCP, DNS через туннель. HA через VRRP — отдельный профиль.

## Требования вкратце

- Exit VPS: Debian 12/13 или Ubuntu 22.04/24.04, public IPv4, root SSH, TUN.
- Edge: Debian 12/13 или Ubuntu 22.04/24.04, 1–2 NIC, всегда включён.
- Роутер: возможность выключить DHCP или задать gateway/DNS.
- Список префиксов: default, свой файл или URL.

Подробности — в [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Ограничения

- Один WAN/роутер и один exit — точки отказа.
- IPv6 в MVP выключен.
- SSH-туннели могут блокироваться DPI; обфускация не входит в MVP.
- Нет web UI и автоматического создания VPS.
- Проект не заменяет коммерческий сервис и не даёт SLA.

## Структура

```text
ARCHITECTURE.md
Makefile      # check, doctor, backup, plan
ansible/      # inventory, playbooks, роли
config/       # smartgate.example.yaml
docs/
  DEPLOYMENT.md
  MANAGEMENT.md
deploy/       # старые заготовки, требуют ревизии
gateway/      # старые заготовки, требуют ревизии
upstream/     # старые заготовки, требуют ревизии
```

Локальный `ansible/inventories/prod/hosts.yml` исключён через `.gitignore`; в репозитории хранится только `example/hosts.yml.example`. Реальные адреса и доступы в git не попадают.

Старые каталоги не отражают текущий production-стек и будут перенесены в `legacy/` или удалены после подтверждения.

## Локальная проверка

```bash
cp ansible/inventories/example/hosts.yml.example ansible/inventories/prod/hosts.yml
make check    # граф inventory
make backup   # read-only снимок конфигов в .work/backups/
make doctor   # read-only проверка TUN, BIRD и ОС
make plan     # ansible --check --diff
```

Нужен `ansible-core`. `make backup` ничего не меняет на хостах; `.work/` исключён из git.

## Лицензия

См. [LICENSE](LICENSE).
