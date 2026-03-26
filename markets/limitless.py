import requests
import time
import socketio
import os
url = "https://api.limitless.exchange/markets/active"
apikey= "lmts_Spe3xciKBUdmClYO_qY8lL9HmHdiMg815QNLh0KEetwOUCabyFNPE9NoK5vc"
response = requests.get(url)
market = None
r = response.json()
for m in r["data"]:
    if "Minutes 15" in m["tags"] and "eth" in m["slug"]  :
        market = m
if not market:
    exit("No active market found with the specified tags.")
print(market)
tokens = market["tokens"]
tokens = {
    "yes": tokens["yes"],
    "no": tokens["no"]
}
slug = market["slug"]
sio = socketio.Client()
def print_orderbook(data, token_side='yes'):
    orderbook = data.get('orderbook', {})
    timestamp = data.get('timestamp', '')

    bids = orderbook.get('bids', [])
    asks = orderbook.get('asks', [])

    # Print raw first time so we can see the actual structure
    print("RAW SAMPLE:", bids[:1], asks[:1])

    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None

    print(f"\n{'='*40}")
    print(f"Market: {data.get('marketSlug')}  [{token_side.upper()} token]")
    print(f"Time:   {timestamp}")
    print(f"{'='*40}")

    if best_bid:
        print(f"Best Bid: {best_bid.get('price')}  (size: {best_bid.get('size')})")
    if best_ask:
        print(f"Best Ask: {best_ask.get('price')}  (size: {best_ask.get('size')})")

    print(f"\n{'--- Asks ---':>20}")
    for ask in reversed(asks[:10]):
        print(f"  {ask.get('price'):>10}  |  {ask.get('size')}")

    print(f"{'--- Bids ---':>20}")
    for bid in bids[:10]:
        print(f"  {bid.get('price'):>10}  |  {bid.get('size')}")




@sio.event
def connect():
    print(f"Connected! Subscribing to {slug}...")
    sio.emit('subscribe_market_prices', {
        'marketSlugs': [slug]
    })



@sio.event
def disconnect():
    print("Disconnected.")




def on_orderbook(data):
    print("updating orderbook...")
    print_orderbook(data, token_side='yes')


sio.on('orderbookUpdate', on_orderbook)


sio.connect(
    'wss://ws.limitless.exchange/markets',
    transports=['websocket'],
    headers={'X-API-Key': apikey}
)
sio.wait() 



#if market:
#        print(f"Market: {market['slug']} RELOADING")
#        url = f"https://api.limitless.exchange/markets/{market['slug']}/orderbook"
#    
#        response = requests.get(url)
#        print(response.json())
#        for i in response.json()["asks"]:
#            print(f"ask price: {i['price']} size: {i['size']}")

