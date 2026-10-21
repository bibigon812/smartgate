# Инвентори

- `prod/hosts.yml` — локальный inventory с реальными хостами. Он **не коммитится**: каталог `prod/` и файлы `hosts.yml` исключены через `.gitignore`.
- `example/hosts.yml.example` — шаблон для новой установки.
- `local/` — дополнительный локальный inventory, тоже исключён.

Для начала работы:

```bash
cp ansible/inventories/example/hosts.yml.example ansible/inventories/prod/hosts.yml
$EDITOR ansible/inventories/prod/hosts.yml
```

Никогда не добавляйте реальные адреса, ключи и доступы в `example/`.
