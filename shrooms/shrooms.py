#Author: Max Petschack
#Stuff to fix when porting: Change sqldb local, change error image local
#THINGS TO DO: Test pi view time increment function, 
from flask import Flask, request, url_for, render_template, stream_with_context, make_response, send_file, send_from_directory
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from math import floor
import os
import re
import pytz
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import csv
import hashlib
import time
import datetime
app = Flask(__name__)
open('shrooms.db')

def getuser(session_id):
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    curs.execute('SELECT user FROM sessions WHERE id = ?',(session_id,))
    user = curs.fetchone()[0]
    conn.close()
    return user

def aest():
        time_aest = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(pytz.timezone('Australia/Melbourne'))
        time_aest = time.mktime(time_aest.timetuple())
        return time_aest

def htmldate_to_seconds(date):
    date = pytz.timezone('Australia/Melbourne').localize(datetime.datetime.strptime(date,'%Y-%m-%dT%H:%M'))
    epoch = pytz.utc.localize(datetime.datetime.fromtimestamp(0)).astimezone(pytz.timezone('Australia/Melbourne'))
    date = (date-epoch).total_seconds()
    return date

#Google verification
@app.route('/googlefa24e96c2bedf47d.html')
def verification():
    return 'google-site-verification: googlefa24e96c2bedf47d.html'

@app.route('/')
def main():
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Delete old sessions
    curs.execute('DELETE FROM sessions WHERE id < ?;',(time.time(),))
    #Check log in status
    if 'logged_in' in request.cookies and 'session_id' in request.cookies:
        if request.cookies['logged_in'] == 'true' and request.cookies['session_id'] != 'None':
            try:
                curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
            except:
                pass
            else:
                user = curs.fetchone()
                if user != None:
                    #Render page
                    user = user[0]
                    if user == 'admin':
                        curs.execute('SELECT name,id,user FROM pis ORDER BY user ASC')
                    else:
                        curs.execute('SELECT name,id,user FROM pis WHERE user = ?;',(user,))
                    pis = curs.fetchall()
                    data = {}
                    for x in pis:
                        curs.execute('SELECT temp,humidity,time FROM data WHERE pi = ?',(x[1],))
                        latest = list(curs.fetchall())
                        #deal with empty data
                        if latest == []:
                            latest = [['No data','No data','No data']]
                        #Convert unix stamp to readable string
                        for y in range(len(latest)):
                            try:
                                latest[y] = list(latest[y])
                                latest[y][2] = datetime.datetime.fromtimestamp(float(latest[y][2]))
                                latest[y][2] = pytz.utc.localize(latest[y][2]).astimezone(pytz.timezone('Australia/Melbourne'))
                                latest[y][2] = latest[y][2].strftime('%a %b %d %H:%M:%S %Y AEST')
                            except:
                                pass
                        data[x[1]] = latest[::-1]
                    conn.commit()
                    conn.close()
                    if user == 'admin':
                        return render_template('admin.html',data=data,pis=pis,user=user)
                    else:
                        return render_template('index.html',data=data,pis=pis,user=user)
    conn.commit()
    conn.close()
    return '<script>document.cookie = "session_id=None; expires=1"; window.location = "/login"</script>'

@app.route('/validate',methods=['POST'])
def login():
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    username,password = request.form['user'],request.form['pass'].encode('utf-8')
    password = hashlib.md5(password).hexdigest()
    curs.execute('SELECT * FROM users WHERE username = ? AND password = ?;',(username,password))
    user = curs.fetchone()
    if user == None:
        conn.close()
        return '<script>window.location = "/login?success=false";</script>'
    else:
        session = int(time.time()+3600)
        curs.execute('DELETE FROM sessions WHERE user = ?',(username,))
        curs.execute('INSERT INTO sessions (user,id) VALUES (?,?)',(request.form['user'],session))
        conn.commit()
        conn.close()
        return render_template('login.js',logged_in='true',session_id=session)

@app.route('/login')
def loginform():
    return render_template('login.html')

@app.route('/logout')
def logout():
    return '<script>document.cookie = "session_id=None; expires=1"; window.location = "/login"</script>'

