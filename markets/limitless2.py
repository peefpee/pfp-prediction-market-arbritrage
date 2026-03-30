import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libaries.limitless import LimitlessClient


def format_price(price):
    if price is None:
        return "N/A"
    return format(price.normalize(), "f")


def snapshot_key(snapshot):
    return (
        snapshot.get("yes", {}).get("bid"),
        snapshot.get("yes", {}).get("ask"),
        snapshot.get("no", {}).get("bid"),
        snapshot.get("no", {}).get("ask"),
    )


def print_orderbook(snapshot):
    print(f"Market: {snapshot.get('market_slug', 'unknown')}")
    print(
        "YES best bid/ask:",
        f"{format_price(snapshot['yes']['bid'])} / {format_price(snapshot['yes']['ask'])}",
    )
    print(
        "NO  best bid/ask:",
        f"{format_price(snapshot['no']['bid'])} / {format_price(snapshot['no']['ask'])}",
    )
    print(f"Timestamp: {snapshot.get('timestamp', 'unknown')}")
    print()


def main():
<<<<<<< HEAD
    market_slug = input("Enter the Limitless market slug: ").strip()
    if not market_slug:
        raise SystemExit("A Limitless market slug is required.")

    client = LimitlessClient(
        api_key=os.getenv("LIMITLESS_API_KEY"),
        market_slug=market_slug,
=======
    client = LimitlessClient(
        api_key=os.getenv("LIMITLESS_API_KEY"),
        timeframe=os.getenv("MARKET_TIMEFRAME", "auto"),
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae
    ).connect()

    try:
        if not client.wait_for_prices(timeout=15):
            raise SystemExit("Timed out waiting for Limitless prices.")

        last_seen = None
        while True:
            snapshot = client.get_latest_prices()
            if snapshot is None:
                time.sleep(0.1)
                continue

            current = snapshot_key(snapshot)
            if current != last_seen:
                print_orderbook(snapshot)
                last_seen = current

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
