<<<<<<< HEAD
from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("limitless2.py")), run_name="__main__")
=======
import asyncio

from limitless_sdk.api import HttpClient
from limitless_sdk.markets import MarketFetcher

SIZE_SCALE = 1_000_000


def format_size(size):
    if size is None:
        return "n/a"
    return f"{float(size) / SIZE_SCALE:,.4f}"


def format_level(level):
    return f"{level.price:>7.4f} | {format_size(level.size):>12} | {level.side:<4}"


def select_market(markets):
    for market in markets:
        if "Minutes 15" in market.tags and "eth" in market.slug.lower():
            return market
    return None


def print_orderbook_snapshot(market, orderbook):
    bids = sorted(orderbook.bids, key=lambda level: level.price, reverse=True)
    asks = sorted(orderbook.asks, key=lambda level: level.price)

    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None
    token_side = "UP" if market.tokens and orderbook.token_id == market.tokens.yes else "UNKNOWN"

    print(f"\n{'=' * 72}")
    print(f"Market: {market.title}")
    print(f"Slug:   {market.slug}")
    if market.tokens:
        print(f"UP:     {market.tokens.yes}")
        print(f"DOWN:   {market.tokens.no}")
    print(f"Book:   {orderbook.token_id} [{token_side}]")
    print(
        f"Adjusted Midpoint: {orderbook.adjusted_midpoint:.4f}"
        f" | Last Trade: {orderbook.last_trade_price:.4f}"
    )
    print(
        f"Max Spread: {orderbook.max_spread}"
        f" | Min Size: {format_size(orderbook.min_size)}"
    )

    if best_bid is None and best_ask is None:
        print("No liquidity yet")
        return

    if best_bid is not None:
        print(f"Best Bid: {best_bid.price:.4f} | Size: {format_size(best_bid.size)}")
    if best_ask is not None:
        print(f"Best Ask: {best_ask.price:.4f} | Size: {format_size(best_ask.size)}")
    if best_bid is not None and best_ask is not None:
        print(f"Spread:   {best_ask.price - best_bid.price:.4f}")

    print("\nAsks")
    print(" Price  |        Tokens | Side")
    for ask in asks[:5]:
        print(format_level(ask))

    print("\nBids")
    print(" Price  |        Tokens | Side")
    for bid in bids[:5]:
        print(format_level(bid))


async def main():
    http_client = HttpClient()
    market_fetcher = MarketFetcher(http_client)

    try:
        active = await market_fetcher.get_active_markets()
        market = select_market(active.data)
        if market is None:
            raise SystemExit("No active ETH 15-minute market found.")

        market = await market_fetcher.get_market(market.slug)
        orderbook = await market_fetcher.get_orderbook(market.slug)
        print_orderbook_snapshot(market, orderbook)
    finally:
        await http_client.close()


asyncio.run(main())
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae
