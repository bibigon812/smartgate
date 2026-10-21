# Развёртывание SmartGate с нуля

- **Статус:** спецификация. CLI `smartgate`, installer и Ansible-роли ещё не реализованы.
- **Связанные документы:** [ARCHITECTURE.md](../ARCHITECTURE.md), [MANAGEMENT.md](MANAGEMENT.md).

Документ описывает целевой пользовательский сценарий: что нужно подготовить, какие команды выполнить и как безопасно переключить LAN на SmartGate.

## 1. Что получится

После установки:

- локальный edge-узел становится шлюзом для LAN;
- заблокированные направления идут через зарубежный exit;
- остальной трафик идёт напрямую через домашнего провайдера;
- DNS работает через туннель, а не через DNS провайдера;
- маршруты обновляются автоматически;
- есть `smartgate status`, `doctor`, `verify` и откат.

В MVP HA нет: один edge, один exit. VRRP и второй edge — отдельный профиль.

## 2. Профили

| Профиль | Узлы | LAN | DHCP | HA |
|---|---|---|---|---|
| `home-single` | 1 edge + 1 exit | one-arm | edge DHCP или router DHCP | нет |
| `home-ha` | 2 edge + 1–2 exit | one-arm | router DHCP или Kea HA | VRRP |
| `inline` | 1–2 edge + exit | edge между router и LAN | edge DHCP | опционально |
| `lab` | VM/контейнеры | изолированная | внутри lab | нет |

### `home-single` — golden path

Рекомендуемый сценарий:

1. Один зарубежный VPS.
2. Один локальный Linux-хост.
3. Роутер, на котором можно выключить DHCP.
4. Edge раздаёт DHCP и DNS, клиенты получают edge как gateway.

Если DHCP на роутере выключить нельзя, используйте router DHCP: роутер раздаёт gateway/DNS = edge или VIP.

### `inline`

Edge с двумя NIC ставится между роутером и LAN. Роутер можно оставить с DHCP, но он должен быть в bridge/AP-режиме, а Wi-Fi/AP — после edge. Иначе клиенты Wi-Fi останутся в обход шлюза.

### `home-ha`

Два edge-узла в одной LAN, VRRP VIP для gateway и DNS. Оба узла держат туннели до exit-узлов. Нужны второй хост, свободный VIP и понимание, что DHCP при failover — отдельная задача.

## 3. Требования

### 3.1. Exit VPS

- Debian 12/13 или Ubuntu 22.04/24.04.
- Public IPv4.
- Root SSH по ключу.
- `/dev/net/tun` и возможность создавать `tun`.
- Provider firewall не блокирует outbound SSH и TUN.
- 1 vCPU, 1 ГБ RAM, 10 ГБ диска — минимум.
- Доступ к консоли провайдера на случай потери SSH.
- Снимок/бэкап перед изменениями.

### 3.2. Edge

- Debian 12/13 или Ubuntu 22.04/24.04.
- x86_64 или arm64.
- 1–2 сетевых интерфейса.
- 2 ГБ RAM, 8 ГБ диска — минимум.
- Always-on, желательно UPS.
- `/dev/net/tun`.
- Физический доступ или консоль на случай ошибки в сети.
- Свободный порт 53, если edge будет DNS-сервером.

### 3.3. Роутер

- Административный доступ.
- Возможность выключить DHCP **или** задать DHCP options:
  - option 3 (router/gateway) = edge или VIP;
  - option 6 (DNS) = edge или VIP.
- Резервирование VIP/edge-адреса вне DHCP-пула.
- Понимание, что роутер остаётся WAN-шлюзом и единой точкой отказа.

### 3.4. Control host

CLI можно запускать:

- на самом edge-хосте (рекомендуется для always-on);
- на ноутбуке с Linux/macOS/WSL2;
- в CI/management-хосте.

Нужны Python 3.11+, SSH-клиент и доступ к exit VPS. Ansible ставится в отдельный venv, чтобы не ломать системный Python.

