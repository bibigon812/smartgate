ANSIBLE_DIR := ansible
VENV := $(CURDIR)/.venv
ANSIBLE_INVENTORY := $(VENV)/bin/ansible-inventory
ANSIBLE_PLAYBOOK := $(VENV)/bin/ansible-playbook
LIMIT ?=
ANSIBLE_LIMIT := $(if $(LIMIT),--limit $(LIMIT),)

.PHONY: venv check doctor backup plan prefixes prefixes-collect prefixes-publish bird bird-config bird-fragments bird-sysctl bird-netlink

venv:
	test -x $(VENV)/bin/python || uv venv $(VENV)
	uv pip install --python $(VENV)/bin/python ansible-core

check:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_INVENTORY) --graph

doctor:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/doctor.yml $(ANSIBLE_LIMIT)

backup:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/backup.yml $(ANSIBLE_LIMIT)

plan:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/site.yml --check --diff $(ANSIBLE_LIMIT)

prefixes:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/prefixes.yml $(ANSIBLE_LIMIT)

prefixes-collect:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/prefixes.yml --tags 'prefixes:collect' $(ANSIBLE_LIMIT)

prefixes-publish:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/prefixes.yml --tags 'prefixes:publish' $(ANSIBLE_LIMIT)

bird:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/bird.yml $(ANSIBLE_LIMIT)

bird-config:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/bird.yml --tags 'bird:config' $(ANSIBLE_LIMIT)

bird-fragments:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/bird.yml --tags 'bird:fragments' $(ANSIBLE_LIMIT)

bird-sysctl:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/bird.yml --tags 'bird:sysctl' $(ANSIBLE_LIMIT)

bird-netlink:
	cd $(ANSIBLE_DIR) && $(ANSIBLE_PLAYBOOK) playbooks/bird.yml --tags 'bird:sysctl,bird:config' $(ANSIBLE_LIMIT)
