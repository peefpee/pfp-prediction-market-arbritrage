import os
import time
from decimal import Decimal

from libaries.limitless import LimitlessClient
from libaries.polymarket import PolymarketClient


def format_price(price):
    if price is None:
        return "N/A"
    return format(price.normalize(), "f")


def snapshot_key(snapshot):
    if snapshot is None:
        return None

    return (
        snapshot.get("yes", {}).get("bid"),
        snapshot.get("yes", {}).get("ask"),
        snapshot.get("no", {}).get("bid"),
        snapshot.get("no", {}).get("ask"),
    )


def estimate_polymarket_fee(price):
    if price is None:
        return None

    distance_from_mid = abs(price - Decimal("0.5")) / Decimal("0.5")
    fee_scale = Decimal("1") - min(distance_from_mid, Decimal("1"))
    return Decimal("0.01") + (Decimal("0.01") * fee_scale)


def best_arbitrage(limitless_prices, polymarket_prices):
    candidates = []

    limitless_yes_ask = limitless_prices.get("yes", {}).get("ask")
    limitless_no_ask = limitless_prices.get("no", {}).get("ask")
    polymarket_yes_ask = polymarket_prices.get("yes", {}).get("ask")
    polymarket_no_ask = polymarket_prices.get("no", {}).get("ask")

    if limitless_yes_ask is not None and polymarket_no_ask is not None:
        total_cost = limitless_yes_ask + polymarket_no_ask
        candidates.append(
            {
                "gap": "LIMITLESS YES / POLYMARKET NO",
                "difference": Decimal("1") - total_cost,
                "limitless_price": limitless_yes_ask,
                "polymarket_price": polymarket_no_ask,
            }
        )

    if polymarket_yes_ask is not None and limitless_no_ask is not None:
        total_cost = polymarket_yes_ask + limitless_no_ask
        candidates.append(
            {
                "gap": "POLYMARKET YES / LIMITLESS NO",
                "difference": Decimal("1") - total_cost,
                "limitless_price": limitless_no_ask,
                "polymarket_price": polymarket_yes_ask,
            }
        )

    if not candidates:
        return None

    return max(candidates, key=lambda item: item["difference"])


def execution_threshold(arbitrage):
    if arbitrage is None:
        return None

    polymarket_fee = estimate_polymarket_fee(arbitrage["polymarket_price"])
    limitless_fee = Decimal("0.0075")
    combined_slippage = Decimal("0.015")
    buffer = Decimal("0.015")
    return polymarket_fee + limitless_fee + combined_slippage + buffer


def print_opportunity(limitless_prices, polymarket_prices):
    arbitrage = best_arbitrage(limitless_prices, polymarket_prices)
    if arbitrage is None:
        return

    required_edge = execution_threshold(arbitrage)
    if required_edge is None or arbitrage["difference"] <= required_edge:
        return

    print(f"limitless url : {limitless_prices.get('market_url', 'N/A')}")
    print(f"polymarket url : {polymarket_prices.get('market_url', 'N/A')}")
    print(
        "limitless",
        f"YES - bid : {format_price(limitless_prices['yes']['bid'])}",
        f"ask : {format_price(limitless_prices['yes']['ask'])}",
        f"NO - bid : {format_price(limitless_prices['no']['bid'])}",
        f"ask : {format_price(limitless_prices['no']['ask'])}",
    )
    print(
        "polymarket",
        f"YES - bid : {format_price(polymarket_prices['yes']['bid'])}",
        f"ask : {format_price(polymarket_prices['yes']['ask'])}",
        f"NO - bid : {format_price(polymarket_prices['no']['bid'])}",
        f"ask : {format_price(polymarket_prices['no']['ask'])}",
    )
    print(f"gap : {arbitrage['gap']}")
    print(f"difference : {format_price(arbitrage['difference'])}")
    print(
        "arbitrage possible : YES",
        f"(required edge: {format_price(required_edge)})",
    )
    print()


def prompt_market_slugs():
    limitless_slug = input(
        "Enter the Limitless market slug: "
    ).strip()
    polymarket_slug = input(
        "Enter the Polymarket event slug "
        "(example: solana-up-or-down-march-28-2026-8am-et): "
    ).strip()

    if not limitless_slug or not polymarket_slug:
        raise SystemExit("Both market slugs are required.")

    return limitless_slug, polymarket_slug


def main():
    limitless_slug, polymarket_slug = prompt_market_slugs()

    limitless_client = LimitlessClient(
        api_key=os.getenv("LIMITLESS_API_KEY"),
        market_slug=limitless_slug,
    ).connect()
    polymarket_client = PolymarketClient(
        event_slug=polymarket_slug,
    ).connect()

    try:
        if not limitless_client.wait_for_prices(timeout=15):
            raise SystemExit("Timed out waiting for Limitless prices.")

        if not polymarket_client.wait_for_prices(timeout=15):
            raise SystemExit("Timed out waiting for Polymarket prices.")

        last_seen = None

        while True:
            limitless_prices = limitless_client.get_latest_prices()
            polymarket_prices = polymarket_client.get_latest_prices()
            if limitless_prices is None or polymarket_prices is None:
                time.sleep(0.1)
                continue

            current = (snapshot_key(limitless_prices), snapshot_key(polymarket_prices))
            if current != last_seen:
                print_opportunity(limitless_prices, polymarket_prices)
                last_seen = current

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        limitless_client.close()
        polymarket_client.close()


if __name__ == "__main__":
    main()
