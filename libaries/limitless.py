import requests
import json
import socketio

class limitlessclient:
    def __init__(self, url, apikey=None):
        self.url = url
        self.apikey = apikey
        self.sio = socketio.Client(reconnection=True)
    def find_active_rolling_market(self,coinslug,timeframetag):
        url = "https://api.limitless.exchange/markets/active"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        market = None
        for m in response.json()["data"]:
            if timeframetag in m.get("tags", []) and coinslug in m.get("slug", ""):
                market = m
                break

        if not market:
            raise SystemExit("No active market found with the specified tags.")
        return market["slug"]
    
    def parse_orderbook(self, data,mode=1):
        orderbook = data.get("orderbook", {})  
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        # Mode 1 - Best bid/ask price
        if mode == 1:
            # Best prices
            best_bid = float(bids[0]["price"]) if bids else None
            best_ask = float(asks[0]["price"]) if asks else None

            if best_bid is None or best_ask is None:
                print("No liquidity yet")
                return

            up_best_ask = best_ask
            up_best_bid = best_bid
            down_best_ask = round(1 - up_best_bid, 4)
            down_best_bid = round(1 - up_best_ask, 4)

            print(f"UP   : Best Ask : {up_best_ask:.2f} | Best Bid : {up_best_bid:.2f}")
            print(f"DOWN : Best Ask : {down_best_ask:.2f} | Best Bid : {down_best_bid:.2f}")