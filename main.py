import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from libaries.limitless import LimitlessClient
from libaries.polymarket import PolymarketClient

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
SUPPORTED_COINS = ("BTC", "ETH", "SOL", "XRP")
SUPPORTED_TIMEFRAMES = ("m15", "hourly", "daily", "weekly", "monthly")
DEFAULT_CONFIG = {
    coin: {timeframe: True for timeframe in SUPPORTED_TIMEFRAMES}
    for coin in SUPPORTED_COINS
}


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


def load_config(path=CONFIG_PATH):
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
        return json.loads(json.dumps(DEFAULT_CONFIG))

    loaded = json.loads(path.read_text())
    config = json.loads(json.dumps(DEFAULT_CONFIG))

    for coin, timeframes in loaded.items():
        coin_key = str(coin).strip().upper()
        if coin_key not in config or not isinstance(timeframes, dict):
            continue

        for timeframe, enabled in timeframes.items():
            timeframe_key = str(timeframe).strip().lower()
            if timeframe_key in config[coin_key]:
                config[coin_key][timeframe_key] = bool(enabled)

    return config


class ArbitrageDetector:
    def __init__(self, coin, timeframe, limitless_client, polymarket_client):
        self.coin = coin
        self.timeframe = timeframe
        self.limitless_client = limitless_client
        self.polymarket_client = polymarket_client
        self._last_seen = None

    def start(self):
        self.limitless_client.connect()
        self.polymarket_client.connect()
        return self

    def wait_ready(self, timeout=15):
        return (
            self.limitless_client.wait_for_prices(timeout=timeout)
            and self.polymarket_client.wait_for_prices(timeout=timeout)
        )

    def get_profitable_opportunity(self):
        limitless_prices = self.limitless_client.get_latest_prices()
        polymarket_prices = self.polymarket_client.get_latest_prices()
        if limitless_prices is None or polymarket_prices is None:
            return None

        current = (snapshot_key(limitless_prices), snapshot_key(polymarket_prices))
        if current == self._last_seen:
            return None
        self._last_seen = current

        arbitrage = best_arbitrage(limitless_prices, polymarket_prices)
        required_edge = execution_threshold(arbitrage)
        if arbitrage is None or required_edge is None:
            return None

        difference = arbitrage["difference"]
        if difference <= required_edge:
            return None

        return {
            "coin": self.coin,
            "timeframe": self.timeframe,
            "limitless": limitless_prices,
            "polymarket": polymarket_prices,
            "gap": arbitrage["gap"],
            "difference": difference,
            "required_edge": required_edge,
            "net_edge": difference - required_edge,
        }

    def close(self):
        self.limitless_client.close()
        self.polymarket_client.close()


def build_detectors(config):
    api_key = os.getenv("LIMITLESS_API_KEY")
    detectors = []

    for coin in SUPPORTED_COINS:
        if not any(config[coin].values()):
            continue

        coinslug = coin.lower()
        limitless_markets = LimitlessClient(
            api_key=api_key,
            coinslug=coinslug,
        ).list_active_markets()
        polymarket_markets = PolymarketClient(
            coinslug=coinslug,
        ).list_active_markets()

        for timeframe in SUPPORTED_TIMEFRAMES:
            if not config[coin].get(timeframe, False):
                continue
            if timeframe not in limitless_markets or timeframe not in polymarket_markets:
                continue

            limitless_client = LimitlessClient(
                api_key=api_key,
                coinslug=coinslug,
                timeframe=timeframe,
            )
            limitless_client.market = limitless_markets[timeframe]
            limitless_client.selected_timeframe = timeframe

            polymarket_client = PolymarketClient(
                coinslug=coinslug,
                timeframe=timeframe,
            )
            polymarket_client.event = polymarket_markets[timeframe]
            polymarket_client.selected_timeframe = timeframe

            detectors.append(
                ArbitrageDetector(
                    coin=coin,
                    timeframe=timeframe,
                    limitless_client=limitless_client,
                    polymarket_client=polymarket_client,
                )
            )

    return detectors


def print_opportunity(opportunity):
    limitless_prices = opportunity["limitless"]
    polymarket_prices = opportunity["polymarket"]

    print(f"coin : {opportunity['coin']} timeframe : {opportunity['timeframe']}")
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
    print(f"gap : {opportunity['gap']}")
    print(f"difference : {format_price(opportunity['difference'])}")
    print(
        "arbitrage possible : YES",
        f"(required edge: {format_price(opportunity['required_edge'])})",
    )
    print()


def main():
    config = load_config()
    detectors = build_detectors(config)
    if not detectors:
        raise SystemExit("No active enabled coin/timeframe pairs found in config.json.")

    with ThreadPoolExecutor(max_workers=len(detectors)) as executor:
        futures = [executor.submit(detector.start) for detector in detectors]
        for future in futures:
            future.result()

    try:
        for detector in detectors:
            if not detector.wait_ready(timeout=15):
                raise SystemExit(
                    f"Timed out waiting for {detector.coin} {detector.timeframe} prices."
                )

        while True:
            opportunities = []
            for detector in detectors:
                opportunity = detector.get_profitable_opportunity()
                if opportunity is not None:
                    opportunities.append(opportunity)

            opportunities.sort(key=lambda item: item["net_edge"], reverse=True)
            for opportunity in opportunities:
                print_opportunity(opportunity)

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        for detector in detectors:
            detector.close()


if __name__ == "__main__":
    main()