### 3.5. Сеть и доступы

- LAN CIDR, свободный VIP, диапазон DHCP.
- SSH-ключи для edge и exit.
- Источник списка префиксов: default, file или url.
- Решение по DNS: DoT через exit, fail-closed.
- Решение по IPv6: в MVP выключен.

## 4. Перед началом

- [ ] Есть консоль/снимок VPS.
- [ ] Есть физический доступ или консоль edge.
- [ ] Известны имена LAN-интерфейсов.
- [ ] Известны LAN CIDR, router IP, свободный VIP.
- [ ] Есть доступ к DHCP-настройкам роутера.
- [ ] Проверено, что порт 53 не занят `systemd-resolved`, AdGuard, Pi-hole или другим resolver.
- [ ] Проверено, что нет работающих BIRD/FRR/keepalived на edge.
- [ ] Проверено, что провайдер не блокирует SSH/TUN на VPS.
- [ ] Есть план отката DHCP и доступа к edge.
- [ ] Сделан бэкап текущих конфигов.

## 5. Установка CLI

Целевой сценарий после реализации installer:

```bash
git clone https://github.com/bibigon812/smartgate.git
cd smartgate
sudo ./install.sh
```

Installer должен:

- поставить `smartgate` в `/usr/local/bin`;
- создать pinned venv `/opt/smartgate/venv` с `ansible-core` и коллекциями;
- не менять сетевые настройки;
- проверить checksum релиза.

Не используйте непроверенный `curl | bash`. Если проект предлагает one-liner, он должен быть подписан и иметь checksum.

До реализации CLI автоматизированного сценария в репозитории нет. Этот документ — спецификация целевого UX; существующие ручные Ansible-конфиги не являются публичным интерфейсом проекта.

Реальный inventory не коммитится. В репозитории есть только `ansible/inventories/example/hosts.yml.example`; локальный `ansible/inventories/prod/hosts.yml` создаётся из него и исключён через `.gitignore`.

## 6. `smartgate init`

Мастер задаёт вопросы и пишет `smartgate.yaml`, inventory, ключи и секреты.

Пример результата:

```yaml
profile: home-single

exit:
  host: vpn.example.com
  ssh_user: root
  ssh_port: 22

edge:
  host: localhost
  lan_interface: enp1s0
  address: 192.168.10.2/24
  router: 192.168.10.1

dhcp:
  mode: edge
  range: 192.168.10.100-192.168.10.199
  vip: 192.168.10.254

dns:
  mode: dot-via-exit
  fail_closed: true

routes:
  source: default
  update: 6h

ha:
  enabled: false

monitoring:
  enabled: false

mobile:
  enabled: false
```

Вопросы мастера:

1. Профиль: `home-single`, `home-ha`, `inline`, `lab`.
2. Exit VPS: host, SSH user, port, ключ.
3. Edge: localhost или SSH; LAN-интерфейс; адрес; router.
4. DHCP: edge или router.
5. VIP и DHCP range.
6. DNS: DoT через exit; fail-closed.
7. Источник префиксов и интервал обновления.
8. HA: да/нет.
9. Мониторинг: да/нет.
10. Mobile OpenVPN: да/нет.

`init` не должен менять сеть. Он только готовит файлы.

## 7. `smartgate doctor`

Preflight без изменений. Проверяет:

- ОС, версию, архитектуру, systemd, Python.
- SSH до exit и edge, ключ, `PermitTunnel`.
- `/dev/net/tun`, возможность создать `tun`.
- IP forwarding и текущие sysctl.
- Порты 22/53/1194; конфликт `systemd-resolved` на 53.
- Установленные BIRD/FRR/keepalived/OpenVPN.
- LAN-интерфейс, default route, несколько DHCP-серверов.
- Доступность router, возможность DHCP cutover.
- DNS: прямой vs через exit, признаки подмены.
- VPS firewall, public IP, NAT.
- Диск, RAM, время, версии пакетов.
- MTU, PMTUD, IPv6.
- Существующие маршруты и таблицу `exclude`.

