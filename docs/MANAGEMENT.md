# Управление SmartGate

- **Статус:** спецификация. CLI `smartgate` и Ansible-роли ещё не реализованы.
- **Связанные документы:** [ARCHITECTURE.md](../ARCHITECTURE.md), [DEPLOYMENT.md](DEPLOYMENT.md).

## 1. Решение

**Ansible — движок, CLI — продукт.**

- Ansible остаётся единственным механизмом описания состояния хостов.
- Пользователь работает с `smartgate`, а не с inventory, group_vars и тегами.
- CLI не пишет конфиги напрямую: он вызывает Ansible или контролируемый pipeline обновления маршрутов.
- Runtime-отказоустойчивость обеспечивают BIRD, keepalived, unbound и systemd timers, а не Ansible.
- Продвинутый пользователь может выполнить `smartgate render` и забрать готовый Ansible-проект.

## 2. Слои

| Слой | Инструмент | Ответственность |
|---|---|---|
| Desired state | Git + Ansible + `smartgate.yaml` | пакеты, sysctl, systemd, BIRD, keepalived, unbound, nftables, SSH, мониторинг |
| Dynamic data | build pipeline + systemd timer | список префиксов, артефакт, проверка, атомарный reload |
| Runtime | BIRD, keepalived, unbound | маршрутизация, failover, DNS |
| Operator UX | `smartgate` CLI | init, doctor, plan, apply, verify, status, routes, cutover, rollback |

Ansible не должен запускаться по таймеру и не должен реагировать на отказы. Это работа runtime.

## 3. Источник истины

### 3.1. `smartgate.yaml`

Пользовательский source of truth. Файл хранится в git вместе с секретами в зашифрованном виде или отдельно.

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

Схема версионируется. При изменении схемы `smartgate upgrade` выполняет миграцию.

### 3.2. Сгенерированный Ansible

`smartgate init` и `smartgate plan` генерируют:

```text
.work/
  inventory/hosts.yml
  group_vars/all.yml
  host_vars/
  rendered/
  backups/
  artifacts/
```

Это производные файлы. Пользователь не должен править их руками: при следующем `plan` они будут перезаписаны. Для ручной правки есть `smartgate render --output ./ansible`, после чего пользователь владеет результатом.

Реальный inventory (`ansible/inventories/prod/hosts.yml`) и `config/smartgate.yaml` игнорируются git. В репозитории хранится только `ansible/inventories/example/hosts.yml.example` с placeholder-адресами.

### 3.3. Секреты

- Отдельный SSH-ключ на каждый edge/origin.
- Ключи и пароли — в Ansible Vault или SOPS, а не в `smartgate.yaml`.
- Права `0600`, каталог секретов вне git.
- Bootstrap-ключ используется только для первичной установки; после неё root-пароль и парольный SSH отключаются.
- `smartgate support-bundle` редактирует секреты и приватные ключи.

## 4. CLI

Целевой интерфейс:

| Команда | Меняет состояние | Назначение |
|---|---|---|
| `smartgate init` | локальные файлы | мастер, `smartgate.yaml`, inventory, ключи |
| `smartgate doctor` | нет | preflight: SSH, ОС, TUN, порты, конфликты, DNS |
| `smartgate plan` | нет | `ansible-playbook --check --diff` |
| `smartgate apply` | да | применить с бэкапом и dead-man switch |
| `smartgate confirm` | да | подтвердить изменения, отменить автооткат |
| `smartgate rollback` | да | вернуть последний снапшот |
| `smartgate status` | нет | BGP/OSPF, route count, tun, VRRP, DNS; `--json` |
| `smartgate verify` | нет | egress, split-routing, DNS, SSH, VRRP |
| `smartgate routes build` | локально | собрать артефакт списка префиксов |
| `smartgate routes diff` | нет | показать изменения |
| `smartgate routes deploy` | да | validate + canary + reload, с откатом |
| `smartgate lan cutover` | да | переключить DHCP/gateway на edge |
| `smartgate lan rollback` | да | вернуть DHCP/gateway на роутер |
| `smartgate backup` | локально/remote | конфиги и артефакты |
| `smartgate upgrade` | да | обновить CLI и playbooks, миграции |
| `smartgate support-bundle` | нет | логи и диагностика с редакцией |
| `smartgate render` | локально | отдать Ansible-проект наружу |
| `smartgate failover test` | да | управляемый тест падения edge |

Правила:

- `apply`, `rollback`, `lan cutover`, `routes deploy` требуют явного подтверждения.
- `status` и `doctor` никогда не меняют состояние.
- `status --json` — стабильный интерфейс для скриптов и будущего web UI.
- `doctor` возвращает ненулевой код при blocking-проблемах.
- Все команды пишут структурированный лог в `~/.local/state/smartgate/`.

## 5. Apply pipeline

