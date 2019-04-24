#
# SENSE Network Resource Manager (SENSE-NRM) Copyright (c) 2018-2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy).  All rights reserved.
#
# If you have questions about your rights to use or distribute this
# software, please contact Berkeley Lab's Innovation & Partnerships
# Office at IPO@lbl.gov.
#
# NOTICE.  This Software was developed under funding from the
# U.S. Department of Energy and the U.S. Government consequently retains
# certain rights. As such, the U.S. Government has been granted for
# itself and others acting on its behalf a paid-up, nonexclusive,
# irrevocable, worldwide license in the Software to reproduce,
# distribute copies to the public, prepare derivative works, and perform
# publicly and display publicly, and to permit other to do so.
#
# Fri Apr 12 10:13:23 PDT 2019
# sdmsupport@lbl.gov
#

import re
import os
import time
import uuid
import urllib3
import httplib
import logging
import json
import sys
import argparse
import fileinput
from urlparse import urlparse
import requests
import ssl
from wsgiref.handlers import format_date_time
from time import mktime
from datetime import tzinfo, timedelta, datetime
import pytz
import dateutil.parser
import base64
import gzip
import zlib
import enum 

from  sensenrm_config import oscars_config, nrm_config, log_config
import sensenrm_db

'''
Example responses
{
  "netlab-mx960-rt2:xe-0/0/0" : {
    "vlanRanges" : [ {
      "floor" : 2004,
      "ceiling" : 2004
    }, {
      "floor" : 2006,
      "ceiling" : 2900
    } ],
    "vlanExpression" : "2004,2006:2900",
    "ingressBandwidth" : 8900,
    "egressBandwidth" : 8900
  },
  "netlab-7750sr12-rt1:9/1/3" : {
    "vlanRanges" : [ ],
    "vlanExpression" : "",
    "ingressBandwidth" : 10000,
    "egressBandwidth" : 10000
  }
}
'''