@app.route('/newuser')
def newuser():
    return render_template('newuser.html')

@app.route('/createuser',methods=['POST'])
def createuser():
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    curs.execute('SELECT * FROM users WHERE username = ?;',(request.form['username'],))
    #Check if something was wrong with the inputs
    ##Empty strings
    if request.form['username'] == '' or request.form['pass1'] == '':
        conn.close()
        return '<script>window.location = "/newuser?fail=empty"</script>'
    ##Username taken
    elif curs.fetchone() != None:
        conn.close()
        return '<script>window.location = "/newuser?fail=taken"</script>'
    ##Passwords don't match
    elif request.form['pass1'] != request.form['pass2']:
        conn.close()
        return '<script>window.location = "/newuser?fail=diff"</script>'
    ##Password too short
    elif len(request.form['pass1']) < 7:
        conn.close()
        return '<script>window.location = "/newuser?fail=short"</script>'
    #Create user
    curs.execute('INSERT INTO users (username,password) VALUES (?,?)',(request.form['username'],hashlib.md5(request.form['pass1'].encode('utf-8')).hexdigest()))
    conn.commit()
    conn.close()
    return 'User made!<br/><a href="/login">Login</a>'

@app.route('/newpi',methods=['GET','POST'])
def new_pi():
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Delete old sessions
    curs.execute('DELETE FROM sessions WHERE id < ?;',(time.time(),))
    if request.method == 'POST':
        if 'logged_in' in request.cookies and 'session_id' in request.cookies:
            if request.cookies['logged_in'] == 'true':
                curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
                user = curs.fetchone()
                if user != None:
                    user = getuser(request.cookies['session_id'])
                    #Check inputs for faults
                    ##Key already taken
                    curs.execute('SELECT * FROM pis WHERE key = ?',(request.form['key'],))
                    if curs.fetchone() != None:
                        conn.close()
                        return '<script>window.location = "/newpi?fail=takenkey"</script>'
                    ##No key
                    if request.form['key'] == '':
                        return '<script>window.location = "/newpi?fail=nokey"</script>'
                    ##Name already taken
                    curs.execute('SELECT * FROM pis WHERE user = ? AND name = ?',(user,request.form['name']))
                    if curs.fetchone() != None:
                        conn.close()
                        return '<script>window.location = "/newpi?fail=name"</script>'
                    #Register
                    curs.execute('SELECT id FROM pis ORDER BY id DESC')
                    newid = curs.fetchone()[0]+1
                    curs.execute('INSERT INTO pis (name,user,id,key) VALUES (?,?,?,?)',(request.form['name'],user,newid,request.form['key']))
                    conn.commit()
                    conn.close()
                    return 'Pi registered!<br/><a href="/">Back to main page</a>'
        conn.close()
        return '<script>document.cookie = "session_id=None; expires=1"; window.location = "/login"</script>'
    else:
        #Check log in status
        if 'logged_in' in request.cookies and 'session_id' in request.cookies:
            if request.cookies['logged_in'] == 'true':
                curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
                user = curs.fetchone()
                if user != None:
                    conn.close()
                    return render_template('registerpi.html')
        conn.commit()
        conn.close()
        return '<script>document.cookie = "session_id=None; expires=1"; window.location = "/login"</script>'

