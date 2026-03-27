import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libaries.polymarket import PolymarketClient


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
    client = PolymarketClient(
        timeframe=os.getenv("MARKET_TIMEFRAME", "auto"),
    ).connect()

    try:
        if not client.wait_for_prices(timeout=15):
            raise SystemExit("Timed out waiting for Polymarket prices.")

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
