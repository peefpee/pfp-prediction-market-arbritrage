import limitless
l = limitless.limitlessclient(apikey="xxx",symbol="eth",timeframe="m15")
print(l.get_slug())