@app.route('/monitors/<id>/changekey',methods=['POST','GET'])
def change_key(id):
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Delete old sessions
    curs.execute('DELETE FROM sessions WHERE id < ?;',(time.time(),))
    conn.commit()
    #Check if user has correct privleges
    if 'logged_in' in request.cookies and 'session_id' in request.cookies:
        if request.cookies['logged_in'] == 'true' and request.cookies['session_id'] != 'None':
            curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
            user = curs.fetchone()
            if user != None:
                user = user[0]
            curs.execute('SELECT user FROM pis WHERE id = ?',(id,))
            owner = curs.fetchone()
            if owner!= None:
                owner = owner[0]
            if user == owner or user == 'admin':
                if request.method == 'GET':
                    curs.execute('SELECT name FROM pis WHERE id = ?',(id,))
                    name = curs.fetchone()[0]
                    #Render
                    conn.close()
                    return render_template('changekey.html',id=id,name=name)
                elif request.method == 'POST':
                    #Check inputs for faults
                    ##No key
                    if request.form['newkey'] == '':
                        return '<script>window.location = "/monitors/'+id+'/changekey?fail=nokey"</script>'
                    ##Key already taken
                    curs.execute('SELECT * FROM pis WHERE key = ?',(request.form['newkey'],))
                    if curs.fetchone() != None:
                        conn.close()
                        return '<script>window.location = "/monitors/'+id+'/changekey?fail=key"</script>'
                    ##Confirm wrong
                    curs.execute('SELECT name FROM pis WHERE id = ?',(id,))
                    name = curs.fetchone()
                    if name != None:
                        if name[0] != request.form['confirm']:
                            conn.close()
                            return '<script>window.location = "/monitors/'+id+'/changekey?fail=confirm"</script>'
                    #Change key
                    curs.execute('UPDATE pis SET key = ? WHERE id = ?',(request.form['newkey'],id))
                    conn.commit()
                    conn.close()
                    return 'Key changed!<br/><a href="/">Back to main page</a>'

@app.route('/api/logger',methods=['POST'])
def log_data():
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Check for bad inputs
    ##Forgot a variable
    if 'key' not in request.form or 'temp' not in request.form or 'hum' not in request.form or 'time' not in request.form:
        conn.close()
        return 'Forgot a variable, try again'
    ##Key not registered
    curs.execute('SELECT * FROM pis WHERE key = ?',(request.form['key'],))
    if curs.fetchone() == None:
        conn.close()
        return 'Key is already taken'
    #Log data
    curs.execute('SELECT id FROM pis WHERE key = ?',(request.form['key'],))
    id = curs.fetchone()[0]
    curs.execute('INSERT INTO data (pi,temp,humidity,time) VALUES (?,?,?,?)',(id,int(request.form['temp']),int(request.form['hum']),request.form['time']))
    conn.commit()
    conn.close()
    return 'Logged!'

@app.route('/monitors/<id>',methods=['GET','POST'])
def view_pi(id):
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Delete old sessions
    curs.execute('DELETE FROM sessions WHERE id < ?;',(time.time(),))
    #Check if user has correct privleges
    if 'logged_in' in request.cookies and 'session_id' in request.cookies:
        if request.cookies['logged_in'] == 'true' and request.cookies['session_id'] != 'None':
            curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
            user = curs.fetchone()
            if user != None:
                user = user[0]
            curs.execute('SELECT user FROM pis WHERE id = ?',(id,))
            owner = curs.fetchone()
            if owner!= None:
                owner = owner[0]
            #Get data
            if user == owner or user == 'admin':
                curs.execute('SELECT * FROM data WHERE pi = ?',(id,))
                data = curs.fetchall()[::-1]
                curs.execute('SELECT * FROM pis WHERE id = ?',(id,))
                pi = curs.fetchone()
                #Filter data if requested
                timerange = 'all'
                debug = 'doot'
                if request.method == 'POST':
                    #Convert all time data to unix timestamps
                    for t in range(len(data)):
                        try:
                            data[t] = list(data[t])
                            data[t][3] = datetime.datetime.strptime(data[t][3],'%a %b %d %H:%M:%S %Y AEST')
                        except:
                            pass
                        else:
                            data[t][3] = (data[t][3]-datetime.datetime.fromtimestamp(0)).total_seconds()
                    #Filter for age
                    if 'timerange' in request.form:
                        timerange = request.form['timerange']
                        if timerange != 'all':
                            newdata = []
                            for x in data:
                                if time.time()-float(x[3]) <= int(timerange):
                                    newdata.append(x)
                            data = newdata
                    else:
                        timerange = None
                    newdata = list(data)
                    #Filter by inc
                    inc = None
                    if 'inc' in request.form:
                        if request.form['inc'] != 'all':
                            inc = int(request.form['inc'])
                            newdata = []
                            for t in data:
                                timest = int(float(t[3]))
                                if (timest-(timest%60))%inc == 0:
                                    newdata.append(list(t))
                            data = list(newdata)
                else:
                    timerange,inc = None,None
                #Convert unix stamp to readable string
                for y in range(len(data)):
                    try:
                        data[y] = list(data[y])
                        data[y][3] = datetime.datetime.fromtimestamp(float(data[y][3]))
                        data[y][3] = pytz.utc.localize(data[y][3]).astimezone(pytz.timezone('Australia/Melbourne'))
                        data[y][3] = data[y][3].strftime('%a %b %d %H:%M:%S %Y AEST')
                    except:
                        pass
                conn.close()
                return render_template('pi_view.html',pi=pi,data=data,timerange=timerange,inc=str(inc))
    conn.close()
    return 'You have insufficent privileges to view this monitor<br/><a href="/">Back to main page</a>'