1. `doctor` — preflight без изменений.
2. `backup` — конфиги, route artifacts, состояние сервисов.
3. `render` — сгенерировать inventory и конфиги.
4. `validate` — проверить конфиги до применения.
5. `arm` — включить dead-man switch на 10 минут.
6. `apply` — canary: сначала один узел, затем остальные.
7. `verify` — проверить SSH, DNS, egress, split-routing, VRRP.
8. `confirm` — отменить автооткат.
9. При таймауте или ошибке — `rollback`.

Для сетевых изменений Ansible запускается с `serial: 1` и ограниченным `max_fail_percentage`. SSH-сессия и консоль провайдера должны быть открыты до начала.

### 5.1. Dead-man switch

Перед изменением nftables/SSH/сети на хосте создаётся временный systemd timer:

- через 10 минут восстанавливает предыдущий конфиг и перезапускает сервисы;
- `smartgate confirm` отменяет timer;
- timer не переживает перезагрузку, но после неё остаётся last-known-good конфиг.

Это защита от потери SSH на удалённом VPS. Для LAN cutover дополнительно нужен план возврата DHCP на роутер.

### 5.2. Валидация

| Компонент | Проверка |
|---|---|
| BIRD | `bird -p -c <file>` до reload |
| unbound | `unbound-checkconf` |
| nftables | `nft -c -f <file>` |
| sshd | `sshd -t` |
| keepalived | config test версии или запуск в foreground |
| systemd | `systemd-analyze verify` |
| YAML | schema + `ansible-lint` |
| Ansible | `--check --diff` |

Handler перезапускает сервис только после успешной валидации. Ошибка валидации не должна оставлять хост с нерабочим конфигом.

## 6. Route list pipeline

Список префиксов — данные, а не конфиг хоста.

1. **Source:** `default` (список проекта), `file` (свой CIDR), `url` (community).
2. **Build:** нормализация, дедупликация, проверка размера, checksum, версия.
3. **Validate:** запрет default route, RFC1918, management-IP, IP exit-узла, слишком широких префиксов.
4. **Diff:** показать, что добавится/удалится.
5. **Deploy:** canary на одном origin, `bird -p`, reload, проверка количества маршрутов.
6. **Schedule:** systemd timer на origin с jitter; Ansible не участвует в регулярном обновлении.
7. **Rollback:** предыдущий артефакт и предыдущий конфиг BIRD.

Внешние списки принимаются только с checksum/подписью. Обновление не должно менять локальный `exclude` и management-доступ.

## 7. Секреты и доступ

- Отдельные SSH-ключи для edge/origin; `from=` в `authorized_keys`.
- `PermitRootLogin prohibit-password`, `PermitTunnel` только для нужных пользователей.
- nftables: SSH только из management-сети, DNS только из LAN.
- Ansible Vault/SOPS; пароль vault не хранится в репозитории.
- Ротация ключей — `smartgate rotate-keys` (будущая команда).

## 8. Соглашения Ansible

- Роли: `common`, `bird`, `sshtun`, `unbound`, `keepalived`, `nftables`, `monitoring`, `exclude`.
- Конфиги — шаблоны; IP/ASN/интерфейсы — из inventory, не хардкод в шаблонах.
- `template` с `validate`, `systemd` с `daemon_reload`, handlers для reload.
- Никаких `shell`, если есть модуль.
- Никаких `curl | bash` внутри ролей.
- `--check --diff` в CI и в `plan`.
- `ansible-lint`, Molecule для Debian/Ubuntu, lab-тест BIRD/OSPF/VRRP.
- Inventory генерируется; advanced-пользователь может использовать `render`.

## 9. Runtime vs configuration

- BIRD/keepalived/unbound — runtime; они переживают отказы без Ansible.
- Route timer обновляет только данные.
- `apply` — только по явной команде, не по таймеру.
- `status` читает runtime, а не git.
- `doctor` сравнивает desired state с actual, но не исправляет.

## 10. Break-glass

Прямой SSH и правка конфигов допустимы только в аварии.

1. Сохранить копию текущего файла.
2. Внести минимальное изменение.
3. Проверить синтаксис и reload.
4. Зафиксировать причину в runbook.
5. После восстановления — `smartgate doctor` и `smartgate plan`, чтобы вернуть drift в git.

CLI не должен препятствовать break-glass. Но и не должен молча затирать ручные изменения без diff.

## 11. Non-goals

- Ansible как runtime control plane.
- CLI как второй source of truth.
- Web UI в MVP.
- Kubernetes/оператор.
- Docker на production-хостах.
- Автоматическое создание VPS у провайдеров в MVP.
- Поддержка Windows в роли edge.

## 12. Открытые вопросы

- Язык CLI: Python/Typer или Go.
- Где живёт control host: edge, ноутбук или CI.
- Формат версионирования `smartgate.yaml`.
- Backend секретов: Vault или SOPS+age.
- Дефолтный источник списка префиксов.
- Нужен ли web UI после MVP.
- Нужен ли `smartgate adopt` для уже существующих ручных установок.