`doctor` должен выдавать конкретные действия, а не только «FAIL».

## 8. `smartgate plan`

```bash
smartgate plan
```

Под капотом:

```bash
ansible-playbook site.yml --check --diff
```

Пользователь видит:

- какие пакеты будут установлены;
- какие файлы изменятся;
- какие сервисы перезапустятся;
- какие sysctl/nftables-правила появятся;
- какие маршруты и DNS-настройки изменятся.

`plan` ничего не меняет. Если diff слишком большой или непонятный — остановиться и разобраться.

## 9. `smartgate apply`

```bash
smartgate apply
```

Порядок:

1. Backup конфигов и артефактов.
2. Рендер inventory и шаблонов.
3. Валидация BIRD, unbound, nftables, sshd, keepalived.
4. Dead-man switch на 10 минут.
5. Canary: сначала exit, затем edge.
6. Проверка SSH и сервисов.
7. `smartgate verify`.
8. `smartgate confirm` — отмена автоотката.

Если SSH потерян, timer вернёт предыдущий конфиг. Если изменения успешны, `confirm` обязателен.

## 10. `smartgate verify`

Проверяет:

- SSH до edge и exit.
- `birdc show protocols`, OSPF/BGP-соседей.
- Количество маршрутов и отсутствие netlink drops.
- `ip route get` для заблокированного и прямого адреса.
- Egress через exit для заблокированного направления.
- Прямой egress для RU-направления.
- DNS через VIP/edge: ответы, latency, отсутствие подмены.
- DHCP: клиент получает правильный gateway/DNS.
- VRRP: master/backup, если HA.
- IPv6: нет глобального адреса и RA.

`smartgate verify --json` — для CI и мониторинга.

## 11. LAN cutover

Это отдельный шаг. Не делайте его в одном `apply` с установкой.

### 11.1. Edge DHCP

1. `smartgate lan cutover --dry-run`.
2. Выключить DHCP на роутере.
3. Включить DHCP на edge с коротким lease (10 минут).
4. Продлить lease на одном тестовом клиенте.
5. Проверить gateway, DNS, egress, split-routing.
6. Продлить lease на остальных клиентах.
7. Вернуть нормальный lease.

Откат:

1. Выключить DHCP на edge.
2. Включить DHCP на роутере.
3. Продлить lease на клиентах.
4. `smartgate lan rollback`.

### 11.2. Router DHCP

1. Зарезервировать edge/VIP вне DHCP-пула.
2. Поставить option 3 = edge/VIP, option 6 = edge/VIP.
3. Уменьшить lease до 10 минут.
4. Продлить lease на тестовом клиенте.
5. Проверить egress, DNS, split-routing.
6. Вернуть нормальный lease.

Откат: вернуть прежние options 3/6, продлить lease.

### 11.3. Статические клиенты

Устройства со статическим gateway/DNS нужно перевести вручную. До cutover составьте список: серверы, NAS, принтеры, IoT, камеры. Иначе после failover они останутся на старом шлюзе.

### 11.4. Wi-Fi

При one-arm Wi-Fi-клиенты остаются в той же LAN и получают edge как gateway. При inline убедитесь, что AP/Wi-Fi находится после edge, иначе трафик обойдёт шлюз.

## 12. Профиль `home-ha`

Дополнительно к `home-single`:

- второй edge с тем же набором ролей;
- туннели до всех exit-узлов;
- unbound на обоих;
- keepalived, VIP, `unicast_peer`;
- health-check BIRD/OSPF/туннелей;
- VIP для gateway и DNS;
- DHCP: router DHCP с VIP или Kea HA;
- тест падения каждого edge и потеря туннелей.

Обратный путь:

- `t400` анонсирует LAN с меньшей метрикой;
- `box01` — с большей;
- exit предпочитает `t400`, при падении переключается на `box01`.

VRRP не защищает от падения exit-узла, роутера, провайдера или коммутатора. Это отдельные failure domains.

## 13. После установки

- Отключить парольный SSH и root-логин по паролю.
- Проверить, что ключи ограничены `from=`.
- Включить автообновление списка префиксов.
- Настроить `smartgate backup` по расписанию.
- Включить мониторинг, если нужен.
- Проверить `smartgate upgrade` на тестовом стенде.
- Записать runbook отката.

## 14. Восстановление

- **Потерян SSH к VPS:** консоль провайдера, дождаться dead-man switch, `smartgate rollback`.
- **Потерян SSH к edge:** физическая консоль, `smartgate rollback`.
- **Нет интернета после cutover:** вернуть DHCP на роутер, проверить gateway/DNS, `ip_forward`, nftables.
- **DNS не работает:** проверить unbound, порт 53, доступность exit, fail-closed.
- **Split-brain VRRP:** проверить `unicast_peer`, proto 112, LAN-связность.
- **Сломан маршрут:** вернуть предыдущий route artifact и reload BIRD.

## 15. Troubleshooting

| Симптом | Вероятная причина | Что проверить |
|---|---|---|
| Нет интернета после cutover | неверный gateway/DNS, `ip_forward=0`, nftables, VRRP | DHCP lease, `ip route`, `sysctl`, `nft list ruleset` |
| DNS SERVFAIL | unbound не запущен, порт 53 занят, exit недоступен | `systemctl status unbound`, `ss -ulnp`, `dig` |
| DNS отдаёт неверные ответы | клиент использует DNS роутера, прямой upstream, DoT не активен | `resolvectl`, unbound config, `dig` напрямую и через exit |
| Туннель не поднимается | SSH-ключ, `PermitTunnel`, firewall, MTU | `ssh -w`, `ip link`, `journalctl -u sshtun@` |
| OSPF/BGP не сходится | неверные интерфейсы, адреса, auth, MTU | `birdc show protocols`, `birdc show ospf neighbors` |
| VRRP split-brain | `unicast_peer`, firewall, LAN partition | `tcpdump` proto 112, keepalived logs |
| Два DHCP-сервера | router DHCP не выключен | broadcast DHCP, lease time |
| Потерян SSH | nftables/sshd/network | консоль, dead-man switch, rollback |
| Низкая скорость | CPU, MTU/MSS, encryption | `iperf3`, `ping -M do`, CPU load |
| IPv6-утечка | RA/global address | `ip -6 addr`, `sysctl`, router RA |

## 16. Ограничения MVP

- Один WAN и один роутер — единая точка отказа.
- Один exit — единая точка отказа для внешних маршрутов.
- IPv6 выключен.
- SSH-туннели могут быть заблокированы DPI; обфускация не входит в MVP.
- Нет Windows-edge и OpenWrt-edge.
- Нет web UI.
- Качество списка префиксов — ответственность пользователя/источника.
- Нет автоматического создания VPS у провайдеров.
- Нет SLA; проект не заменяет коммерческий сервис.

## 17. Объём MVP

1. Профиль `home-single`, one-arm.
2. Debian 12/13, Ubuntu 22.04/24.04.
3. CLI: `init`, `doctor`, `plan`, `apply`, `verify`, `status`, `rollback`.
4. Ansible-роли: `common`, `bird`, `sshtun`, `unbound`, `nftables`, `exclude`.
5. DHCP: edge или router.
6. DNS: DoT через exit, fail-closed.
7. Route list: default/file/url, timer, diff, rollback.
8. Документация: quickstart, recovery, troubleshooting.

После MVP: `home-ha`, VRRP, inline, Kea HA, мониторинг, mobile OpenVPN, Terraform/cloud-init, `adopt` для существующих установок.