@app.route('/monitors/<id>/graphs')
def graph_maker(id):
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Check if user has correct privileges
    if 'logged_in' in request.cookies and 'session_id' in request.cookies:
        if request.cookies['logged_in'] == 'true' and request.cookies['session_id'] != 'None':
            curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
            user = curs.fetchone()
            if user != None:
                user = user[0]
            curs.execute('SELECT user FROM pis WHERE id = ?',(id,))
            owner = curs.fetchone()
            if owner != None:
                owner = owner[0]
            else:
                conn.close()
                return 'Selected monitor does not exist'
            if user == owner or user == 'admin':
                curs.execute('SELECT name FROM pis WHERE id = ?',(id,))
                name = curs.fetchone()[0]
                #Render
                conn.close()
                return render_template('graphview.html',id=id,name=name)
    conn.close()
    return 'You have insufficent privileges to view this data<br/><a href="/">Back to main page</a>'

@app.route('/monitors/<id>/graphgen')
def gen_graph(id):
    timerange_lookup = {'60':'Minutes','3600':'Hours','86400':'Days','604800':'Weeks','2678400':'Months','31557600':'Years'}
    #Get variables
    try:
        graph_type = request.args['type']
        start = htmldate_to_seconds(request.args['start'])
        end = htmldate_to_seconds(request.args['end'])
        timerange = int(request.args['timerange'])
    except ValueError:
        return 'Something went wrong, please try again'
    #Make graph
    if graph_type not in ['temp','humidity'] or str(timerange) not in timerange_lookup:
        return 'Invalid graph settings<br/><a href="/">Back to main page</a>'
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Check if user has correct privileges
    if 'logged_in' in request.cookies and 'session_id' in request.cookies:
        if request.cookies['logged_in'] == 'true' and request.cookies['session_id'] != 'None':
            curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
            user = curs.fetchone()
            if user != None:
                user = user[0]
            curs.execute('SELECT user FROM pis WHERE id = ?',(id,))
            owner = curs.fetchone()
            if owner!= None:
                owner = owner[0]
            #Get data
            if user == owner or user == 'admin':
                #Get data
                if graph_type == 'temp':
                    curs.execute('SELECT temp,time FROM data WHERE pi = ?;',(id,))
                elif graph_type == 'humidity':
                    curs.execute('SELECT humidity,time FROM data WHERE pi = ?;',(id,))
                else:
                    conn.close()
                    return 'Something went wrong, please try again'
                data = curs.fetchall()
                #Convert data to timestamps
                for t in range(len(data)):
                    try:
                        data[t] = list(data[t])
                        data[t][1] = datetime.datetime.strptime(data[t][1],'%a %b %d %H:%M:%S %Y AEST')
                        data[t][1] = pytz.utc.localize(data[t][1]).astimezone(pytz.timezone('Australia/Melbourne'))
                    except:
                        pass
                    else:
                        epoch = pytz.utc.localize(datetime.datetime.fromtimestamp(0)).astimezone(pytz.timezone('Australia/Melbourne'))
                        data[t][1] = (data[t][1]-epoch).total_seconds()
                #Filter
                newdata = []
                data = data[::-1]
                for x in range(int((end-start)/timerange)):
                    found = False
                    for t in data:
                        if int(floor((end-float(t[1]))/timerange)) == x:
                            found = True
                            newdata.append(t[0])
                            break
                    if found == False:
                        newdata.append(None)
                #Check if data exists
                empty = True
                for x in newdata:
                    if x != None:
                        empty = False
                        break
                    else:
                        empty = True
                if empty:
                    conn.close()
                    return send_file(app.root_path+'\static\errornodata.png')
                #Deal with gaps in data
                fixed = []
                for x in range(len(newdata)):
                    if newdata[x] == None:
                        try:
                            neighbours = [newdata[x-1],newdata[x+1]]
                        except IndexError:
                            fixed.append(None)
                            continue
                        else:
                            if neighbours != [None,None]:
                                if None not in neighbours:
                                    fixed.append((neighbours[0]+neighbours[1])/2.0)
                                else:
                                    neighbours.pop(neighbours.index(None))
                                    fixed.append(neighbours[0])
                            else:
                                fixed.append(None)
                    else:
                        fixed.append(newdata[x])
                data = list(fixed)
                nononedata = [x for x in data if x != None]
                if nononedata == []:
                    nononedata = [0]
                #Make graph
                fig = Figure()
                axis = fig.add_subplot(1, 1, 1)
                ys = np.array(data[::-1])
                xs = np.array(range(int((end-start)/timerange)))
                axis.set_xlim(0,(end-start)/timerange)
                if min(nononedata) < 0:
                    axis.set_ylim(ymin=min(nononedata))
                else:
                    axis.set_ylim(ymin=0)
                axis.set_xlabel(timerange_lookup[str(timerange)]+' since start')
                #Get ylabel
                if graph_type == 'temp':
                    axis.set_ylabel('Degrees celsius')
                elif graph_type == 'humidity':
                    axis.set_ylabel('Humidity percentage')
                else:
                    axis.set_ylabel('?')
                axis.set_xticks(range(int((end-start)/timerange)),10)
                yticks = range(0,110,10) if min(nononedata) > 0 else range(min(nononedata),110,10)
                axis.set_yticks(yticks)
                axis.plot(xs, ys)
                #Get title
                if graph_type == 'temp':
                    fig.suptitle('Temperature over time')
                elif graph_type == 'humidity':
                    fig.suptitle('Humidity over time')
                else:
                    fig.suptitle('Unknown graph type')
                canvas = FigureCanvas(fig)
                output = StringIO()
                canvas.print_png(output)
                response = make_response(output.getvalue())
                response.mimetype = 'image/png'
                conn.close()
                return response
    conn.close()
    return 'You have insufficent privileges to view this data<br/><a href="/">Back to main page</a>'

