import json
import threading
from copy import deepcopy
from decimal import Decimal

import requests
import websocket

EVENT_SLUG_URL_PREFIX = "https://gamma-api.polymarket.com/events/slug/"
MARKET_URL_PREFIX = "https://polymarket.com/event/"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
PING_INTERVAL_SECONDS = 3
TIMEFRAME_LABELS = {
    "m15": {"15m"},
    "hourly": {"1h", "hourly"},
    "daily": {"1d", "daily"},
    "weekly": {"1w", "weekly"},
    "monthly": {"1m", "monthly"},
}


class PolymarketClient:
    def __init__(
        self,
        *,
        event_slug=None,
        ping_interval_seconds=PING_INTERVAL_SECONDS,
    ):
        self.event_slug = event_slug
        self.ping_interval_seconds = ping_interval_seconds

        self.event = None
        self.coin = None
        self.market = None
        self.slug = None
        self.asset_ids = []
        self.raw_outcomes = []
        self.selected_timeframe = None

        self._latest_prices = None
        self._lock = threading.Lock()
        self._prices_event = threading.Event()
        self._thread = None
        self._stop_heartbeats = threading.Event()
        self._heartbeat_thread = None

        self.ws = None

    def fetch_event(self, slug=None):
        event_slug = slug or self.event_slug
        if not event_slug:
            raise SystemExit("A Polymarket event slug is required.")

        response = requests.get(f"{EVENT_SLUG_URL_PREFIX}{event_slug}", timeout=15)
        response.raise_for_status()
        return response.json()

    def connect(self):
        if self.event is None:
            self.event = self.fetch_event()

        self.market = (self.event.get("markets") or [None])[0]
        if not self.market:
            raise SystemExit("Active Polymarket event is missing market data.")

        self.slug = self.event.get("slug")
        self.coin = self._event_coin(self.event)
        self.raw_outcomes = self._parse_json_field(self.market.get("outcomes")) or []
        self.asset_ids = self._parse_json_field(self.market.get("clobTokenIds")) or []
        if len(self.asset_ids) < 2:
            raise SystemExit("Active Polymarket market is missing both token IDs.")
        if self.selected_timeframe is None:
            self.selected_timeframe = self._event_timeframe(self.event)

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        self.ws = websocket.WebSocketApp(
            WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.ws.run_forever()

    def _on_open(self, ws):
        payload = {
            "assets_ids": self.asset_ids,
            "type": "market",
            "custom_feature_enabled": True,
        }
        ws.send(json.dumps(payload))

        self._stop_heartbeats.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._send_heartbeats,
            args=(ws,),
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _on_message(self, ws, raw_message):
        del ws

        if raw_message == "PONG":
            return

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        if isinstance(message, list):
            for item in message:
                self._handle_message(item)
            return

        self._handle_message(message)

    def _on_error(self, ws, error):
        del ws
        print("Polymarket websocket error:", error)

    def _on_close(self, ws, close_status_code, close_msg):
        del ws
        del close_status_code
        del close_msg
        self._stop_heartbeats.set()

    def _handle_message(self, message):
        if not isinstance(message, dict):
            return

        event_type = message.get("event_type")

        if "bids" in message and "asks" in message and "asset_id" in message:
            self._update_asset_prices(
                asset_id=message["asset_id"],
                bid=self._best_price(message.get("bids", []), reverse=True),
                ask=self._best_price(message.get("asks", [])),
                timestamp=message.get("timestamp"),
            )
            return

        if event_type == "best_bid_ask":
            self._update_asset_prices(
                asset_id=message.get("asset_id"),
                bid=self._parse_decimal(message.get("best_bid")),
                ask=self._parse_decimal(message.get("best_ask")),
                timestamp=message.get("timestamp"),
            )
            return

        if event_type == "price_change":
            for price_change in message.get("price_changes", []):
                self._update_asset_prices(
                    asset_id=price_change.get("asset_id"),
                    bid=self._parse_decimal(price_change.get("best_bid")),
                    ask=self._parse_decimal(price_change.get("best_ask")),
                    timestamp=message.get("timestamp"),
                )

    def _update_asset_prices(self, *, asset_id, bid, ask, timestamp):
        if asset_id not in self.asset_ids:
            return

        with self._lock:
            if self._latest_prices is None:
                self._latest_prices = {
                    "venue": "polymarket",
                    "coin": self.coin,
                    "market_slug": self.slug,
                    "market_url": f"{MARKET_URL_PREFIX}{self.slug}",
                    "timestamp": timestamp,
                    "timeframe": self.selected_timeframe,
                    # Normalize the first and second binary outcomes for comparison.
                    "yes": {"bid": None, "ask": None},
                    "no": {"bid": None, "ask": None},
                    "raw_outcomes": list(self.raw_outcomes),
                }

            side = "yes" if asset_id == self.asset_ids[0] else "no"
            self._latest_prices["timestamp"] = timestamp
            self._latest_prices["timeframe"] = self.selected_timeframe
            self._latest_prices["market_url"] = f"{MARKET_URL_PREFIX}{self.slug}"
            self._latest_prices[side] = {"bid": bid, "ask": ask}

        self._prices_event.set()

    def _send_heartbeats(self, ws):
        while not self._stop_heartbeats.wait(self.ping_interval_seconds):
            try:
                if ws.sock and ws.sock.connected:
                    ws.send("PING")
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                print("Polymarket heartbeat failed:", exc)
                return

    def wait_for_prices(self, timeout=None):
        return self._prices_event.wait(timeout)

    def get_latest_prices(self):
        with self._lock:
            if self._latest_prices is None:
                return None
            return deepcopy(self._latest_prices)

    def close(self):
        self._stop_heartbeats.set()

        if self.ws is not None:
            self.ws.close()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)

        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2)

    @staticmethod
    def _parse_json_field(value):
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _parse_decimal(value):
        if value is None:
            return None
        return Decimal(str(value))

    @classmethod
    def _best_price(cls, levels, *, reverse=False):
        prices = []

        for level in levels:
            price = cls._parse_decimal(level.get("price"))
            size = cls._parse_decimal(level.get("size"))
            if price is None or size is None or size <= 0:
                continue
            prices.append(price)

        if not prices:
            return None

        return max(prices) if reverse else min(prices)

    @classmethod
    def _event_timeframe(cls, event):
        labels = {
            str(tag.get("label") or "").strip().lower()
            for tag in event.get("tags", [])
        }

        for timeframe, aliases in TIMEFRAME_LABELS.items():
            if labels & aliases:
                return timeframe

        slug = event.get("slug", "").lower()
        if "-15m-" in slug:
            return "m15"
        if "-1h-" in slug:
            return "hourly"
        if "-1d-" in slug or "-daily-" in slug:
            return "daily"
        if "-1w-" in slug or "-weekly-" in slug:
            return "weekly"
        if "-1m-" in slug or "-monthly-" in slug:
            return "monthly"

        return None

    @classmethod
    def _event_coin(cls, event):
        return cls._slug_coin(event.get("slug", ""))

    @staticmethod
    def _slug_coin(slug):
        base = str(slug).strip().split("-", 1)[0].lower()
        aliases = {
            "bitcoin": "BTC",
            "btc": "BTC",
            "ethereum": "ETH",
            "eth": "ETH",
            "solana": "SOL",
            "sol": "SOL",
            "ripple": "XRP",
            "xrp": "XRP",
        }
        return aliases.get(base, base.upper() if base else "UNKNOWN")


polymarketclient = PolymarketClient
