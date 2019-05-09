import requests
import Adafruit_DHT
import time
import settings
import pytz
import datetime

def til_interval(timestamp,interv):
        return interv-(timestamp%interv)

def average(data):
        return int(sum(data)/len(data))

def utc():
        time_utc = pytz.utc.localize(datetime.datetime.utcnow())                                                                           z.timezone('Australia/Melbourne'))
        time_utc = time.mktime(time_utc.timetuple())
        return str(time_utc)

while True:
        temp = []
        hum = []
        for x in range(6):
                data = Adafruit_DHT.read_retry(11,4)
                print('Read data!',data)
                temp.append(data[1])
                hum.append(data[0])
                time.sleep(til_interval(int(float(utc())),10))
        fintime = int(float(utc()))
        fintime -= fintime%60
        fintime = str(fintime)
        temp,hum = average(temp),average(hum)
        print({'temp':temp,'hum':hum,'time':fintime,'licence':settings.licence})
        requests.post('http://'+settings.host+'/api/logger',data={'temp':temp,'h                                                                             um':hum,'time':fintime,'key':settings.licence})
        print('Sent data!')
