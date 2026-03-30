import threading
from copy import deepcopy
from decimal import Decimal

import requests
import socketio

WS_URL = "wss://ws.limitless.exchange"
NAMESPACE = "/markets"
<<<<<<< HEAD
MARKET_API_URL_PREFIX = "https://api.limitless.exchange/markets/"
MARKET_URL_PREFIX = "https://limitless.exchange/markets/"
=======
ACTIVE_MARKETS_URL = "https://api.limitless.exchange/markets/active"
MARKET_URL_PREFIX = "https://limitless.exchange/markets/"
SUPPORTED_TIMEFRAMES = ("m15", "hourly", "daily", "weekly", "monthly")
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae
TIMEFRAME_TAGS = {
    "m15": {"minutes 15", "15m", "15 min", "15 minute", "15 minutes"},
    "hourly": {"hourly", "1h", "1 hour", "60m"},
    "daily": {"daily", "1d", "1 day"},
    "weekly": {"weekly", "1w", "1 week"},
    "monthly": {"monthly", "1m", "1 month"},
}


class LimitlessClient:
    def __init__(
        self,
        *,
        api_key=None,
<<<<<<< HEAD
        market_slug=None,
    ):
        self.api_key = api_key
        self.market_slug = market_slug

        self.market = None
        self.coin = None
=======
        coinslug="eth",
        timeframe="auto",
        active_markets_url=ACTIVE_MARKETS_URL,
    ):
        self.api_key = api_key
        self.coinslug = coinslug
        self.timeframe = timeframe
        self.active_markets_url = active_markets_url

        self.market = None
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae
        self.slug = None
        self.tokens = None
        self.selected_timeframe = None

        self._latest_prices = None
        self._lock = threading.Lock()
        self._prices_event = threading.Event()
        self._thread = None

        self.sio = socketio.Client(reconnection=True)
        self.sio.on("connect", self._on_connect, namespace=NAMESPACE)
        self.sio.on("disconnect", self._on_disconnect, namespace=NAMESPACE)
        self.sio.on("exception", self._on_exception, namespace=NAMESPACE)
        self.sio.on("orderbookUpdate", self._on_orderbook, namespace=NAMESPACE)

<<<<<<< HEAD
    def fetch_market(self, slug=None):
        market_slug = slug or self.market_slug
        if not market_slug:
            raise SystemExit("A Limitless market slug is required.")

        response = requests.get(f"{MARKET_API_URL_PREFIX}{market_slug}", timeout=15)
=======
    def list_active_markets(self):
        response = requests.get(self.active_markets_url, timeout=15)
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae
        response.raise_for_status()
        return response.json()

<<<<<<< HEAD
    def connect(self):
        if self.market is None:
            self.market = self.fetch_market()

        self.slug = self.market["slug"]
        self.coin = self._market_coin(self.market)
        self.tokens = [self.market["tokens"]["yes"], self.market["tokens"]["no"]]
        if self.selected_timeframe is None:
            self.selected_timeframe = self._market_timeframe(self.market)
=======
        markets_by_timeframe = {}
        for market in response.json()["data"]:
            if self.coinslug.lower() not in market.get("slug", "").lower():
                continue

            timeframe = self._market_timeframe(market)
            if timeframe is None or timeframe in markets_by_timeframe:
                continue

            markets_by_timeframe[timeframe] = market

        return markets_by_timeframe

    def find_active_market(self):
        markets_by_timeframe = self.list_active_markets()
        requested_timeframe = self._normalize_requested_timeframe(self.timeframe)

        if requested_timeframe == "auto":
            for timeframe in SUPPORTED_TIMEFRAMES:
                market = markets_by_timeframe.get(timeframe)
                if market is not None:
                    return timeframe, market
        else:
            market = markets_by_timeframe.get(requested_timeframe)
            if market is not None:
                return requested_timeframe, market

        raise SystemExit("No active market found with the specified tags.")

    def connect(self):
        if self.market is None:
            self.selected_timeframe, self.market = self.find_active_market()
        elif self.selected_timeframe is None:
            self.selected_timeframe = self._normalize_requested_timeframe(self.timeframe)

        self.slug = self.market["slug"]
        self.tokens = [self.market["tokens"]["yes"], self.market["tokens"]["no"]]
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        headers = {"X-API-Key": self.api_key} if self.api_key else None
        self.sio.connect(
            WS_URL,
            transports=["websocket"],
            namespaces=[NAMESPACE],
            headers=headers,
        )
        self.sio.wait()

    def _on_connect(self):
        payload = {"marketSlugs": [self.slug]}
        self.sio.emit("subscribe_market_prices", payload, namespace=NAMESPACE)

    def _on_disconnect(self):
        return None

    def _on_exception(self, data):
        print("Limitless exception:", data)

    def _on_orderbook(self, data):
        prices = self._parse_orderbook(data)
        if prices is None:
            return

        with self._lock:
            self._latest_prices = prices
        self._prices_event.set()

    def _parse_orderbook(self, data):
        orderbook = data.get("orderbook", {})
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])

        yes_bid = self._best_price(bids, reverse=True)
        yes_ask = self._best_price(asks)

        return {
            "venue": "limitless",
<<<<<<< HEAD
            "coin": self.coin,
=======
            "coin": self.coinslug.upper(),
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae
            "market_slug": data.get("marketSlug", self.slug),
            "market_url": f"{MARKET_URL_PREFIX}{data.get('marketSlug', self.slug)}",
            "timestamp": data.get("timestamp"),
            "timeframe": self.selected_timeframe,
            "yes": {
                "bid": yes_bid,
                "ask": yes_ask,
            },
            # Limitless sends the orderbook from the YES token perspective only.
            "no": {
                "bid": self._invert_price(yes_ask),
                "ask": self._invert_price(yes_bid),
            },
        }

    def wait_for_prices(self, timeout=None):
        return self._prices_event.wait(timeout)

    def get_latest_prices(self):
        with self._lock:
            if self._latest_prices is None:
                return None
            return deepcopy(self._latest_prices)

    def close(self):
        if self.sio.connected:
            self.sio.disconnect()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)

    @staticmethod
    def _best_price(levels, *, reverse=False):
        prices = [
            Decimal(str(level["price"]))
            for level in levels
            if level.get("price") is not None
        ]
        if not prices:
            return None
        return max(prices) if reverse else min(prices)

    @staticmethod
    def _invert_price(price):
        if price is None:
            return None
        return Decimal("1") - price

    @classmethod
<<<<<<< HEAD
    def _market_coin(cls, market):
        return cls._slug_coin(market.get("slug", ""))

    @staticmethod
    def _slug_coin(slug):
        base = str(slug).strip().split("-", 1)[0].lower()
        if base in {"btc", "eth", "sol", "xrp"}:
            return base.upper()
        return base.upper() if base else "UNKNOWN"
=======
    def _normalize_requested_timeframe(cls, timeframe):
        if timeframe is None:
            return "auto"

        normalized = str(timeframe).strip().lower()
        aliases = {
            "15m": "m15",
            "m15": "m15",
            "hourly": "hourly",
            "1h": "hourly",
            "daily": "daily",
            "1d": "daily",
            "weekly": "weekly",
            "1w": "weekly",
            "monthly": "monthly",
            "1m": "monthly",
            "auto": "auto",
        }
        return aliases.get(normalized, normalized)
>>>>>>> e19d88b8104a00cf8d3d4e251a434bad006b37ae

    @classmethod
    def _market_timeframe(cls, market):
        tags = {str(tag).strip().lower() for tag in market.get("tags", [])}

        for timeframe, aliases in TIMEFRAME_TAGS.items():
            if tags & aliases:
                return timeframe

        return None


limitlessclient = LimitlessClient
