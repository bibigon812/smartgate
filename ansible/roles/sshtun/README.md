# sshtun

Управляет L3-туннелями `tunN` поверх SSH (`ssh -w N:N`) через один
systemd-шаблон юнита `sshtun@.service` (инстансы `sshtun@tun10.service`,
`sshtun@tun11.service`, ...).

Что делает роль:

- ставит `openssh-client`;
- генерирует per-tunnel ключи поверх ed25519 (idempotent);
- раскладывает wrapper `/usr/local/bin/sshtun-connect` и env-файлы
  `/etc/smartgate/sshtun/tunN.env` (mode 0600);
- рендерит и валидирует юнит `sshtun@.service` через `systemd-analyze verify`;
- запускает/останавливает туннели по явному списку и удаляет протухшие
  инстансы (`sshtun:purge`).

Поведение туннеля соответствует ARCHITECTURE.md §6.4:

- адреса через `ip addr replace`, а не `add`;
- экспоненциальный backoff между попытками;
- проверка состояния интерфейса через `ip link`, а не ping раз в секунду;
- один SSH на туннель, адрес на выходе назначается в этой же сессии
  (`manage_remote`, требует `ssh_user: root`);

Все адреса и хосты задаются в inventory, в роли реальных адресов нет.

## Переменные

Ключевые глобальные:

- `sshtun_tunnels` — явный список туннелей, обязательный;
- `sshtun_enabled`, `sshtun_install`, `sshtun_manage_config`,
  `sshtun_manage_service`, `sshtun_manage_keys`, `sshtun_validate`,
  `sshtun_purge`;
- `sshtun_ssh_options` — базовые опции ssh-клиента;
- `sshtun_mtu` — MTU по умолчанию для туннелей; через SSH `-w` есть
  накладные расходы, поэтому дефолт — `1400`, а не 1500. MSS clamp
  на туннелях — задача роли `nftables`.
- `sshtun_dev_wait` — сколько секунд ждать появления `tunN`;
- `sshtun_check_interval`, `sshtun_check_down_threshold` — как часто
  проверяется `ip link` и сколько неудачных проверок подряд считаются
  смертью туннеля;
- `sshtun_backoff_base`, `sshtun_backoff_max` — base/max экспоненциального
  backoff между попытками.

Поля туннеля:

| поле | обязательное | значение по умолчанию |
|---|---|---|
| `name` | да | `tunN` |
| `exit_host` | да | — |
| `local_addr` | да | адрес этого конца `tunN` с префиксом |
| `remote_addr` | да | адрес выхода с префиксом |
| `tun` | нет | из `name` (`tun10` → `10`; индексы должны быть уникальны) |
| `exit_port` | нет | `22` |
| `ssh_user` | нет | `root` |
| `manage_remote` | нет | `true`, требует `ssh_user: root` |
| `ssh_key` | нет | `/etc/smartgate/sshtun/keys/<name>` |
| `seed_known_hosts` | нет | `false` (вместе с `sshtun_manage_known_hosts`) |
| `ssh_options` | нет | `sshtun_ssh_options` |
| `mtu` | нет | `sshtun_mtu` |
| `enabled` | нет | `true` |
| `state` | нет | `started` |

## Пример inventory (group_vars для edges)

```yaml
sshtun_tunnels:
  - name: tun10
    exit_host: vpn.example.com
    local_addr: 10.11.10.2/30
    remote_addr: 10.11.10.1/30

  - name: tun11
    exit_host: vpn.example.com
    local_addr: 10.11.11.2/30
    remote_addr: 10.11.11.1/30

  - name: tun30
    exit_host: ru1.example.com
    local_addr: 10.30.0.2/30
    remote_addr: 10.30.0.1/30
    seed_known_hosts: true
```

`ip_forward`, `accept_redirects`, `rp_filter` и прочие sysctl относятся к
роли `common`; протоколы поверх туннелей — к роли `bird`.

## Теги

- `sshtun:check` — assert по списку туннелей;
- `sshtun:install` — пакеты и ключи;
- `sshtun:keys` — ключи;
- `sshtun:known_hosts` — ssh-keyscan выходов;
- `sshtun:script` — wrapper `sshtun-connect`;
- `sshtun:unit` — systemd template;
- `sshtun:config` — env-файлы и reload;
- `sshtun:service` — enable/start;
- `sshtun:purge` — удаление инстансов, не попавших в `sshtun_tunnels`;
- `sshtun` — всё.

Примеры:

```bash
make tunnels LIMIT=edge-a
make tunnels-config LIMIT=edge-a
make tunnels-purge LIMIT=edge-a
```

Удаление из `sshtun_tunnels` и `apply` убирает юнит и env-файл туннеля
(`sshtun_purge: true` по умолчанию). `sshtun_purge: false` оставляет
нежелательные инстансы, если туннели управляются не только этой ролью.

Важно: purge не выполняется, если на хосте `sshtun_tunnels` пустой —
так забытый список не останавливает существующие туннели. Хосты без
клиентских туннелей (например, exits) оставляют список пустым.

Список задается на уровне каждого edge (host vars или group_vars группы
`edges`). Playbook цель `all:!origins` — origin-узлы не обрабатываются
(там только server-side туннелей, у них роль пропускается полностью;
exit-узлы, инициирующие туннели, например ru1 -> vpn, входят через
`sshtun_tunnels` в своих host_vars).

## Проверка

```bash
cd ansible
../.venv/bin/ansible-playbook playbooks/tunnels.yml --syntax-check
../.venv/bin/ansible-playbook playbooks/tunnels.yml --check --diff
```

Поведение в check mode: ничего не запускается, ключи не генерируются,
purge не встаёт в play.

## Отладка

```bash
journalctl -u sshtun@tun10 -f
systemctl status sshtun@tun10
ip link show tun10
cat /etc/smartgate/sshtun/tun10.env
```
