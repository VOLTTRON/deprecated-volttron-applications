import time
import urllib2
import json

def get_forecast_temp_10day():
    retRows = []
    url = "http://api.wunderground.com/api/e136063baaea177f/hourly10day/q/WA/Richland.json"
    f = urllib2.urlopen(url)
    json_string = f.read()
    parsed_json = json.loads(json_string)
    records = parsed_json["hourly_forecast"]
    for rec in records:
        ts = float(rec["FCTTIME"]["epoch"])
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
        temp = float(rec["temp"]["english"])
        retRows.append((ts, temp))
    f.close()
    return retRows


if __name__ == '__main__':
    retRows = get_forecast_temp_10day()
    for row in retRows:
        print("Results %s: %s" % (row[0], row[1]))