urllib3.disable_warnings(urllib3.exceptions.SubjectAltNameWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
debug=True
if not sensenrm_db.initDone:
    sensenrm_db.initialize_db()
mydb_session = sensenrm_db.db_session

tZERO = timedelta(0)
class UTC(tzinfo):
  def utcoffset(self, dt):
    return tZERO
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return tZERO
utc = UTC()

def get_unixtime(delay_days):
    mytime1=datetime.now()
    if delay_days == 0:
        mytime11=time.mktime(mytime1.timetuple())
    else:
        from datetime import date
        today = date.fromtimestamp(time.time())
        newday = mytime1.day+delay_days
        newmonth = mytime1.month
        daycomp = 30
        if (mytime1.month == 2):
            daycomp = 28 
        if (mytime1.day+delay_days > daycomp):
            newday = mytime1.day+delay_days - daycomp
            newmonth = mytime1.month + 1
        mytime2=datetime(mytime1.year, newmonth, newday, mytime1.hour, mytime1.minute, mytime1.second, tzinfo=utc)
        mytime11=time.mktime(mytime2.timetuple())
    return mytime11

def get_delayed_time(delay_days):
    mytime1=datetime.now()
    mytime11=mytime1
    if delay_days != 0:
        import time
        from datetime import date
        today = date.fromtimestamp(time.time())
        newday = mytime1.day+delay_days
        newmonth = mytime1.month
        daycomp = 30
        if (mytime1.month == 2):
            daycomp = 28 
        if (mytime1.day+delay_days > daycomp):
            newday = mytime1.day+delay_days - daycomp
            newmonth = mytime1.month + 1
        mytime2=datetime(mytime1.year, newmonth, newday, mytime1.hour, mytime1.minute, mytime1.second, tzinfo=utc)
        mytime11 = mytime2
    return mytime11

def get_datetime_str(unixtime):
    fmt_datetime=datetime.fromtimestamp(float(str(unixtime))).strftime('%Y-%m-%d %H:%M:%S')
    fmt_timezone = "+00:00"
    return fmt_datetime + fmt_timezone

def get_datetime_obj(unixtime):
    import datetime
    fmt_datetime=datetime.datetime.fromtimestamp(float(str(unixtime))).strftime('%Y-%m-%d %H:%M:%S')
    mytimeobj=datetime.datetime.strptime(fmt_datetime,'%Y-%m-%d %H:%M:%S')
    return mytimeobj

def get_unixtime_from_datetime(dt):
    tz = pytz.timezone('US/Pacific')
    udt = dt.astimezone(tz) 
    mytime11=time.mktime(udt.timetuple())
    return mytime11

class FixedOffset(tzinfo):
    """offset_str: Fixed offset in str: e.g. '-0400'"""
    def __init__(self, offset_str):
        sign, hours, minutes = offset_str[0], offset_str[1:3], offset_str[3:]
        offset = (int(hours) * 60 + int(minutes)) * (-1 if sign == "-" else 1)
        self.__offset = timedelta(minutes=offset)
        # NOTE: the last part is to remind about deprecated POSIX GMT+h timezones
        # that have the opposite sign in the name;
        # the corresponding numeric value is not used e.g., no minutes
        '<%+03d%02d>%+d' % (int(hours), int(minutes), int(hours)*-1)
    def utcoffset(self, dt=None):
        return self.__offset
    def tzname(self, dt=None):
        return self.__name
    def dst(self, dt=None):
        return timedelta(0)
    def __repr__(self):
        return 'FixedOffset(%d)' % (self.utcoffset().total_seconds() / 60)

def get_unixtime_from_deltatime(date_with_tz):
    date_str, tz = date_with_tz[:-5], date_with_tz[-5:]
    dt_utc = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
    dt = dt_utc.replace(tzinfo=FixedOffset(tz))
    if (nrm_config["debug"]>9): 
        print "OSCARS: datetime=", dt
    myutime1 = get_unixtime_from_datetime(dt)
    if (nrm_config["debug"]>9):
        print "OSCARS: unixtime=", myutime1
    return myutime1

#class nrm_user(object):
#    tablename = "user"
#    id = ""
#    passwd = ""
#    token = ""
#    dn = ""
#    def __init__(self):
#        self.id=""
#        self.passwd=""
#        self.token=""
#        self.dn=""
#
#    def assign(self, key, value):
#        if (key.lower() == "id"):
#            self.id = value
#        elif (key.lower() == "passwd"):
#            self.passwd = value
#        elif (key.lower() == "token"):
#            self.token = value
#        elif (key.lower() == "dn"):
#            self.dn = value
#        else:
#            return "User key not found: ", key
            
class nrm_fixture(object):
    id = "" # (junction.id)
    ingress = 0
    egress = 0
    port_urn = "" #(string)
    vlan_id = 0

    def __init__(self, jid, ingr, egre, purn, vid):
        self.id = jid # (junction.id)
        self.ingress = ingr
        self.egress = egre
        self.port_urn = purn #(string)
        self.vlan_id = vid

    def assign(self, key, value):
        if (key.lower() == "id"):
            self.id = value
        elif (key.lower() == "ingress"):
            self.ingress = value
        elif (key.lower() == "egress"):
            self.egress = value
        elif (key.lower() == "port_urn"):
            self.port_urn = value
        elif (key.lower() == "vlan_id"):
            self.vlan_id = value
        else:
            return "Held key not found: ", key, ", ", value

class nrm_held(object):
    id=""
    heldmode = sensenrm_db.heldModes.automatic   # manual
    description=""
    userid=""
    phase = sensenrm_db.heldPhases.held
    state = sensenrm_db.heldStates.active
    schedule_begin = None
    schedule_end = None
    schedule_expiration = None
    schedule_refid = ""
    junction_list = []
    bandwidth_az = 0
    bandwidth_za = 0
    pce_id = ""
    fixtures_list=[]
    
    def __init__(self):
        self.id=""
        heldmode = sensenrm_db.heldModes.automatic  # manual
        description=""
        userid=""
        phase = sensenrm_db.heldPhases.held
        state = sensenrm_db.heldStates.active
        schedule_begin = None
        schedule_end = None
        schedule_expiration = None
        schedule_refid = ""
        junction_list = []
        bandwidth_az = 0
        bandwidth_za = 0
        pce_id = ""
        fixtures_list = []
        
    def assign(self, key, value):
        if (key.lower() == "id"):
            self.id = value
        elif (key.lower() == "heldmode"):
            self.heldmode = value
        elif (key.lower() == "description"):
            self.description = value
        elif (key.lower() == "userid"):
            self.userid = value
        elif (key.lower() == "phase"):
            self.phase = value
        elif (key.lower() == "state"):
            self.state = value
        elif (key.lower() == "schedule_begin"):
            self.schedule_begin = value
        elif (key.lower() == "schedule_end"):
            self.schedule_end = value
        elif (key.lower() == "schedule_expiration"):
            self.schedule_expiration = value
        elif (key.lower() == "schedule_refid"):
            self.schedule_refid = value
        elif (key.lower() == "bandwidth_az"):
            self.bandwidth_az = value
        elif (key.lower() == "bandwidth_za"):
            self.bandwidth_za = value
        elif (key.lower() == "pce_id"):
            self.pce_id = value
        elif (key.lower() == "fixtures_list"):
            self.fixtures_list.append(value)
        else:
            return "Held key not found: ", key
            
class nrm_vlanRange(object):
    floor=0
    ceiling=0
    def __init__(self):
        self.floor=0
        self.ceiling=0
    
    def assign(self, key, value):
        if (key.lower() == "floor"):
            self.floor = value
        elif (key.lower() == "ceiling"):
            self.ceiling = value
        else:
            return "vlanRange key not found: ", key
    
    def indented_show(self):
        mystr = "{\n\t\t\"floor\" : " + str(self.floor) + ",\n\t\t\"celing\" : " + str(self.ceiling) + "\n\t}"
        return mystr
    
class nrm_junction(object):
    junction_id=""
    junction_name=""
    port_urn=""
    vlanRanges=[]
    vlanr = nrm_vlanRange()
    vlanExpression=""
    ingressBandwidth=0
    egressBandwidth=0
    time_begin = None
    time_end = None
    
    def __init__(self, name):
        self.junction_name=name
        self.junction_id=""
        self.port_urn=""
        self.vlanRanges=[]
        self.vlanr = nrm_vlanRange()
        self.vlanExpression=""
        self.ingressBandwidth=0
        self.egressBandwidth=0
        self.time_begin = datetime.utcnow()
        self.time_end = get_delayed_time(2)
    
    def db_assign(self):
        sensenrm_db.insert_junction(mydb_session, self)
    
    def assign_value(self, key, value):
        if (key.lower() == "junction_id"):
            self.junction_id = value
        elif (key.lower() == "junction_name"):
            self.junction_name = value
        elif (key.lower() == "port_urn"):
            self.port_urn = value
        elif (key.lower() == "vlanRanges"):
            self.vlanRanges = value
        elif (key.lower() == "vlanr"):
            self.vlanr = value
        elif (key.lower() == "vlanExpression"):
            self.vlanExpression = value
        elif (key.lower() == "ingressBandwidth"):
            self.ingressBandwidth = value
        elif (key.lower() == "egressBandwidth"):
            self.egressBandwidth = value
        elif (key.lower() == "time_begin"):
            self.time_begin = value
        elif (key.lower() == "time_end"):
            self.time_end = value
        else:
            return "Junction key not found: ", key
    
    def findkeyvaluedict(self, keystr):
        for keyv in keystr:
            value = keystr[keyv]
            if (nrm_config["debug"]>9): print "KD=", keyv
            self.assign(keyv, value)
            
    def findkeyvaluelist(self, keystr):
        if (len(keystr) == 0) :
            if (nrm_config["debug"]>9): print "VL=0"
        else :
            keystri = iter(keystr)
            for value in keystri:
                if (type(value) is dict):
                    self.findkeyvaluedict(value)
                elif (type(value) is list):
                    self.findkeyvaluelist(value)
                else:
                    if (nrm_config["debug"]>9): print "VL=", value

    def assign(self, key, value):
        def vlans():
            if (nrm_config["debug"]>9): print "#vlanRanges=", value
            self.findkeyvaluelist(value)
        def floor():
            if (nrm_config["debug"]>9): print "#floor=", value
            self.vlanr.floor = value
            if (self.vlanr.floor is 0):
                if (nrm_config["debug"]>9): print "##floor=ZERO?"
            else:
                if (self.vlanr.ceiling is not 0):
                    self.vlanRanges.append(self.vlanr)
                    self.vlanr = nrm_vlanRange()
                    if (nrm_config["debug"]>9): print "##floor=", self.vlanr.floor
                else:
                    if (nrm_config["debug"]>9): print "##floor_ceiling=HUH?"
        def ceiling():
            if (nrm_config["debug"]>9): print "#ceiling=", value
            self.vlanr.ceiling = value
            if (self.vlanr.ceiling is 0): 
                if (nrm_config["debug"]>9): print "##ceiling=ZERO?"
            else:
                if (self.vlanr.floor is not 0):
                    self.vlanRanges.append(self.vlanr)
                    self.vlanr = nrm_vlanRange()
                    if (nrm_config["debug"]>9): print "##ceiling", self.vlanr.ceiling
                else:
                    if (nrm_config["debug"]>9): print "##ceiling_floor=ZERO"
        def vlanExpression():
            if (nrm_config["debug"]>9): print "#vlanExpression", value
            self.vlanExpression = value
        def ingressBandwidth():
            if (nrm_config["debug"]>9): print "#ingressBandwidth", value
            self.ingressBandwidth = value
        def egressBandwidth():
            if (nrm_config["debug"]>9): print "#egressBandwidth", value
            self.egressBandwidth = value
        
        options = {"vlanRanges" : vlans,
                        "floor" : floor,
                        "ceiling" : ceiling,
                        "vlanExpression" : vlanExpression,
                        "ingressBandwidth" : ingressBandwidth,
                        "egressBandwidth" : egressBandwidth,
        }
        
        if options.has_key(key):
            options[key]()
        else:
            if (nrm_config["debug"]>9): printf("OSCARS: JUNCTION assign NONE\n");
        
    def indented_show(self):
        def pvlans(vlanrs):
            mystr=""
            for i, v in enumerate(vlanrs):
                mystr =  mystr + v.indented_show() 
                if i is not len(vlanrs)-1:
                    mystr = mystr + ","
            return mystr
        print self.junction_name, ": {" 
        print "\t\"vlanRanges\" : [", pvlans(self.vlanRanges), "],"
        print "\t\"vlanExpression\" : \"" + self.vlanExpression + "\",\n"
        print "\t\"ingressBandwidth\" : ", self.ingressBandwidth, ","
        print "\t\"egressBandwidth\" : ", self.egressBandwidth
        print "}"
    
class nrm_pce(object):
    id = ""  # delta id
    time_begin = None
    time_end = None
    junction_a = ""
    junction_b = ""
    evaluted = 0
    cost = 0.0
    azEro=[]
    zaEro=[]
    azAvailable = 0
    zaAvailable = 0
    azBaseline = 0
    zaBaseline = 0
    held_id = ""  # Connection ID from OSCARS
    
    def __init__(self, heldid, deltaid, ja, jb, bt, et):
        if (len(deltaid) != 0) or (deltaid is not None):
            self.id=deltaid # delta id from orchestrator
        self.time_begin = get_datetime_obj(bt)    # datetime.utcnow()
        self.time_end = get_datetime_obj(et)      # datetime.utcnow()
        self.junction_a = ja
        self.junction_b = jb
        self.evaluated = 0
        self.cost = 0.0
        self.azEro=[]
        self.zaEro=[]
        self.azAvailable = 0
        self.zaAvailable = 0
        self.azBaseline = 0
        self.zaBaseline = 0
        if (len(heldid) == 0) or (heldid is None):  # connection id for held from OSCARS
            self.held_id = ""
        else:
            self.held_id = heldid
    
    def indented_show(self):
        def pvlans(vlanrs):
            mystr=""
            for i, v in enumerate(vlanrs):
                mystr =  mystr + v.indented_show() 
                if i is not len(vlanrs)-1:
                    mystr = mystr + ","
            return mystr
        print "UUID: ", self.id
        print "ConnID: ", self.held_id
        print "junction_a: ", self.junction_a
        print "junction_b: ", self.junction_b
        print "\"shortest\": {" 
        print "\t\"cost\" : " + str(self.cost) + ","
        print "\t\"azEro\" : ", self.azEro, ","
        print "\t\"zaEro\" : ", self.zaEro, ","
        print "\t\"azAvailable\" : " + str(self.azAvailable) + ","
        print "\t\"zaAvailable\" : ", str(self.zaAvailable), ","
        print "\t\"azBaseline\" : ", str(self.azBaseline), ","
        print "\t\"zaBaseline\" : ", str(self.zaBaseline)
        print "}"
    
    def assign(self, key, value):
        def azEro():
            if (nrm_config["debug"]>9): print "#azEro=", value
            self.findkeyvaluelistaz(value)
        def zaEro():
            if (nrm_config["debug"]>9): print "#zaEro=", value
            self.findkeyvaluelistza(value)
        def cost():
            if (nrm_config["debug"]>9): print "#cost", value
            self.cost = float(value)
        def azAvailable():
            if (nrm_config["debug"]>9): print "#azAvailable", value
            self.azAvailable = int(value)
        def zaAvailable():
            if (nrm_config["debug"]>9): print "#zaAvailable", value
            self.zaAvailable = int(value)
        def azBaseline():
            if (nrm_config["debug"]>9): print "#azBaseline", value
            self.azBaseline = int(value)
        def zaBaseline():
            if (nrm_config["debug"]>9): print "#zaBaseline", value
            self.zaBaseline = int(value)

        options = {"cost" : cost,
                        "azEro" : azEro,
                        "zaEro" : zaEro,
                        "azAvailable" : azAvailable,
                        "zaAvailable" : zaAvailable,
                        "azBaseline" : azBaseline,
                        "zaBaseline" : zaBaseline,
        }
        
        if options.has_key(key):
            options[key]()
        else:
            if (nrm_config["debug"]>9): print "OSCARS: PCE assign NONE";
        
    def assign_value(self, key, value):
        
        if (key.lower() == "id"):
            self.id = value
        elif (key.lower() == "time_begin"):
            self.time_begin = value
        elif (key.lower() == "time_end"):
            self.time_end = value
        elif (key.lower() == "evaluated"):
            self.evaluated = value
        elif (key.lower() == "cost"):
            self.cost = value
        elif (key.lower() == "azEro"):
            self.azEro = value
        elif (key.lower() == "zaEro"):
            self.zaEro = value
        elif (key.lower() == "azAvailable"):
            self.azAvailable = value
        elif (key.lower() == "zaAvailable"):
            self.zaAvailable = value
        elif (key.lower() == "azBaseline"):
            self.azBaseline = value
        elif (key.lower() == "zaBaseline"):
            self.zaBaseline = value
        elif (key.lower() == "held_id"):
            self.held_id = value
        else:
            return "PCE key not found: ", key
        

    def findkeyvaluedict(self, keystr):
        if (nrm_config["debug"]>9): print "OSCARS: PCE findkeyvaluedict"
        for keyv in keystr:
            value = keystr[keyv]
            if (nrm_config["debug"]>9): print "#KD=", keyv
            self.assign(keyv, value)

    def findkeyvaluelistaz(self, keystr):
        if (nrm_config["debug"]>9): print "OSCARS: PCE findkeyvaluelistaz"
        if (len(keystr) == 0) :
            if (nrm_config["debug"]>9): print "#VLaz="
        else :
            if (nrm_config["debug"]>9): print "#MYLISTaz: ", keystr
            keystri = iter(keystr)
            for value in keystri:
                if (nrm_config["debug"]>9): print "#KL2az=", value
                for keyv in value:
                    myurnvalue = value[keyv]
                    if (nrm_config["debug"]>9): print "#LISTaz: ", keyv, "=", myurnvalue
                    self.azEro.append(str(myurnvalue))

    def findkeyvaluelistza(self, keystr):
        if (nrm_config["debug"]>9): print "OSCARS: PCE findkeyvaluelistza"
        if (len(keystr) == 0) :
            if (nrm_config["debug"]>9): print "#VLza="
        else :
            if (nrm_config["debug"]>9): print "#MYLISTza: ", keystr
            keystri = iter(keystr)
            for value in keystri:
                if (nrm_config["debug"]>9): print "#KL2za=", value
                for keyv in value:
                    myurnvalue = value[keyv]
                    if (nrm_config["debug"]>9): print "#LISTza: ", keyv, "=", myurnvalue
                    self.zaEro.append(str(myurnvalue))

class nrm_oscars_json_parser(object):
    junctions=[]
    pce=[]
    
    def __init__(self):
        self.junctions=[]
        self.pce=[]
            
    def pce_parser(self, id, deltaid, a, b, bt, et, jstr):
        for key in jstr:
            if (key == "shortest") :  # OR shortest or fits
                valuestr = jstr[key]
                mypce=nrm_pce(id, deltaid, a, b, bt, et)
                if (nrm_config["debug"]>9): print "#KEY=", key
                if (type(valuestr) is dict):
                    if (nrm_config["debug"]>9): print "#DICT"
                    mypce.findkeyvaluedict(valuestr)
                elif (valuestr is None):
                    if (nrm_config["debug"]>9): print "#Value is None"
                    mypce.findkeyvaluedict(valuestr)
                else:
                    if (nrm_config["debug"]>9): print "#LIST VALUE=", valuestr
                    mypce.findkeyvaluedict(valuestr)
                self.pce.append(mypce)
        return self.pce

    def json_parser(self, jstr):
        for key in jstr:
            valuestr = jstr[key]
            myjunction=nrm_junction(key);
            if (nrm_config["debug"]>9): print "#KEY=", key
            if (type(valuestr) is dict):
                myjunction.findkeyvaluedict(valuestr)
            else:
                if (nrm_config["debug"]>9): print "#VALUE=", valuestr
            self.junctions.append(myjunction)
        return self.junctions
    

class nrm_oscars_connection(object):
    oscars_url = oscars_config["url"]
    debug = True
    last_activity_time = time.mktime(datetime.now().timetuple())
    mytoken = ""
    
    if oscars_config["default_token"] == None:
        raise Exception('Cannot get oscars_config["default_token"]. Edit sensenrm_config.py for oscars_config.default_token')
    else:
        mytoken = oscars_config["default_token"]
    
    def __init__(self):
        last_activity_time = get_unixtime(0)
        
    def _url(self, path):
        return 'http://' + self.oscars_url + path

    def _surl(self, path):
        return 'https://' + self.oscars_url + path

    def get_token(self, uid, upasswd):
        if (nrm_config["debug"]>7): print "OSCARS: GetToken"
#        if oscars_config["default_user"] == None:
#            raise Exception('Cannot get oscars_config["default_user"]. Edit sensenrm_config.py for oscars_config.default_user')
#        else:
#            defaultuser = oscars_config["default_user"]
#        if oscars_config["default_passwd"] == None:
#            raise Exception('Cannot get oscars_config["default_passwd"]. Edit sensenrm_config.py for oscars_config.default_passwd')
#        else:
#            defaultpasswd = oscars_config["default_passwd"]
        resp = requests.post(self._surl('/api/account/login'), json={
            'username': uid,
            'password': upasswd
            }, verify=False)
        if (nrm_config["debug"]>7): print "OSCARS: GetToken DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): 
                print "OSCARS: Token FAILED:", resp._content
            raise Exception('OSCARS: Cannot GetToken: {}'.format(resp.status_code))
        if (nrm_config["debug"]>6): 
            print "OSCARS: Token_UID: ", uid
            print "OSCARS: Token:", resp._content
        return str(resp._content)
    
    def get_sslinfo(self):
        if (nrm_config["debug"]>7): print "OSCARS: SSLinfo"
        resp = requests.get(self._surl('/api/version'), verify=False)
        if (nrm_config["debug"]>7): 
            print "OSCARS: SSLinfo DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): 
                print "OSCARS: SSLinfo FAILED:", resp._content
            raise Exception('OSCARS: Cannot get_SSLinfo: {}'.format(resp.status_code))
        if (nrm_config["debug"]>6): 
            #print "OSCARS: SSLinfo: ", resp.headers['content-type']
            print "OSCARS: SSLinfo:", resp._content
        return str(resp._content)
            
    def get_info(self):
        if (nrm_config["debug"]>7): print "OSCARS: Info"
        resp = requests.get(self._surl('/api/topo/version'), verify=False)
        if (nrm_config["debug"]>7): 
            print "OSCARS: Info DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): 
                print "OSCARS: Info FAILED:", resp._content
            raise Exception('OSCARS: Cannot get_info: {}'.format(resp.status_code))
        if (nrm_config["debug"]>6): 
            print "OSCARS: Info:", resp._content
        return str(resp._content)

    def get_protected_info(self):
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, "default")
        myheaders = {'authentication': thisToken} 
        if (nrm_config["debug"]>7): print "OSCARS: Protected_SSL"
        resp = requests.get(self._surl('/protected/greeting'), 
                            verify=False, headers=myheaders)
        if (nrm_config["debug"]>7): 
            print "OSCARS: Protected_SSL DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): 
                print "OSCARS: Protected_SSL FAILED:", resp._content
            raise Exception('OSCARS: Cannot get_protected_info: {}'.format(resp.status_code))
        if (nrm_config["debug"]>6): 
            print "OSCARS: Protected_SSL:", resp._content
        return str(resp._content)

    def writeAvail(self, mytime, acontent):
        timed_file = datetime.fromtimestamp(time.mktime(datetime.now().timetuple())).strftime('%Y%m%d-%H%M%S')
        output_file = log_config["basepath"]+"/avail_" + str(timed_file) + "_" + str(mytime) + ".txt"
        if (nrm_config["debug"]>2):
            print "OSCARS: AVAIL_OUTPUT_PATH=", output_file
        fo = open(output_file, 'w')
        fo.write(acontent)
        fo.close()

        return True
        
    def get_avail_topo(self):
        myutime1 = get_unixtime(0)
        myutime2 = get_unixtime(2)
        if (nrm_config["debug"]>3): 
            print "OSCARS: GET_MODEL_time=", myutime1, ", ", myutime2
            # print "HERE_TOPO_00"
        resp = requests.post(self._surl('/api/topo/available'), json={
            'beginning': myutime1,	# java.time.Instant format
            'ending': myutime2
            }, verify=False)

        if (nrm_config["debug"]>7): 
            print "OSCARS: GET_MODEL_DONE: ", resp.status_code
            # print "HERE_TOPO"
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): 
                print "OSCARS: MODEL_AVAIL FAILED: ", resp._content
            raise Exception('OSCARS: Cannot get_avail_topo: {}'.format(resp.status_code))
        if (nrm_config["debug"]>8): 
            print "OSCARS: MODEL_AVAIL :\n", resp._content
            self.writeAvail(str(myutime1), str(resp._content))
        
        ## convert response to formatted output, eventually to SENSE API format
        myparser=nrm_oscars_json_parser()
        myjunctions = myparser.json_parser(resp.json())
        for j in myjunctions:
            with mydb_session() as s:
                sensenrm_db.insert_junction(s, j)
        if (nrm_config["debug"]>7): 
            with mydb_session() as s:
                sensenrm_db.display_db_junctions(s)
        return str(resp._content)

    def get_reserved(self):
        if (nrm_config["debug"]>7): print "OSCARS: RESERVED_LIST"
        resp = requests.get(self._surl('/api/conn/simplelist'), verify=False)

        if (nrm_config["debug"]>7):
            print "OSCARS: GET_RESERVED_LIST_DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3):
                print "OSCARS: ReservedList FAILED: ", resp._content
            raise Exception('OSCARS Cannot get ReservedList: {}'.format(resp.status_code))
        if (nrm_config["debug"]>6):
            print "OSCARS: ReservedList:\n", resp._content
        return str(resp._content)
        
    def get_conn_id(self, groupid):  # e.g. groupid = "default"
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, groupid)
            if (thisToken is None):
                raise Exception('OSCARS: ConnID Cannot get Token : {}'.format(groupid))
        myheaders = {'authentication': thisToken} 
        if (nrm_config["debug"]>7): print "OSCARS: ConnID"
        resp = requests.get(self._surl('/protected/conn/generateId'), 
                            verify=False, headers=myheaders)
        if (nrm_config["debug"]>7): print "OSCARS: ConnID DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): 
                print "OSCARS: ConnID FAILED: ", resp._content
            raise Exception('OSCARS: Cannot GetConnID : {}'.format(resp.status_code))
        if (nrm_config["debug"]>3): 
            print "OSCARS: ConnID: ", resp._content
            #print "ConnID TYPE: ", type(resp._content)

        with mydb_session() as s:
            sensenrm_db.insert_conn(s, resp._content, groupid)
        return str(resp._content)
    
    def get_pce(self, id, deltaid, src, dest, myutime1, myutime2):
        if (nrm_config["debug"]>7): print "OSCARS: Path_Computation"

        resp = requests.post(self._surl('/api/pce/paths'), json={
            "interval": {
                'beginning': myutime1,	# java.time.Instant format
                'ending': myutime2
            },
            "a": src,
            "z": dest,
            "azBw": 0,
            "zaBw": 0
            }, verify=False)
        if (nrm_config["debug"]>7): print "OSCARS: Path_Computation DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): print "OSCARS: Path_Computation FAILED: ", resp._content
            raise Exception('OSCARS: Cannot get_PCE : {}'.format(resp.status_code))
        if (nrm_config["debug"]>6): print "OSCARS: Path_Computation: ", resp._content
        ## convert response to formatted output, eventually to SENSE API format
        myparser=nrm_oscars_json_parser()
        mypce = myparser.pce_parser(id, deltaid, src, dest, myutime1, myutime2, resp.json())
        for j in mypce:
            j.indented_show()
            with mydb_session() as s:
                sensenrm_db.insert_pce(s, j)
        
        return mypce

    def get_pcelist(self, id, deltaid, jlist, starttime, endtime):
        # 2018-07-13T10:37:01.000-0400
        myutime1 = get_unixtime_from_deltatime(starttime)
        myutime2 = get_unixtime_from_deltatime(endtime)
        #if (nrm_config["debug"]>5): 
        #    print "PCE_time_unixtime=", myutime1, ", ", myutime2

        if (nrm_config["debug"]>7): print "OSCARS: Path_Computation_list"
        
        jpairs = [(jlist[i],jlist[j]) for i in range(len(jlist)) for j in range(i+1, len(jlist))]
        if (nrm_config["debug"]>6): print "OSCARS: Junction_Pairs=", jpairs
        mypce = []
        for a, z in jpairs:
            ja = a.split(':')[0] #oSwitch.id = delta.id:netlab-7750sr12-rt1:9/1/4:port
            jz = z.split(':')[0]
            if (nrm_config["debug"]>7): 
                print a, z
                print ja, jz
            if not (ja == jz) :
                try:
                    mypce = mypce + self.get_pce(id, deltaid, ja, jz, myutime1, myutime2)
                except Exception as e:
                    if (nrm_config["debug"]>3): print "OSCARS: PCE EXCEPT: ", e
                    raise
            else :
                if (nrm_config["debug"]>7): print "SAME junctions"

        if (nrm_config["debug"]>9): 
            print "OSCARS: PRINT DB ALL PCEs"
            with mydb_session() as s:
                sensenrm_db.display_db_pce(s)
        
        return mypce
    
    def get_clear(self, connid, groupid):
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, groupid)
            if (thisToken is None):
                raise Exception('OSCARS: CLEAR Cannot get Token : {}'.format(groupid))
        myheaders = {'authentication': thisToken}
        if (nrm_config["debug"]>7): print "OSCARS: CLEAR_ID=", connid
        resp = requests.get(self._surl('/protected/held/clear/')+connid,
            verify=False, headers=myheaders)
        if (nrm_config["debug"]>7): print "OSCARS: CLEAR DONE: ", resp.status_code
        if resp.status_code == 200:
            if (nrm_config["debug"]>3): print "OSCARS: CLEAR: ", resp._content
        else:
            if (nrm_config["debug"]>3): print "OSCARS: CLEAR FAILED: ", resp._content
            #raise Exception('OSCARS Cannot CLEAR: {}'.format(resp.status_code))
        return resp.status_code, resp._content

    def get_commit(self, connid, groupid):
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, groupid)
            if (thisToken is None):
                raise Exception('OSCARS: COMMIT Cannot get Token : {}'.format(groupid))
        myheaders = {'authentication': thisToken} 
        if (nrm_config["debug"]>7): print "OSCARS: COMMIT_ID=", connid

        resp = requests.post(self._surl('/protected/conn/commit'), 
            connid, verify=False, headers=myheaders)
        if (nrm_config["debug"]>7): print "OSCARS: COMMIT DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): print "OSCARS: COMMIT FAILED: ", resp._content
            raise Exception('OSCARS Cannot COMMIT: {}'.format(resp.status_code))
        if (nrm_config["debug"]>3): print "OSCARS: COMMIT: ", resp._content
        return resp.status_code, resp._content
        
    def get_uncommit(self, connid, groupid):
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, groupid)
            if (thisToken is None):
                raise Exception('OSCARS: UNCOMMIT Cannot get Token : {}'.format(groupid))
        myheaders = {'authentication': thisToken} 
        if (nrm_config["debug"]>7): print "OSCARS: UNCOMMIT"
        resp = requests.post(self._surl('/protected/conn/uncommit'), json={
            'connectionId': connid
            }, verify=False, headers=myheaders)
        if (nrm_config["debug"]>7): print "OSCARS: UNCOMMIT DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): print "OSCARS: UNCOMMIT FAILED: ", resp._content
            raise Exception('OSCARS:Cannot UNCOMMIT : {}'.format(resp.status_code))
        if (nrm_config["debug"]>3): print "OSCARS: UNCOMMIT: ", resp._content
        return resp.status_code, resp._content

    def get_cancel(self, connid, groupid):
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, groupid)
            if (thisToken is None):
                raise Exception('OSCARS: CANCEL Cannot get Token : {}'.format(groupid))
        myheaders = {'authentication': thisToken} 
        if (nrm_config["debug"]>7): 
            print "OSCARS: CANCEL GROUPID:",groupid
        #resp = requests.post(self._surl('/protected/conn/cancel'), 
        resp = requests.post(self._surl('/protected/conn/release'), 
            connid, verify=False, headers=myheaders)
        if (nrm_config["debug"]>7): print "OSCARS: CANCEL DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): print "OSCARS: CANCEL FAILED: ", resp._content
            #raise Exception('OSCARS Cannot CANCEL: {}'.format(resp.status_code))
        if (nrm_config["debug"]>3): print "OSCARS: CANCEL: ", resp._content
        return resp.status_code, resp._content

    def get_status(self, connid):
        if (nrm_config["debug"]>7): print "OSCARS: STATUS"
        resp = requests.get(self._surl('/api/conn/info/'+connid), verify=False)
        if (nrm_config["debug"]>7): print "OSCARS: STATUS_DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): print "OSCARS: STATUS FAILED: ", resp._content
            raise Exception('OSCARS Cannot get STATUS: {}'.format(resp.status_code))
        if (nrm_config["debug"]>3): print "OSCARS: STATUS:", resp._content
        return resp

    def dump(self, obj, nested_level=0, output=sys.stdout):
        spacing = '   '
        if type(obj) == dict:
            print >> output, '%s{' % ((nested_level) * spacing)
            for k, v in obj.items():
                if hasattr(v, '__iter__'):
                    print >> output, '%s%s:' % ((nested_level + 1) * spacing, k)
                    dump(v, nested_level + 1, output)
                else:
                    print >> output, '%s%s: %s' % ((nested_level + 1) * spacing, k, v)
            print >> output, '%s}' % (nested_level * spacing)
        elif type(obj) == list:
            print >> output, '%s[' % ((nested_level) * spacing)
            for v in obj:
                if hasattr(v, '__iter__'):
                    dump(v, nested_level + 1, output)
                else:
                    print >> output, '%s%s' % ((nested_level + 1) * spacing, v)
            print >> output, '%s]' % ((nested_level) * spacing)
        else:
            print >> output, '%s%s' % (nested_level * spacing, obj)
    
    
    def get_conn_held(self, connid, deltaid, swdict, mypce, flist, starttime, endtime, groupid):
        with mydb_session() as s:
            thisToken = sensenrm_db.get_group_token(s, groupid)
            if (thisToken is None):
                raise Exception('OSCARS: HELD Cannot get Token : {}'.format(groupid))
        myheaders = {'authentication': thisToken} 
        #if (nrm_config["debug"]>7): print "OSCARS: HELD_headers: ", myheaders

        if (connid is None) or (deltaid is None):
            raise Exception('OSCARS: Cannot HELD. Conn ID and/or Delta ID is empty.')
            
        # 2018-07-13T10:37:01.000-0400
        myutime1 = get_unixtime_from_deltatime(starttime)
        myutime2 = get_unixtime_from_deltatime(endtime)
        if (nrm_config["debug"]>2): 
            print "OSCARS: HELD deltaid=", deltaid
            print "OSCARS: HELD connid=", connid
            print "OSCARS: HELD begin,end=", myutime1, ", ", myutime2
            print "OSCARS: HELD URL=", self._surl('/protected/held/{:s}'.format(connid))

        if (nrm_config["debug"]>7): print "PCE came along: ", len(mypce)
        if (nrm_config["debug"]>5):
            for j in mypce:
                #print "OSCARS: HELD UUID: ", j.id
                #print "OSCARS: HELD ConnID: ", j.held_id
                #print "OSCARS: HELD junction_a: ", j.junction_a
                #print "OSCARS: HELD junction_b: ", j.junction_b
                #print "\t\"cost\" : " + str(j.cost) + ","
                #print "\t\"azEro\" : ", j.azEro, ","
                #print "\t\"zaEro\" : ", j.zaEro, ","
                #print "\t\"azAvailable\" : " + str(j.azAvailable) + ","
                #print "\t\"zaAvailable\" : ", str(j.zaAvailable), ","
                #print "\t\"azBaseline\" : ", str(j.azBaseline), ","
                #print "\t\"zaBaseline\" : ", str(j.zaBaseline)
                j.indented_show()
        
        jlist = []
        for k in swdict.keys():
            mysw=swdict[k]
            jlist.append(k)
            mysw.reservedbw

        def get_bandwidth(devicename):
            for a in flist:
                ja = a.id.split(':')[0]
                if (devicename == ja):
                    if (nrm_config["debug"]>7): print "OSCARS: HELD devicename_found=", a.port_urn
                    return (int) (swdict[a.port_urn+":"+str(a.vlan_id)].reservedbw / 1000000)
            if (nrm_config["debug"]>7): print "OSCARS: HELD devicename_not_found=", devicename   # it should not be here
            return -1

        azbw = 0
        zabw = 0
        mypipe='['
        for j in mypce:
            if (nrm_config["debug"]>9):
                print "OSCARS: HELD azEro: ", j.azEro
                print "OSCARS: HELD zaEro: ", j.zaEro
            azbw = get_bandwidth(j.junction_a)
            zabw = get_bandwidth(j.junction_b)
            mypipe = mypipe + '{ \
                "a": "' + j.junction_a + '", \
                "z": "' + j.junction_b + '", \
                "mbps": null, \
                "azMbps": ' + str(azbw) + ',\
                "zaMbps": ' + str(zabw) + ',\
                "ero": [ ' 
            jazero = []
            for a in j.azEro:
                jazero.append(str('"' + a + '"'))
            
            mypipe = mypipe + ', '.join(x for x in jazero) + ']} '
            
            if mypce.index(j) != len(mypce)-1:
                mypipe = mypipe + ','
        mypipe = mypipe + ']'

        if (nrm_config["debug"]>5): 
            print "OSCARS: HELD MYPIPE=", mypipe
            print "OSCARS: HELD Junctions=", jlist
        tjlist=[]
        myjuncs='['
        for a in jlist:
            ja = a.split(':')[0]
            if (nrm_config["debug"]>9): print "OSCARS: HELD junction = ", a, ", ", ja
            if not (ja in tjlist):
                tjlist.append(ja)
                if jlist.index(a) == 0:
                    myjuncs=myjuncs+'{ "device": "' + ja + '"' + ' }'
                else:
                    myjuncs=myjuncs+', { "device": "' + ja + '"' + ' }'
        myjuncs = myjuncs + ']'
        
        '''
        Each fixture belongs to a single junction, 
        each pipe touches two junctions,
        each junction can have 0..N fixtures.
        A fixture has a junction field but it's single-valued
        '''
        if (nrm_config["debug"]>5): print "Fixtures=", flist
        myfix='['
        for a in flist:
            ja = a.id.split(':')[0]
            if (nrm_config["debug"]>9): print "OSCARS: HELD junction = ", a, ", ", ja
            myfix=myfix+'{ "junction": "' + ja + '", \
                  "port": "' + a.port_urn + '", \
                  "vlan": ' + str(a.vlan_id) + ', \
                  "inMbps": ' + str(a.ingress) + ', \
                  "outMbps": ' + str(a.egress) + ' \
                  }'
            if flist.index(a) != len(flist)-1:
                myfix = myfix + ','
        myfix = myfix + ']'
        if (nrm_config["debug"]>7): print "OSCARS: HELD Fixtures=", myfix
        
        from collections import OrderedDict
        jsontext='{ \
            "connectionId": "' + connid + '", \
            "begin": ' + str(myutime1) + ', \
            "end": ' + str(myutime2) + ', \
            "mode": "AUTOMATIC",	 \
            "junctions": ' + myjuncs + ', \
            "pipes": ' + mypipe + ', \
            "fixtures": ' + myfix + ', \
            "description": "' + deltaid + '" \
            }'
            
        jsonobj=json.loads(jsontext, object_pairs_hook=OrderedDict)
        if (nrm_config["debug"]>6):
            print "############################"
            print jsontext
            print "############################"
            print "HELD INPUT"
            print json.dumps(jsonobj, indent=4)
        
        if (nrm_config["debug"]>7): print "OSCARS: HELD"
        req = requests.Request('POST', self._surl('/protected/hold'), headers=myheaders, json=jsonobj)

        prepared = req.prepare()

        def pretty_print_POST(req):
            print('{}\n{}\n{}\n\n{}'.format(
                '-----------START-----------',
                req.method + ' ' + req.url,
                '\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
                req.body,
                '-----------END-----------',
            ))

        #pretty_print_POST(prepared)
        s = requests.Session()
        resp = s.send(prepared, verify=False)
        # response is when your hold expires before that you will need to do a commit
        if (nrm_config["debug"]>7): print "OSCARS: HELD DONE: ", resp.status_code
        if resp.status_code != 200:
            if (nrm_config["debug"]>3): print "OSCARS: HELD FAILED: ", resp._content
            raise Exception('OSCARS Cannot HELD: {}'.format(resp.status_code))
        if (nrm_config["debug"]>3): print "OSCARS: HELD: ", resp._content

        return resp
        

