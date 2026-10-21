# bird

Управляет BIRD 2.x: пакетом, конфигом, фрагментами `conf.d`, проверкой
синтаксиса и reload через `birdc configure`.

Все адреса и топология задаются в inventory. Реальных адресов в роли нет.

## Переменные

Обязательные:

- `bird_router_id` — стабильный router-id, обычно loopback.
- `bird_ospf.interfaces` — явный список OSPF-интерфейсов.
- `bird_ospf.area` — area, по умолчанию `0.0.0.100`.

Основные:

- `bird_install`, `bird_manage_config`,
  `bird_manage_service`, `bird_validate`;
- `bird_tables` — дополнительные `ipv4 table`;
- `bird_filters` — словарь `name: body` для `filter`;
- `bird_direct`, `bird_kernel`, `bird_pipes`,
  `bird_static`;
- `bird_netlink_rmem_max` — поднять `net.core.rmem_max` для kernel-протокола;
  в `bird_kernel` можно задать `netlink_rx_buffer` (байты, BIRD >= 2.14);
- `bird_ospf` — OSPF underlay;
- `bird_ospf_retransmit` — RxmtInterval по умолчанию, `10`;
- `bird_bgp` — необязательный BGP;
- `bird_fragments` — список `{name, src|content}` для `conf.d`;
- `bird_extra_config` — сырой BIRD-конфиг для переходного периода.

## Пример inventory

```yaml
bird_router_id: 10.255.0.10

bird_filters:
  kernel_reject_local: |
    if (source = RTS_DEVICE) then { reject; }
    accept;

bird_direct:
  - table: master4
    interfaces:
      - enp0s25

bird_kernel:
  - table: master4
    import: filter kernel_reject_local
    export: filter kernel_reject_local

bird_ospf:
  enabled: true
  table: master4
  import: all
  export: all
  area: 0.0.0.100
  interfaces:
    - name: tun10
      cost: 100
      hello: 1
      retransmit: 10
      dead: 4
      priority: 10
      type: ptp
      neighbors:
        - 10.1.1.1
        - 10.1.1.5
```

Для exit-узла с внешними префиксами статические маршруты задаются строками.
Имя protocol static не должно совпадать с именем таблицы:

```yaml
bird_static:
  - name: blacklist_static
    table: blacklist
    import: all
    export: none
    routes:
      - 203.0.113.0/24 blackhole
```

Большие списки префиксов лучше генерировать в `bird_fragments`
через отдельный pipeline, а не держать в inventory.

## Теги

- `bird:adapter` — чтение `prefixes.txt` и установка `bird_blackhole_prefixes`;
- `bird:config` — main config: render, validate, install;
- `bird:fragments` — фрагменты `conf.d`; на origin также запускает adapter;
- `bird:sysctl` — `net.core.rmem_max` для kernel-протокола;
- `bird:service` — enable/start, reload через handler;
- `bird` — всё.

Примеры:

```bash
make bird-config LIMIT=vpn
make bird-fragments LIMIT=vpn
make bird-netlink LIMIT=t400
```

`bird:config` не читает `prefixes.txt` и не перекладывает фрагменты; для смены
только OSPF/BGP-настроек этого достаточно.

## Проверка

```bash
cd ansible
../.venv/bin/ansible-playbook playbooks/bird.yml --syntax-check
../.venv/bin/ansible-playbook playbooks/bird.yml --check --diff
```

Запись конфига выполняется только после `bird -p -c <staging>`. При ошибке
боевой конфиг не перезаписывается.
