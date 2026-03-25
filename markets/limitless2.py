import os
import requests
import socketio

API_KEY = os.getenv("LIMITLESS_API_KEY")  # rotate your exposed key
WS_URL = "wss://ws.limitless.exchange"
NAMESPACE = "/markets"

# --- find one active ETH 15-min market ---
url = "https://api.limitless.exchange/markets/active"
response = requests.get(url, timeout=15)
response.raise_for_status()

market = None
for m in response.json()["data"]:
    if "Minutes 15" in m.get("tags", []) and "eth" in m.get("slug", ""):
        market = m
        break

if not market:
    raise SystemExit("No active market found with the specified tags.")

slug = market["slug"]
print("Using slug:", slug)

# --- socket client with debug logging ---
sio = socketio.Client(reconnection=True)

def print_orderbook(data):
    orderbook = data.get("orderbook", {})
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])

    # Best prices
    best_bid = float(bids[0]["price"]) if bids else None
    best_ask = float(asks[0]["price"]) if asks else None

    if best_bid is None or best_ask is None:
        print("No liquidity yet")
        return

    # UP = YES side (as given)
    up_best_ask = best_ask
    up_best_bid = best_bid

    # DOWN = NO side (complement)
    down_best_ask = round(1 - up_best_bid, 4)
    down_best_bid = round(1 - up_best_ask, 4)

    print(f"UP   : Best Ask : {up_best_ask:.2f} | Best Bid : {up_best_bid:.2f}")
    print(f"DOWN : Best Ask : {down_best_ask:.2f} | Best Bid : {down_best_bid:.2f}")



@sio.event(namespace=NAMESPACE)
def connect():
    print(f"Connected to {NAMESPACE}")
    payload = {"marketSlugs": [slug]}
    print("Emitting subscribe_market_prices:", payload)
    sio.emit("subscribe_market_prices", payload, namespace=NAMESPACE)

@sio.event(namespace=NAMESPACE)
def disconnect():
    print("Disconnected from /markets")

@sio.on("system", namespace=NAMESPACE) # pyright: ignore[reportOptionalCall]
def on_system(data):
    pass

@sio.on("authenticated", namespace=NAMESPACE) # pyright: ignore[reportOptionalCall]
def on_authenticated(data):
    pass

@sio.on("exception", namespace=NAMESPACE) # pyright: ignore[reportOptionalCall]
def on_exception(data):
    pass

@sio.on("orderbookUpdate", namespace=NAMESPACE) # pyright: ignore[reportOptionalCall]
def on_orderbook(data):
    print_orderbook(data)

# optional: if you also want AMM price events, you'd subscribe with marketAddresses


headers = {"X-API-Key": API_KEY} if API_KEY else None

sio.connect(
    WS_URL,
    transports=["websocket"],
    namespaces=[NAMESPACE],
    headers=headers,
)

sio.wait()