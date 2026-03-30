import requests
class limitlessclient:
    def __init__(self,apikey=None,symbol=None,timeframe=None):
        self.categories = {"m15" : "15 min","h1":"Hourly"}
        self.api_key=apikey
        self.symbol=symbol
        if timeframe is not None and timeframe not in self.categories:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported timeframes are: {', '.join(self.categories.keys())}")
        else:
            self.timeframe = self.categories.get(timeframe, "auto")
        self.base_url="https://api.limitless.exchange"
    def get_slug(self):
        if self.symbol is None and self.timeframe is None:
            raise ValueError("Symbol and timeframe must be provided.")
        response = requests.get(f"{self.base_url}/markets/active")
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch active markets: {response.status_code} {response.text}")
        for market in response.json().get("data", []):
            if "eth" in market["slug"] or "ethereum" in market["slug"]:
                if self.timeframe in market["slug"]:
                    return market["slug"]
        raise ValueError(f"No active market found for symbol {self.symbol} and timeframe {self.timeframe}.")