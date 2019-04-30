import requests
import Adafruit_DHT
import time
import settings
import pytz
import datetime

def average(data):
        return int(sum(data)/len(data))

def aest():
        time_aest = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(pytz.timezone('Australia/Melbourne'))
        time_aest = time.mktime(time_aest.timetuple())
        return str(time_aest)

while True:
        temp = []
        hum = []
        for x in range(6):
                data = Adafruit_DHT.read_retry(11,4)
		print 'Read data!'
                temp.append(data[1])
                hum.append(data[0])
                time.sleep(10)
        temp,hum = average(temp),average(hum)
        print {'temp':temp,'hum':hum,'time':aest(),'licence':settings.licence}
        requests.post('http://'+settings.host+'/api/logger',data={'temp':temp,'hum':hum,'time':aest(),'key':settings.licence})
        print 'Sent data!'
