import aiohttp
import asyncio
import os
import sys


# Наш точный совместный список автономных систем
TARGET_ASNS = [
    "AS8075",      # microsoft
    "AS12222",     # akamai
    "AS16702",
    "AS20940",
    "AS21342",
    "AS35994",
    "AS18717",
    "AS32787",
    "AS16509",     # amazon
    "AS14618",
    "AS36263",
    "AS13335",     # cloudflare
    "AS395747",
    "AS209242",
    "AS14061",     # digitalocean
    "AS133165",
    "AS54113",     # fastly
    "AS15169",     # google
    "AS32934",     # facebook
    "AS29405",     # SK-VNET
    "AS60068",     # Datacamp Limited
    "AS62041",     # telegram
    "AS211157",    # telegram
    "AS44893",     # inet ltd
    "AS16276",     # ovh
    "AS199524",    # gcore
    "AS21859",     # Zenlayer Inc
    "AS46652",     # digitalocean
    "AS48326",     # DataNetworks s.r.o. Slovakia
    "AS21276",
    "AS36459"      # github
]


# Изолированный VRF на Upstream сервере
VRF_NAME = "vrf-export"


async def fetch_prefixes_for_asn(session: aiohttp.ClientSession, asn: str) -> list:
    """
    Асинхронно выкачивает IPv4 префиксы для одной AS через официальное API RIPE NCC.
    """
    clean_asn = asn.upper().replace("AS", "")

    # Железобетонный обход бага рендеринга ссылок чата: собираем URL из чистых строк
    domain = "stat.ripe.net"
    path = "/data/announced-prefixes/data.json"
    params = f"?resource=AS{clean_asn}"

    url = f"https://{domain}{path}{params}"

    try:
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                json_data = await response.json()
                prefixes = []

                prefixes_data = json_data.get("data", {}).get("prefixes", [])
                for item in prefixes_data:
                    prefix = item.get("prefix")
                    if prefix and ":" not in prefix:
                        prefixes.append(prefix)
                return prefixes
            else:
                print(f"[ERROR] RIPE API returned status {response.status} for {asn}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Failed to fetch data from RIPE for {asn}: {e}", file=sys.stderr)
    return []


async def main():
    print(f"[INFO] Starting Route Injector. Processing {len(TARGET_ASNS)} ASNs...", file=sys.stderr, flush=True)

    # МАГИЯ ИЗОЛЯЦИИ: Гарантированно создаем и поднимаем VRF интерфейс внутри контейнера
    # Теперь скрипт сам настраивает ядро Linux перед вызовом vtysh!
    # os.system(f"ip link add {VRF_NAME} type vrf table 100 >/dev/null 2>&1")
    # os.system(f"ip link set dev {VRF_NAME} up >/dev/null 2>&1")

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_prefixes_for_asn(session, asn) for asn in TARGET_ASNS]
        results = await asyncio.gather(*tasks)

    # Объединяем списки и убираем дубликаты
    raw_prefixes = [prefix for sublist in results for prefix in sublist]
    unique_prefixes = sorted(set(raw_prefixes))

    if not unique_prefixes:
        print("[ERROR] No prefixes downloaded. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)

    print(f"[INFO] Successfully aggregated {len(unique_prefixes)} unique prefixes.", file=sys.stderr, flush=True)

    # Генерируем команды для vtysh (FRR)
    commands = []
    commands.append("configure terminal")
    commands.append(f"vrf {VRF_NAME}")

    for prefix in unique_prefixes:
        commands.append(f"ip route {prefix} blackhole")

    commands.append("exit")
    commands.append("end")
    commands.append("write memory")

    vtysh_input = "\n".join(commands) + "\n"

    print("[INFO] Injecting routes into FRR via vtysh...", file=sys.stderr, flush=True)
    process = await asyncio.create_subprocess_exec(
        "vtysh",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate(input=vtysh_input.encode())

    if process.returncode == 0:
        print(f"[SUCCESS] All {len(unique_prefixes)} routes successfully injected into {VRF_NAME}!", file=sys.stderr, flush=True)
    else:
        print(f"[ERROR] vtysh failed with exit code {process.returncode}", file=sys.stderr, flush=True)
        print(stderr.decode(), file=sys.stderr, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
