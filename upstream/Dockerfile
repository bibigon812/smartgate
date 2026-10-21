# ======================================================================
# ЭТАП 1: Сборка shadowsocks-rust из исходников (Мультистейдж-сборка)
# ======================================================================
# Используем официальный образ Rust на базе Alpine для сборки легковесного бинарника
FROM rust:alpine AS ss-builder

RUN apk add --no-cache musl-dev git openssl-dev

# Скачиваем стабильную версию shadowsocks-rust
WORKDIR /src
RUN git clone --depth 1 https://github.com/shadowsocks/shadowsocks-rust .

# Собираем только серверный и клиентский бинарники в режиме Release (максимальная скорость)
RUN cargo build --release --bin ssserver --bin sslocal

# ======================================================================
# ЭТАП 2: Финальный сетевой образ Upstream Node
# ======================================================================
# Базируемся на официальном, проверенном образе FRR
FROM quay.io/frrouting/frr:10.5.0

# Отключаем интерактивные запросы apt при сборке
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем зависимости для Python-бэкенда и утилиты отладки через apk
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-aiohttp \
    ca-certificates \
    iproute2 \
    iptables \
    net-tools \
    iputils \
    procps


# Копируем скомпилированные бинарники Shadowsocks из первого этапа
COPY --from=ss-builder /src/target/release/ssserver /usr/local/bin/ssserver
COPY --from=ss-builder /src/target/release/sslocal /usr/local/bin/sslocal

# Создаем рабочую директорию для нашего Route Injector скрипта
WORKDIR /app
COPY src/ /app/src/

# Информационные порты (443 для Shadowsocks, 179 для eBGP маршрутизации)
EXPOSE 443/tcp
EXPOSE 179/tcp

# Точка входа по умолчанию: запускаем стандартный скрипт инициализации FRR.
# В docker-compose мы переопределим команду, чтобы запускать параллельно
# и FRR, и сервер Shadowsocks.
CMD ["/usr/lib/frr/frrinit.sh"]
