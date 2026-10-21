# Роли

Планируемые роли:

- `common` — базовые пакеты, пользователи, SSH, sysctl, time sync.
- `bird` — BIRD, OSPF/BGP, route policy, validation, reload.
- `prefixes` — сбор внешних префиксов из RIPE Stat в нормализованный список.
- `sshtun` — SSH-туннели и systemd-шаблон.
- `unbound` — DNS, DoT через туннель, fail-closed.
- `keepalived` — VRRP, VIP, health-check.
- `nftables` — firewall и NAT на exit-узлах.
- `monitoring` — exporters и scrape-конфиги.
- `exclude` — персистентная таблица прямых исключений.

Роли должны быть идемпотентными, использовать шаблоны с `validate` и не содержать реальных адресов или секретов.