@app.route('/download_data/<id>')
def download_data(id):
    conn = sqlite3.connect('shrooms.db')
    curs = conn.cursor()
    #Check if user has correct privleges
    if 'logged_in' in request.cookies and 'session_id' in request.cookies:
        if request.cookies['logged_in'] == 'true' and request.cookies['session_id'] != 'None':
            curs.execute('SELECT * FROM sessions WHERE id = ?;',(float(request.cookies['session_id']),))
            user = curs.fetchone()
            if user != None:
                user = user[0]
            curs.execute('SELECT user FROM pis WHERE id = ?',(id,))
            owner = curs.fetchone()
            if owner!= None:
                owner = owner[0]
            if user == owner or user == 'admin':
                def generate():
                    data = StringIO()
                    w = csv.writer(data)

                    # write header
                    w.writerow(('Temperature', 'Humidity', 'C02', 'Light', 'Timestamp'))
                    yield data.getvalue()
                    data.seek(0)
                    data.truncate(0)
                    curs.execute('SELECT temp,humidity,time FROM data WHERE pi = ?',(id,))
                    pi_data = curs.fetchall()
                    # write each log item
                    for item in pi_data:
                        w.writerow((
                            item[0],
                            item[1],
                            'Not connected',
                            'Not connected',
                            item[2]
                        ))
                        yield data.getvalue()
                        data.seek(0)
                        data.truncate(0)

                # add a filename
                headers = Headers()
                headers.set('Content-Disposition', 'attachment', filename='data.csv')

                # stream the response as the data is generated
                return Response(
                    stream_with_context(generate()),
                    mimetype='text/csv', headers=headers
                )
    conn.close()
    return 'You have insufficent privileges to view this data<br/><a href="/">Back to main page</a>'
