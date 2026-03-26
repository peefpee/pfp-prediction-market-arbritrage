from libaries import *
import os

from libaries import limitless

limitlessclient = limitless.limitlessclient(url="https://api.limitless.exchange/markets/active", apikey=os.getenv("LIMITLESS_API_KEY") )
print(limitlessclient.find_active_rolling_market(coinslug="eth",timeframetag="Minutes 15"))