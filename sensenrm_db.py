#
# SENSE Network Resource Manager (SENSE-NRM) Copyright (c) 2018-2020,
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
import sqlite3
from sqlite3 import Error

import sqlalchemy
from sqlalchemy.orm import sessionmaker
import os.path
from contextlib import contextmanager

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship, backref
import os.path
import json
import enum 

import time
from time import mktime
from datetime import tzinfo, timedelta, datetime
import dateutil.parser

from sensenrm_config import nrmdb_config, oscars_config, nrm_config, users_config
import sensenrm_utils as utils

Base = declarative_base()
database = None
db_session = None
initDone = False

#### data time for RFC_1123 and ISO_8601
class UTC(tzinfo):
  def utcoffset(self, dt):
    return timedelta(0)
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return timedelta(0)
utc = UTC()

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

def convert_str_to_datetime(mystr):
    date_with_tz = mystr
    date_str, tz = date_with_tz[:-5], date_with_tz[-5:]
    dt_utc = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
    dt = dt_utc.replace(tzinfo=FixedOffset(tz))
    return dt

class nrmSys (Base):
    __tablename__ = "nrmsys"

    id = Column(String, primary_key=True)
    last_model_time = Column(DateTime) # DateTime e.g. datetime.utcnow(), mObj.time_begin.strftime('%Y-%m-%d %H:%M:%S')
    model_changed = Column(Integer) # 0/1 
                                    # 1 when expired/terminated/cancelled/initialized
                                    # 0 when a new model is captured as last_model
    last_id = Column(String)
    last_href = Column(String)
    last_creationtime = Column(String)
    last_model= Column(String)

class oUser(Base):
    # User list for NRM access
    __tablename__ = "user"

    id = Column(String, primary_key=True) # DN
    group = Column(String) # oGroup:id (e.g. "default")
    role = Column(String) # admin, user
    active = Column(Integer) # 1=active, 0=inactive
    last_updated = Column(String) # str(datetime.now())

    def printMe(self):
        if (nrm_config["debug"]>0): utils.nprint("DN::[",self.id,"] Group=[",self.group,"]");

class oGroup(Base):
    # Group logins for OSCARS access (default access account, group access account, etc)
    __tablename__ = "group"

    id = Column(String, primary_key=True) # group id: default, cms, 
    login = Column(String)
    passwd = Column(String)
    dn = Column(String)
    code = Column(String)

    def printMe(self):
        if (nrm_config["debug"]>0): utils.nprint("id::[",self.id,"] login=[",self.login,"]");

class connModes(enum.Enum):
    created = 1
    delta_dereived = 2
    held = 3
    finished = 4
    aborted = 5
    cancelled = 6

class oConnID(Base):
    __tablename__ = "connid"

    id = Column(String, primary_key=True) # held_id "MMCF"
    userid = Column(String) # user id / login
    name = Column(String) # UUID from SENSE-O
    creation_date = Column(String)
    mode = Column(Enum(connModes))
           #"CREATED", "DELTA_RECEIVED", "HELD", "FINISHED", "ABORTED", "CANCELLED"

class oJunction(Base):
    __tablename__ = "junction"

    id = Column(String, primary_key=True) # netlab-7750sr12-rt1:9/1/4
    name = Column(String)   # netlab-7750sr12-rt1
    port_urn = Column(String)   # 9/1/4  # mystr.replace('/', '_')
    vlan_expression = Column(String)    # "2004,2006:2900"
    ingress_bandwidth = Column(Integer)
    egress_bandwidth = Column(Integer)
    bidports = Column(String) # delta_id:oJunctionID:vlan 
                              # "netlab-7750sr12-rt2:10/1/5:2210,netlab-mx960-rt1:xe-11/2/0:2210"
    
    held_id = Column(String, ForeignKey("held.id"))

class pceModes(enum.Enum):
    shortest = 1
    leatHops = 2
    fits = 3
    widestSum = 4
    widestAZ = 5
    widestZA = 6

class oPCE(Base):
    __tablename__ = "pce"
        
    id = Column(String, primary_key=True) # delta_id
    time_begin = Column(String)
    time_end = Column(String)
    evaluated = Column(Integer)
    pcemode = Column(Enum(pceModes))  # 1 shortest OR 3 fits
              #"shortest", "leatHops", "fits", "widestSum", "widestAZ", "widestZA"
    cost = Column(Float)
    ero_a_name = Column(String)  # juncion a from input
    ero_z_name = Column(String)  # junction z from input
    ero_az = Column(String) # comma separated list of junctions (id)
                            # e.g. list1 = ['1', '2', '3']
                            #      str1 = ','.join(list1)
                            #      list2 = str1.split(',')
                            # myList = ','.join(map(str, myList))
                            # list = [x.strip() for x in myList.split(',')]
    ero_za = Column(String) # comma separated list of junctions
    available_az = Column(Integer)
    available_za = Column(Integer)
    baseline_az = Column(Integer)
    baseline_za = Column(Integer)
    
    heldid = Column(String) # for local table
    held_id = Column(String, ForeignKey("held.id")) # Connection ID from OSCARS
    
class heldModes(enum.Enum):
    manual = 1
    automatic = 2

class heldPhases(enum.Enum):
    design = 1
    reserved = 2
    archived = 3
    held = 4

class heldStates(enum.Enum):
    waiting = 1
    active = 2
    finished = 3
    failed = 4

class oHeld(Base):
    __tablename__ = "held"
    
    id = Column(String, primary_key=True) # held_id "MMCF"
    heldmode = Column(Enum(heldModes))
               #"MANUAL", "AUTOMATIC"
    description = Column(String)
    userid = Column(String)
    phase = Column(Enum(heldPhases)) # HELD
                   #"DESIGN", "RESERVED", "ARCHIVED", "HELD"
    state = Column(Enum(heldStates))
                   #"WAITING", "ACTIVE", "FINISHED", "FAILED"
    creation_date = Column(String)
    
    schedule_begin = Column(String)
    schedule_end = Column(String)
    schedule_expiration = Column(String)
    schedule_refid = Column(String) # "MMCF-HELD"
    junction_list = Column(String) # comma separated list of junctions (id)
    bandwidth_az = Column(Integer)
    bandwidth_za = Column(Integer)
        # multipoint; data = '0,0,0,0,'
        # values = [int(x) for x in data.split(',') if x]
    pce_id = Column(String, ForeignKey("pce.id"))
    fix_a = Column(String) # junction name
    fix_a_ingress = Column(Integer)
    fix_a_egress = Column(Integer)
    fix_a_port_urn = Column(String)
    fix_a_vlan_id = Column(Integer)
    fix_z = Column(String) # junction name
    fix_z_ingress = Column(Integer)
    fix_z_egress = Column(Integer)
    fix_z_port_urn = Column(String)
    fix_z_vlan_id = Column(Integer)

class oSwitch(Base):
    __tablename__ = "switch"

    id = Column(String, primary_key=True) # delta.id:netlab-7750sr12-rt1:9/1/4:port
    deltaid = Column(String) # delta.id
    name = Column(String) # netlab-7750sr12-rt1:9/1/4
    vlanport = Column(Integer)    # 2004
    reservedbw = Column(Integer)
    creation_date = Column(String)
    delta_id = Column(String, ForeignKey("delta.id"))
    active = Column(Integer)  # 0 for inactive 1 for active
    time_begin = Column(String)
    time_end = Column(String)
    heldid = Column(String)


class oDelta(Base):
    __tablename__ = "delta"
    
    id = Column(String, primary_key=True) # delta_id UUID from sense-o
    altid = Column(String) # conn+ id from delta when available
    altvlan = Column(String) # vlan+ part associated with conn+ id from delta when available
    urs = Column(String) # URI string: e.g. resource+links-connection_1
    heldid = Column(String) # from OSCARS id e.g. "MMCF"
    modelid = Column(String) # from the model request
    userid = Column(String) # user ID, owner of the delta
    time_begin = Column(String)
    time_end = Column(String)
    creation_date = Column(String)
    switch_list = Column(String)
    time_history = Column(String)
    held_history = Column(String)
    status = Column(String) # REQUESTED, COMMITTED, CANCELED, EXPIRED
    held_id = Column(String, ForeignKey("held.id"))
    additional_info = Column(String) # for exception string for failed HOLD. keep adding.

class oiDelta(Base):
    __tablename__ = "inactivedelta"

    id = Column(String, primary_key=True) # delta_id UUID from sense-o
    altid = Column(String) # conn+ id from delta when available
    cancelid = Column(String) # conn+ id from delta when cancelled/reduction
    altvlan = Column(String) # vlan+ part associated with conn+ id from delta when available
    urs = Column(String) # URI string: e.g. resource+links-connection_1
    heldid = Column(String) # from OSCARS id e.g. "MMCF"
    modelid = Column(String) # from the model request
    userid = Column(String) # user ID, owner of the delta
    time_begin = Column(String)
    time_end = Column(String)
    creation_date = Column(String)
    active_creation_date = Column(String) # for creation_date when active
    switch_list = Column(String)
    time_history = Column(String)
    held_history = Column(String)
    status = Column(String) # REQUESTED, COMMITTED, CANCELED, EXPIRED
    held_id = Column(String, ForeignKey("held.id"))
    additional_info = Column(String) # for exception string for failed HOLD. keep adding.

class DB(object):
    def __init__(self, config):
        db_type = config["type"]
        db_url = config["url"]
        if db_type != "sqlite":
            url = "://".join((db_type, db_url))
        else:
            url = ":///".join((db_type, db_url))
        self.engine = sqlalchemy.create_engine(url)
        self.Session = sessionmaker(bind=self.engine)

    def initdb(self):
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        s = self.Session()
        try:
            yield s
            s.commit()
        except:
            s.rollback()
            raise
        finally:
            s.close()

def create_userslist(s):
    # id=DN, group="default", role="admin"/"user", active=1
    s.query(oUser).delete() # clean up all
    
    admin_dn = users_config["admin"]
    insert_user(s, admin_dn, "default", "admin", 1) # insert admin
    
    import fileinput
    input_file = users_config["mapfile"]
    fi = fileinput.FileInput(input_file)
    line1 = fi.readline()
    while line1:
        #utils.nprint("line="+line1)
        parsed1 = line1.split('"')
        if (nrm_config["debug"]>0): 
            utils.nprint("USER_INSERT: " + parsed1[1] + "=" + parsed1[2].strip() + "=")
        insert_user(s, parsed1[1], parsed1[2].strip(), "user", 1)
        line1 = fi.readline()
    if (nrm_config["debug"]>0): utils.nprint("Created USER_LIST successfully")

def initialize_db():
    global initDone
    if (initDone):
        if (nrm_config["debug"]>0): 
            utils.nprint("Created/Opened database already")
            utils.nprint("Init database already done")
    else:
        initDone=True
        if (nrm_config["debug"]>0): utils.nprint("Init database")
        db_config = nrmdb_config
        global database
        database = DB(db_config)
        database.initdb()
        global db_session
        db_session = database.session
    
        mytoken=""
        userid=""
        password=""
        mydn = ""
    
        if oscars_config["default_token"] == None:
            raise Exception('Cannot get oscars_config["default_token"]. Edit sensenrm_config.py for oscars_config.default_token')
        else:
            mytoken = oscars_config["default_token"]
        if oscars_config["default_user"] == None:
            raise Exceptoin('Cannot get oscars_config["default_user"]. Edit sensenrm_config.py for oscars_config.default_user')
        else:
            userid = oscars_config["default_user"]
        if oscars_config["default_passwd"] == None:
            utils.nprint('Cannot get oscars_config["default_passwd"]. Edit sensenrm_config.py for oscars_config.default_passwd')
            password = ""
        else:
            password = oscars_config["default_passwd"]
        if oscars_config["default_dn"] == None:
            utils.nprint('Cannot get oscars_config["default_dn"]. Edit sensenrm_config.py for oscars_config.default_dn')
            mydn = ""
        else:
            mydn = oscars_config["default_dn"]
    
        with db_session() as s:
            mObj = s.query(nrmSys).filter(nrmSys.id == "default").first()
            last_time = datetime.now()
            if mObj is None:
                ns  = nrmSys(id="default", last_model_time=last_time, model_changed=1, last_id="", last_href="", last_creationtime="", last_model="") 
                s.add(ns)
            else:
                mObj.last_model_time = last_time
                mObj.model_changed = 1
                s.add(mObj)
            s.commit()

            insert_group(s, "default", userid, password, mytoken, mydn)
            create_userslist(s)  ## Creating users list with mapfile
    
        if (nrm_config["debug"]>0): utils.nprint("Created/Opened database successfully")

def deactivate_user(s, uid):
    insert_user_value(s, uid, "active", 0)

def activate_user(s, uid):
    insert_user_value(s, uid, "active", 1)
    
def get_sys_lasttime(s):
    mObj = s.query(nrmSys).filter(nrmSys.id == "default").first()
    if mObj is None:
        raise ValueError("DB: NO nrmSys found.")
    return mObj.last_model_time

def get_sys_lastmodel(s):
    mObj = s.query(nrmSys).filter(nrmSys.id == "default").first()
    if mObj is None:
        raise ValueError("DB: NO nrmSys found.")
    return mObj.last_id, mObj.last_href, mObj.last_creationtime, mObj.last_model

def get_sys_lastchange(s):
    mObj = s.query(nrmSys).filter(nrmSys.id == "default").first()
    if mObj is None:
        raise ValueError("DB: NO nrmSys found.")
    return mObj.model_changed

def update_sys_value(s, key, value):
    mObj = s.query(nrmSys).filter(nrmSys.id == "default").first()
    if mObj is None:
        raise ValueError("DB: NO nrmSys found.")

    if (key.lower() == "last_model_time"):
        mObj.last_model_time = value  # DateTime e.g. datetime.now()
    elif (key.lower() == "last_model"):
        mObj.last_model = value
    elif (key.lower() == "last_id"):
        mObj.last_id = value
    elif (key.lower() == "last_href"):
        mObj.last_href = value
    elif (key.lower() == "last_creationtime"):
        mObj.last_creationtime = value
    elif (key.lower() == "model_changed"):
        mObj.model_changed = value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: nrmSys key not found: ", key)
        return "sys key not found"
    s.add(mObj)
    s.commit()

def update_switch(s, did, flag):
    if (nrm_config["debug"]>6): utils.nprint("DB: UPDATE_SWITCH=", did)
    mObjs = s.query(oSwitch).filter(oSwitch.deltaid == did).all()
    if mObjs is None:
        if (nrm_config["debug"]>6): utils.nprint("DB: NO Switches for DELTAID=", did)
    else:
        #if (nrm_config["debug"]>6): utils.nprint("DB: Switch exists=", end=' ') 
        if (nrm_config["debug"]>6): utils.nprint("DB: Switch exists=") 
        for mObj in mObjs:
            mObj.active = flag
            s.add(mObj)
        s.commit()


def insert_switch(s, did, swn, vport, bw, st, et, connid):
    if (nrm_config["debug"]>6): utils.nprint("DB: INSERT_SWITCH indented_show")
    swid = did + ":" + swn + ":" + str(vport)

    mObj = s.query(oSwitch).filter(oSwitch.id == swid).first()
    if mObj is None:
        #timenow = str(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00"
        timenow = str(datetime.now(utc))
        oj = oSwitch(id=swid, deltaid=did, name=swn, vlanport=vport, reservedbw=bw, creation_date=timenow, active=0, time_begin=st, time_end=et, heldid=connid)
        s.add(oj)
        s.commit()
        if (nrm_config["debug"]>9): utils.nprint("DB: switch added=", swn, "=", swid)
    else:
        if (nrm_config["debug"]>9): utils.nprint("DB:A switch exists=", swn, "=", swid)

def insert_switch_value(s, id, key, value):
    mObj = s.query(oSwitch).filter(oSwitch.id == id).first()
    if mObj is None:
        raise ValueError("DB: No switch id found.")
            
    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "deltaid"):
        mObj.deltaid = value
    elif (key.lower() == "heldid"):
        mObj.heldid = value
    elif (key.lower() == "name"):
        mObj.name = value
    elif (key.lower() == "vlanport"):
        mObj.vlanport = value
    elif (key.lower() == "reservedbw"):
        mObj.reservedbw = value
    elif (key.lower() == "creation_date"):
        mObj.creation_date = value
    elif (key.lower() == "delta_id"):
        mObj.delta_id = value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: switch key not found: ", key)
        return "switch key not found"
    s.add(mObj)
    s.commit()


def insert_delta(s, uid, did, mid, swns, tstart, tend, aid, avlan, durs, hldid):
    if (nrm_config["debug"]>4): utils.nprint("DB: INSERT_DELTA")

    mObj = s.query(oDelta).filter(oDelta.id == did).first()
    if mObj is None:
        #timenow = datetime.utcnow()
        timenow = str(datetime.now(utc))
        oj = oDelta(id=did, modelid=mid, userid=uid, time_begin=tstart, time_end=tend, creation_date=timenow, switch_list=swns, altid=aid, altvlan=avlan, urs=durs, status="REQUESTED", heldid=hldid)
        s.add(oj)
        s.commit()
        if (nrm_config["debug"]>6): utils.nprint("DB: delta added=", did)
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: delta exists=", did)

def insert_idelta_remove_delta(s, did, cancelled, cid):
    if (nrm_config["debug"]>4): utils.nprint("DB: INSERT_INACTIVE_DELTA")

    mObj = s.query(oDelta).filter(oDelta.id == did).first()
    if mObj is None:
        if (nrm_config["debug"]>6): utils.nprint("DB: active delta NOT_FOUND=", did)
    else:
        # Cancel equivalent
        update_switch(s, did, 0)
        remove_junction_bidports_with_delta(s, did)

        miObj = s.query(oiDelta).filter(oiDelta.id == did).first()
        if miObj is None:
            #timenow = datetime.utcnow()
            timenow = str(datetime.now(utc))
            mystatus = "CANCELLED"
            if not cancelled: 
                mystatus = "EXPIRED"
            oj = oiDelta(id=did, modelid=mObj.modelid, userid= mObj.userid, time_begin=mObj.time_begin, time_end=mObj.time_end, creation_date=timenow, active_creation_date=mObj.creation_date, switch_list=mObj.switch_list, altid=mObj.altid, altvlan=mObj.altvlan, heldid=mObj.heldid, urs=mObj.urs, status=mystatus, additional_info=mObj.additional_info)
            oj.held_history = mObj.heldid
            timehistory = mObj.time_begin + ":" + mObj.time_end
            oj.time_history = timehistory
            if cancelled: 
                oj.cancelid = cid
            s.add(oj)
            if (nrm_config["debug"]>6): utils.nprint("DB: inactive delta added=", did)
        else:
            if (nrm_config["debug"]>6): utils.nprint("DB: inactive delta exists=", did)
            #timenow = datetime.utcnow()
            timenow = str(datetime.now(utc))
            #creation_date = creation_date + ":" + timenow
            #active_creation_date = active_creation_date + ":" + mObj.creation_date
            #heldhistory = miObj.held_history + "," + mObj.heldid
            #miObj.held_history = heldhistory
            #timehistory = miObj.time_history + "," + mObj.time_begin + ":" + mObj.time_end
            #miObj.time_history = timehistory
            #if cancelled: 
            #    miObj.status = "CANCELLED"
            #    miObj.cancelid = cid
            #else:
            #    miObj.status = "EXPIRED"
            #s.add(miObj)

            mystatus = "CANCELLED"
            if not cancelled: 
                mystatus = "EXPIRED"

            # with new ID, always add to oiDelta list
            did_new = did+str(":")+str(mObj.altid)
            oj = oiDelta(id=did, modelid=mObj.modelid, userid= mObj.userid, time_begin=mObj.time_begin, time_end=mObj.time_end, creation_date=timenow, active_creation_date=mObj.creation_date, switch_list=mObj.switch_list, altid=mObj.altid, altvlan=mObj.altvlan, heldid=mObj.heldid, urs=mObj.urs, status=mystatus, additional_info=mObj.additional_info)
            oj.held_history = mObj.heldid
            timehistory = mObj.time_begin + ":" + mObj.time_end
            oj.time_history = timehistory
            if cancelled: 
                oj.cancelid = cid

            try:
                s.add(oj)
            except Exception as e:
                if (nrm_config["debug"]>0): utils.nprint("DB: INACTIVE_DELTA EXCEPT: ", e)
            if (nrm_config["debug"]>6): utils.nprint("DB: inactive delta exists_added=", did_new)

        # Delete from the active deltas list
        s.delete(mObj)
        s.commit()
        # notify model change
        #update_sys_value(s, "model_changed", 1)

def convert_str_to_datetime(mystr):
    if (nrm_config["debug"]>6): utils.nprint("DB: convert_time: ", mystr)
    date_with_tz = mystr
    date_str, tz = date_with_tz[:-5], date_with_tz[-5:]
    dt_utc = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
    dt = dt_utc.replace(tzinfo=FixedOffset(tz))
    return dt

# t0="2019-01-08T20:02:25.027-0500"
# tx=convert_str_to_datetime(t0)
# tx= 2019-01-08T20:02:25.027000-05:00
# t1=datetime.now(utc)
# t1= 2019-01-09 01:05:28.958184+00:00
# t1-tx= 183.931184
def get_time_diff(time_to_compare, current_time): 
    td = convert_str_to_datetime(time_to_compare) - current_time
    return td.total_seconds()

def remove_expired_deltas(s):
    allDeltas = s.query(oDelta).all()
    if len(allDeltas) > 0:
        if (nrm_config["debug"]>6): utils.nprint("DB: REMOVE_EXPIRED_DELTAS")
        current_time = datetime.now(utc)
        if (nrm_config["debug"]>6):
            utils.nprint("DB: IS_EXPIRED_NOWTIME=", current_time)
        modelUpdated=False
        for f in allDeltas:
            tdiff = get_time_diff(f.time_end, current_time)
            #if (nrm_config["debug"]>4):
                #utils.nprint("DB: IS_EXPIRED_DELTAID=", f.id)
                #utils.nprint("DB: IS_EXPIRED_ENDTIME=", f.time_end)
                #utils.nprint("DB: IS_EXPIRED_DIFFTIME=",tdiff)
            if (tdiff < 0): # expired
                if (nrm_config["debug"]>3):
                    utils.nprint("DB: IS_EXPIRED_TDIFF=", tdiff)
                    utils.nprint("DB: IS_EXPIRED_REMOVE=", f.id)
                    utils.nprint("DB: IS_EXPIRED_ENDTIME=", f.time_end)
                insert_idelta_remove_delta(s, f.id, False, "")
                modelUpdated=True
            elif (f.status == "REQUESTED"):
                tdiff2 = abs(get_time_diff(f.time_begin, current_time))
                if (tdiff2 > 900):
                    if (nrm_config["debug"]>3):
                        utils.nprint("DB: IS_EXPIRED_FROM_HELD_TDIFF2=", tdiff2)
                        utils.nprint("DB: IS_EXPIRED_FROM_HELD_REMOVE=", f.id)
                        utils.nprint("DB: IS_EXPIRED_FROM_HELD_BEGINTIME=", f.time_begin)
                    insert_idelta_remove_delta(s, f.id, False, "")
                    modelUpdated=True
        if (modelUpdated):
            update_sys_value(s, "model_changed", 1)
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: REMOVE_EXPIRED_DELTAS NO_ACTIVE_DELTAS")

def remove_expired_delta(s, did):
    if (nrm_config["debug"]>6): utils.nprint("DB: REMOVE_EXPIRED_DELTA:", did)
    resp_status = False
    mObj = s.query(oDelta).filter(oDelta.id == did).first()
    if mObj is None:
        if (nrm_config["debug"]>6): utils.nprint("DB: REMOVE_EXPIRED_DELTA NOT_FOUND:", did)
    else:
        current_time = datetime.now(utc)
        time_to_compare = mObj.time_end
        if (nrm_config["debug"]>6):
            utils.nprint("DB: IS2_EXPIRED_NOWTIME=", current_time)
            utils.nprint("DB: IS2_EXPIRED_ENDTIME=", time_to_compare)
        #tdiff = current_time - convert_str_to_datetime(time_to_compare)
        tdiff = get_time_diff(time_to_compare, current_time)
        #if (nrm_config["debug"]>4):
            #utils.nprint("DB: IS2_EXPIRED_DELTAID=", mObj.id)
            #utils.nprint("DB: IS2_EXPIRED_ENDTIME=", time_to_compare)
            #utils.nprint("DB: IS2_EXPIRED_DIFFTIME=",tdiff)
        if (tdiff < 0): # expired
            if (nrm_config["debug"]>3):
                utils.nprint("DB: IS2_EXPIRED_TDIFF=", tdiff)
                utils.nprint("DB: IS2_EXPIRED_REMOVE=", mObj.id)
                utils.nprint("DB: IS2_EXPIRED_ENDTIME=", time_to_compare)
            insert_idelta_remove_delta(s, mObj.id, False, "")
            resp_status = True
            update_sys_value(s, "model_changed", 1)
        elif (mObj.status == "REQUESTED"):
            tdiff2 = abs(get_time_diff(mObj.time_begin, current_time))
            if (tdiff2 > 900):
                if (nrm_config["debug"]>3):
                    utils.nprint("DB: IS_EXPIRED_FROM_HELD_TDIFF2=", tdiff2)
                    utils.nprint("DB: IS_EXPIRED_FROM_HELD_REMOVE=", mObj.id)
                    utils.nprint("DB: IS_EXPIRED_FROM_HELD_BEGINTIME=", mObj.time_begin)
                insert_idelta_remove_delta(s, mObj.id, False, "")
                resp_status = True
                update_sys_value(s, "model_changed", 1)
    return resp_status    

def is_delta_active(s, did, checkInactive):
    if (nrm_config["debug"]>6): utils.nprint("DB: delta_search:", did)
    activestatus = False
    mObj = s.query(oDelta).filter(oDelta.id == did).first()
    if mObj is None:
        maObj = s.query(oDelta).filter(oDelta.altid == did).first()
        if maObj is None:
            if (checkInactive):
                miObj = s.query(oiDelta).filter(oiDelta.id == did).first()
                if miObj is None:
                    maiObj = s.query(oiDelta).filter(oiDelta.altid == did).first()
                    if maiObj is None:
                        if (nrm_config["debug"]>6): utils.nprint("DB::delta_search:NOTFOUND:", did,"=",activestatus)
                else:
                    activestatus = False
                    if (nrm_config["debug"]>6): utils.nprint("DB::delta_search:INACT:", did,"=",activestatus)
            else:
                if (nrm_config["debug"]>6): utils.nprint("DB::delta_search:NOTFOUND:", did,"=",activestatus)
                
        else:
            expired_status = remove_expired_delta(s, maObj.id)
            if (not expired_status):
                activestatus = True
            if (nrm_config["debug"]>6): utils.nprint("DB::delta_search:ALT:", did,"=",activestatus)
    else:
        expired_status = remove_expired_delta(s, mObj.id)
        if (not expired_status):
            activestatus = True
        if (nrm_config["debug"]>6): utils.nprint("DB::delta_search:ACT", did,"=",activestatus)
    return activestatus

def get_all_active_deltas(s, uid):
    allDeltas = s.query(oDelta).all()
    allids = ""
    myids = ""
    if len(allDeltas) > 0:
        isadmin = is_admin(s, uid)
        if isadmin:
            for f in allDeltas:
                #allids = allids + f.id
                # 210916 for complete info
                allids = allids + "id=" + f.id + " oscarsid=" + f.heldid + " created=" + f.creation_date + " switchlist=" + f.switch_list + " status=" + f.status
                if allDeltas.index(f) != len(allDeltas)-1:
                    allids = allids + ','
            if (nrm_config["debug"]>6): utils.nprint("DB::all_active_deltas_admin=", allids)
            return allids
        else:
            for f in allDeltas:
                if (f.userid == uid):
                    #myids = myids + f.id
                    # 210916 for complete info
                    myids = myids + "id=" + f.id + " oscarsid=" + f.heldid + " created=" + f.creation_date + " switchlist=" + f.switch_list + " status=" + f.status
                    if allDeltas.index(f) != len(allDeltas)-1:
                        myids = myids + ','
            if (nrm_config["debug"]>6): utils.nprint("DB::all_active_deltas_user=", myids)
            return myids
    return myids


def insert_delta_value(s, id, key, value):
    mObj = s.query(oDelta).filter(oDelta.id == id).first()
    # mObj = s.query(oDelta).filter(oDelta.id == id).order_by(oDelta.creation_date.desc()).first()
    if mObj is None:
        raise ValueError("DB: No delta id found.")
        
    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "status"):
        mObj.status = value
    elif (key.lower() == "altid"):
        mObj.altid = value
    elif (key.lower() == "altvlan"):
        mObj.altvlan = value
    elif (key.lower() == "heldid"):
        mObj.heldid = value
    elif (key.lower() == "modelid"):
        mObj.modelid = value
    elif (key.lower() == "userid"):
        mObj.userid = value
    elif (key.lower() == "time_begin"):
        mObj.time_begin = value
    elif (key.lower() == "time_end"):
        mObj.time_end = value
    elif (key.lower() == "creation_date"):
        mObj.creation_date = value
    elif (key.lower() == "switch_list"):
        mObj.switch_list = value
    elif (key.lower() == "held_id"):
        mObj.held_id = value
    elif (key.lower() == "additional_info"):
        if len(mObj.additional_info) == 0:
            mObj.additional_info =  value 
        else: 
            mObj.additional_info =  mObj.additional_info + ", " + value 
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: delta key not found: ", key)
        return "delta key not found"
    s.add(mObj)
    s.commit()

def validate_user(s, uid):
    if (nrm_config["debug"]>6): utils.nprint("DB: Validate_user: ", uid)
    mObj = s.query(oUser).filter(oUser.id == uid).first()
    if mObj is not None:
        if (nrm_config["debug"]>6): utils.nprint("DB: User found: ", mObj.id)
        return True
    else:
        return False

def get_user(s, uid):
    if (nrm_config["debug"]>6): utils.nprint("DB: Get_user: ", uid)
    mObj = s.query(oUser).filter(oUser.id == uid).first()
    if mObj is not None:
        if (nrm_config["debug"]>6): utils.nprint("DB: User found: ", mObj.id)
        return mObj
    else:
        return None

def is_admin(s, uid):
    if (nrm_config["debug"]>6): utils.nprint("DB: Is_admin: ", uid)
    mObj = s.query(oUser).filter(oUser.id == uid).first()
    if mObj is None:
        return False
    else:
		#if (nrm_config["debug"]>6): utils.nprint("DB: User found: ", mObj.id)
        if (mObj.role == "admin"):
            return True
        else:
            return False

def get_user_group(s, uid):
    if (nrm_config["debug"]>6): utils.nprint("DB: Get_user_group: ", uid)
    mObj = s.query(oUser).filter(oUser.id == uid).first()
    if mObj is not None:
        if (nrm_config["debug"]>6): utils.nprint("DB: User found: ", mObj.id)
        return mObj.group
    else:
        return None

def insert_user(s, uid, group, role, active):
    mObj = s.query(oUser).filter(oUser.id == uid).first()
    current_time = str(datetime.now())
    if mObj is None:
        u = oUser(id=uid, group=group, active=active, role=role, last_updated=current_time)
        s.add(u)
        s.commit()
        if (nrm_config["debug"]>6): utils.nprint("DB: user added=", uid)
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: user exists=", uid)
        mObj.group = group
        mObj.active = active
        mObj.role = role
        mObj.last_updated = current_time
        s.add(mObj)
        s.commit()
        
def insert_user_value(s, id, key, value):
    mObj = s.query(oUser).filter(oUser.id == id).first()
    if mObj is None:
        raise ValueError("No user id found.")

    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "group"):
        mObj.group = value
    elif (key.lower() == "role"):
        mObj.role = value
    elif (key.lower() == "active"):
        mObj.active = value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: User ID not found: ", key)
        return "User ID not found"
    mObj.last_updated =  str(datetime.now())
    s.add(mObj)
    s.commit()

def get_group(s, gid):
    if (nrm_config["debug"]>6): utils.nprint("DB: Group query: ", gid)
    mObj = s.query(oGroup).filter(oGroup.id == gid).first()
    if mObj is not None:
        if (nrm_config["debug"]>6): utils.nprint("DB: Group found: ", mObj.id)
        return mObj
    else:
        return None

def get_group_token(s, gid):
    if (nrm_config["debug"]>6): utils.nprint("DB: Group_token_query: ", gid)
    mObj = s.query(oGroup).filter(oGroup.id == gid).first()
    if mObj is not None:
        if (nrm_config["debug"]>6): utils.nprint("DB: Group found: ", mObj.id)
        return mObj.code
    else:
        return None

def insert_group(s, gid, login, passwd, code, dn):
    mObj = s.query(oGroup).filter(oGroup.id == gid).first()
    if mObj is None:
        u = oGroup(id=gid, login=login, passwd=passwd, dn=dn, code=code)
        s.add(u)
        s.commit()
        if (nrm_config["debug"]>6): utils.nprint("DB: Group added=", gid, "=", u.id)
    else:
        # Updating the group info
        if (nrm_config["debug"]>6): utils.nprint("DB: Group exists=", gid, "=", mObj.id)
        mObj.login = login
        mObj.passwd = passwd
        mObj.dn = dn
        mObj.code = code
        s.add(mObj)
        s.commit()
        
def insert_group_value(s, id, key, value):
    mObj = s.query(oGroup).filter(oGroup.id == id).first()
    if mObj is None:
        raise ValueError("No Group id found.")

    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "login"):
        mObj.login = value
    elif (key.lower() == "passwd"):
        mObj.passwd = value
    elif (key.lower() == "token"):
        mObj.token = value
    elif (key.lower() == "dn"):
        mObj.dn = value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: key not found: ", key)
        return "Group key not found"
    s.add(mObj)
    s.commit()
    
def insert_conn(s, cid, user=None):
    mObj = s.query(oConnID).filter(oConnID.id == cid).first()
    if mObj is None:
        #creationdate = str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00"
        creationdate = str(datetime.now(utc))
        if (nrm_config["debug"]>6): utils.nprint("DB: creationdate=", creationdate)
        u = oConnID(id=cid, userid=user, name=None, creation_date=creationdate, mode=connModes.created)
        s.add(u)
        s.commit()
        if (nrm_config["debug"]>6): utils.nprint("DB: connection added=", cid, "=", u.id)
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: connection exists=", cid, "=", mObj.id)

def update_conn(s, cid, key, value):
    mObj = s.query(oConnID).filter(oConnID.id == cid).first()
    if mObj is None:
        raise ValueError("No ConnectionID found.")

    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "user"):
        mObj.userid = value
    elif (key.lower() == "name"):
        mObj.name = value
    elif (key.lower() == "mode"):
        mObj.mode = value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: ConnectionID not found: ", key)
        return "ConnectionID not found"
    s.add(mObj)
    s.commit()

def insert_junction(s, mj):    
    if (nrm_config["debug"]>9): 
        utils.nprint("DB: INSERT_JUNCTION indented_show")
        mj.indented_show()
        utils.nprint("DB: INSERT_JUNCTION indented_show DONE")
    mObj = s.query(oJunction).filter(oJunction.id == mj.junction_name).first()
    if mObj is None:
        oj = oJunction(id=mj.junction_name, name=mj.junction_name, port_urn=mj.port_urn, vlan_expression=mj.vlanExpression, ingress_bandwidth=mj.ingressBandwidth, egress_bandwidth=mj.egressBandwidth, bidports="")
        s.add(oj)
        s.commit()
        if (nrm_config["debug"]>9): utils.nprint("DB: junction added=", mj.junction_name, "=", oj.id)
    else:
        if (nrm_config["debug"]>9): utils.nprint("DB: junction exists=", mj.junction_name, "=", mObj.id)
        mObj.port_urn = mj.port_urn
        mObj.vlan_expression = mj.vlanExpression
        mObj.ingress_bandwidth = mj.ingressBandwidth
        mObj.egress_bandwidth = mj.egressBandwidth
        s.add(mObj)
        s.commit()

def display_db_junctions(s):
    allJunctions = s.query(oJunction).all();
    if (nrm_config["debug"]>4): utils.nprint("\nDB: num junctions = ", len(allJunctions))
    jDetails = [{"id": f.id, "name": f.name, "port_urn": f.port_urn, "vlan_expression": f.vlan_expression, "ingress_bandwidth": f.ingress_bandwidth, "egress_bandwidth": f.egress_bandwidth } for f in allJunctions]
    if (nrm_config["debug"]>9): print(json.dumps(jDetails, indent = 4))

def display_db_pce(s):
    allPCEs = s.query(oPCE).all();
    if (nrm_config["debug"]>4): utils.nprint("\nDB: num PCEs = ", len(allPCEs))
    jDetails = [{"id": f.id, "time_begin": f.time_begin, "time_end":f.time_end, "evaluated": f.evaluated, "cost": f.cost, "available_az": f.available_az, "available_za": f.available_za, "baseline_az": f.baseline_az, "baseline_za": f.baseline_za, "heldid":f.heldid, "held_id":f.held_id} for f in allPCEs]
    if (nrm_config["debug"]>9): print(json.dumps(jDetails, indent = 4))
    
def display_db_held(s):
    allJunctions = s.query(oJunction).all();
    if (nrm_config["debug"]>4): utils.nprint("\nDB: num junctions = ", len(allJunctions))
    jDetails = [{"id": f.id, "name": f.name, "port_urn": f.port_urn, "vlan_expression": f.vlan_expression, "ingress_bandwidth": f.ingress_bandwidth, "egress_bandwidth": f.egress_bandwidth} for f in allJunctions]
    if (nrm_config["debug"]>9): print(json.dumps(jDetails, indent = 4))
  
def insert_junction_bidports(s, deltaid, plist):
    # plist to be the list of the switches: SWITCHES= [u'wash-cr5:7/1/1:3603', u'chic-cr5:3/2/1:3603']
    # when delta or commit
    # delta_id:junction_id:vlan
    # "netlab-7750sr12-rt2:10/1/5:2210", "netlab-mx960-rt1:xe-11/2/0:2210"
    dbf = False
    for sw in plist:
        jids = sw.split(":")
        jid = jids[0]+":"+jids[1]
        mObj = s.query(oJunction).filter(oJunction.id == jid).first()
        if mObj is not None:
            bports = mObj.bidports.split(",")
            addbp = []
            for sw2 in plist:
                sw3 = deltaid+":"+sw2
                if (sw3 not in bports):
                    addbp.append(sw3)

            newbports = ""
            for bp in addbp:
                newbports = newbports + bp
                if addbp.index(bp) != len(addbp)-1:
                    newbports = newbports + ','

            if len(mObj.bidports) > 0:
                mObj.bidports = mObj.bidports + "," + newbports
            else:
                mObj.bidports = newbports
            s.add(mObj)
            dbf = True
    if dbf:
        s.commit()

def remove_junction_bidports_with_delta(s, nrm_deltaid):
    # When cancelled, only deltaid is available. Get oDelta.switch_list
    # "netlab-7750sr12-rt2:10/1/5:2210,netlab-mx960-rt1:xe-11/2/0:2210"
    mObj = s.query(oDelta).filter(oDelta.id == nrm_deltaid).first()
    if mObj is None:
        raise ValueError("No DeltaID found.")
    if (len(mObj.switch_list) > 0):
        plist = mObj.switch_list.split(",")
        dbf = False
        for sw in plist:
            jids = sw.split(":")
            jid = jids[0]+":"+jids[1]
            mObj = s.query(oJunction).filter(oJunction.id == jid).first()
            if mObj is not None:
                bports = mObj.bidports.split(",")
                for sw2 in plist:
                    sw3 = nrm_deltaid + ":" + sw2
                    if (sw3  in bports):
                        bports.remove(sw3)
                newbports = ""
                for bp in bports:
                    newbports = newbports + bp
                    if bports.index(bp) != len(bports)-1:
                        newbports = newbports + ','
                mObj.bidports = newbports
                s.add(mObj)
                dbf = True
        if (dbf):
            s.commit()
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: REMOVE_JUNCTION NO_SWITCH_LIST")

#def remove_junction_bidports(s, id, plist):
#    # id = junction id
#  # when cancel or commit failed
#    # "netlab-7750sr12-rt2:10/1/5:2210,netlab-mx960-rt1:xe-11/2/0:2210"
#    mObj = s.query(oJunction).filter(oJunction.id == id).first()
#    if mObj is None:
#        raise ValueError("No Junation id found.")
#    bports = mObj.bidports.split(",")
#    for sw in plist:
#        if (sw  in bports):
#            bport.remove(sw)
#    newbports = ""
#    for bp in bports:
#        newbports = newbports + bp
#        if bports.index(bp) != len(bports)-1:
#            newbports = newbports + ','
#    mObj.bidports = newbports
#    s.add(mObj)
#    s.commit()

def insert_junction_value(s, id, key, value):
    mObj = s.query(oJunction).filter(oJunction.id == id).first()
    if mObj is None:
        raise ValueError("No Junction id found.")

    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "name"):
        mObj.name = value
    elif (key.lower() == "port_urn"):
        mObj.port_urn = value
    elif (key.lower() == "vlan_expression"):
        mObj.vlan_expression = value
    elif (key.lower() == "ingress_bandwidth"):
        mObj.ingress_bandwidth = value
    elif (key.lower() == "egress_bandwidth"):
        mObj.egress_bandwidth = value
    elif (key.lower() == "time_begin"):
        mObj.time_begin = value
    elif (key.lower() == "time_end"):
        mObj.time_end = value
    elif (key.lower() == "bidports"):
        bports = mObj.bidports.split(",")
        if (value not in bports): # delta_id:oJunctionID:vlan
            mObj.bidports = mObj.bidports + "," + value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: Junction key not found: ", key)
        return "Junction key not found"
    s.add(mObj)
    s.commit()
    
def insert_pce(s, mj):
    if (nrm_config["debug"]>9): 
        utils.nprint("DB: INSERT_PCE indented_show")
        mj.indented_show()
        utils.nprint("DB: INSERT_PCE indented_show DONE")

    mObj = s.query(oPCE).filter(oPCE.id == mj.id).first()    
    if mObj is None:
        oj = oPCE(id=mj.id, heldid = mj.held_id, time_begin=str(mj.time_begin.strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00", time_end=str(mj.time_end.strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00", pcemode=pceModes.shortest, evaluated=mj.evaluated, cost=mj.cost, ero_az=','.join(mj.azEro), ero_za=','.join(mj.zaEro), available_az=mj.azAvailable, available_za=mj.zaAvailable, baseline_az=mj.azBaseline, baseline_za=mj.zaBaseline);
        s.add(oj)
        if (nrm_config["debug"]>9):
            utils.nprint("DB: PCE added (DeltaID)=", mj.id, "=", oj.id)
            utils.nprint("DB: PCE added (HeldOID)=", mj.held_id, "=", oj.heldid)
            #utils.nprint("DB: PCE DISPLAY")
        s.commit()
        #if (nrm_config["debug"]>9):
        #    utils.nprint("DB: PCE committed1=", mj.id, "=", oj.id)
        #    utils.nprint("DB: PCE committed2=", mj.held_id, "=", oj.heldid)
        #    utils.nprint("DB: PCE committed3=", mj.held_id, "=", oj.held_id)
    else:
        if (nrm_config["debug"]>9):
            utils.nprint("DB: PCE exists1=", mj.id, "=", mObj.id)
            utils.nprint("DB: PCE exists2=", mj.held_id, "=", mObj.heldid)
            utils.nprint("DB: PCE exists3=", mj.held_id, "=", mObj.held_id)
        mObj.time_begin = mj.time_begin
        mObj.time_end = mj.time_end
        mObj.evaluated = mj.evaluated
        mObj.cost = mj.cost
        mObj.ero_a_name = mj.junction_a
        mObj.ero_z_name = mj.junction_b
        mObj.ero_az = ','.join(mj.azEro)
        mObj.ero_za = ','.join(mj.zaEro)
        mObj.available_az = mj.azAvailable
        mObj.available_za  = mj.zaAvailable
        mObj.baseline_az = mj.azBaseline
        mObj.baseline_za = mj.zaBaseline
        mObj.heldid = mj.held_id
        s.add(mObj)
        s.commit()
        if (nrm_config["debug"]>7): utils.nprint("DB: PCE exists. Update done=", mj.time_end, "=", mObj.time_end)

def insert_pce_value(s, id, key, value):
    mObj = s.query(oPCE).filter(oPCE.id == id).first()
    if mObj is None:
        raise ValueError("No PCE id found.")

    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "time_begin"):
        mObj.time_begin = value
    elif (key.lower() == "time_end"):
        mObj.time_end = value
    elif (key.lower() == "evaluated"):
        mObj.evaluated = value
    elif (key.lower() == "pcemode"):
        mObj.pcemode = value
    elif (key.lower() == "cost"):
        mObj.cost = value
    elif (key.lower() == "ero_a_name"):
        mObj.ero_a_name = value
    elif (key.lower() == "ero_z_name"):
        mObj.ero_z_name = value
    elif (key.lower() == "ero_az"):
        mObj.ero_az = value
    elif (key.lower() == "ero_za"):
        mObj.ero_za = value
    elif (key.lower() == "available_az"):
        mObj.available_az = value
    elif (key.lower() == "available_za"):
        mObj.available_za = value
    elif (key.lower() == "baseline_az"):
        mObj.baseline_az = value
    elif (key.lower() == "baseline_za"):
        mObj.baseline_za = value
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: PCE key not found: ", key)
        return "PCE key not found"
    s.add(mObj)
    s.commit()
    
def insert_held(s, id, heldmode=None, description=None, userid=None, phase=None, state=None):
    mObj = s.query(oHeld).filter(oHeld.id == id).first()
    if mObj is None:
        if heldmode is None:
            heldmode = heldModes.automatic    # manual
        if description is None:
            description = id
        if userid is None:
            userid = ""
        if phase is None:
            phase = sensenrm_oscars.heldPhases.held            
        if state is None:
            state = sensenrm_oscars.heldStates.active
        #creationdate = str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00"
        creationdate = str(datetime.now(utc))
        
        ohld = oHeld(id=id, heldmode=heldmode, description=description, userid=userid, phase=phase, state=state, creation_date=creationdate);
                
        s.add(ohld)
        s.commit()
        if (nrm_config["debug"]>6): utils.nprint("DB: Held added=", id, "=", ohld.id)
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: Held exists=", id, "=", mObj.id)        

def update_held(s, id, heldmode=None, description=None, userid=None, phase=None, state=None, schedule_begin=None, schedule_end=None, schedule_expiration=None, schedule_refid=None, bandwidth_az=0, bandwidth_za=0, fix_a=None, fix_a_ingress=0, fix_a_egress=0, fix_a_port_urn=None, fix_a_vlan_id=0, fix_z=None, fix_z_ingress=0, fix_z_egress=0, fix_z_port_urn=None, fix_z_vlan_id=0):
    mObj = s.query(oHeld).filter(oHeld.id == id).first()
    if mObj is not None:
        if heldmode is None:
            mObj.heldmode = heldmode
        if description is None:
            mObj.description = description
        if userid is None:
            mObj.userid = userid
        if phase is None:
            mObj.phase = phase
        if state is None:
            mObj.state = state
        if schedule_begin is None:
            mObj.schedule_begin = str(schedule_begin.strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00"
        if schedule_end is None:
            mObj.schedule_end = str(schedule_end.strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00"
        if schedule_expiration is None:
            mObj.schedule_expiration = str(schedule_expiration.strftime('%Y-%m-%dT%H:%M:%S.%f'))+"-07:00"
        if schedule_refid is None:
            mObj.schedule_refid = schedule_refid
        if bandwidth_az != 0:
            mObj.bandwidth_az = bandwidth_az
        if bandwidth_za != 0:
            mObj.bandwidth_za = bandwidth_za
        if fix_a is None:
            mObj.fix_a = fix_a
        if fix_a_ingress != 0:
            mObj.fix_a_ingress = fix_a_ingress
        if fix_a_egress != 0:
            mObj.fix_a_egress = fix_a_egress
        if fix_a_port_urn is None:
            mObj.fix_a_port_urn = fix_a_port_urn
        if fix_a_vlan_id != 0:
            mObj.fix_a_vlan_id = fix_a_vlan_id
        if fix_z is None:
            mObj.fix_z = fix_z
        if fix_z_ingress != 0:
            mObj.fix_z_ingress = fix_z_ingress
        if fix_z_egress != 0:
            mObj.fix_z_egress = fix_z_egress
        if fix_z_port_urn is None:
            mObj.fix_z_port_urn = fix_z_port_urn
        if fix_z_vlan_id != 0:
            mObj.fix_z_vlan_id = fix_z_vlan_id
        s.add(mObj)
        s.commit()
        if (nrm_config["debug"]>6): utils.nprint("DB: Held updated=", id, "=", mObj.id)
    else:
        if (nrm_config["debug"]>6): utils.nprint("DB: Held does not exists=", id, "=", id)        

def insert_held_value(s, id, key, value):
    mObj = s.query(oHeld).filter(oHeld.id == id).first()
    if mObj is None:
        if (nrm_config["debug"]>6): utils.nprint("DB: Held does not exists=", id, "=", id)
        raise ValueError("No Held id found.")

    if (key.lower() == "id"):
        mObj.id = value
    elif (key.lower() == "heldmode"):
        mObj.heldmode = value
    elif (key.lower() == "description"):
        mObj.description = value
    elif (key.lower() == "userid"):
        mObj.userid = value
    elif (key.lower() == "phase"):
        mObj.phase = value
    elif (key.lower() == "state"):
        mObj.state = value
    elif (key.lower() == "schedule_begin"):
        mObj.schedule_begin = value
    elif (key.lower() == "schedule_end"):
        mObj.schedule_end = value
    elif (key.lower() == "schedule_expiration"):
        mObj.schedule_expiration = value
    elif (key.lower() == "schedule_refid"):
        mObj.schedule_refid = value
    elif (key.lower() == "bandwidth_az"):
        mObj.bandwidth_az = value
    elif (key.lower() == "bandwidth_za"):
        mObj.bandwidth_za = value
    elif (key.lower() == "fix_a"):
        mObj.fix_a = value
    elif (key.lower() == "fix_a_ingress"):
        mObj.fix_a_ingress = value
    elif (key.lower() == "fix_a_egress"):
        mObj.fix_a_egress = value
    elif (key.lower() == "fix_a_port_urn"):
        mObj.fix_a_port_urn = value
    elif (key.lower() == "fix_a_vlan_id"):
        mObj.fix_a_vlan_id = value
    elif (key.lower() == "fix_z"):
        mObj.fix_z = value
    elif (key.lower() == "fix_z_ingress"):
        mObj.fix_z_ingress = value
    elif (key.lower() == "fix_z_egress"):
        mObj.fix_z_egress = value
    elif (key.lower() == "fix_z_port_urn"):
        mObj.fix_z_port_urn = value
    elif (key.lower() == "fix_z_vlan_id"):
        mObj.fix_z_vlan_id = value
        if (nrm_config["debug"]>6): utils.nprint("DB: Held key not found: ", key)
        return "Held key not found"
    s.add(mObj)
    s.commit()
    if (nrm_config["debug"]>6): utils.nprint("DB: Held updated=", id, "=", mObj.id)
    
def display_db(s):
    allJunctions = s.query(oJunction).all();
    if (nrm_config["debug"]>7): utils.nprint("\nDB: num junctions = ", len(allJunctions))
    jDetails = [{"id": f.id, "name": f.name, "port_urn": f.port_urn, "vlan_expression": f.vlan_expression, "ingress_bandwidth": f.ingress_bandwidth, "egress_bandwidth": f.egress_bandwidth} for f in allJunctions]
    if (nrm_config["debug"]>9): print(json.dumps(jDetails, indent = 4))

    allHelds = s.query(oHeld).all();
    if (nrm_config["debug"]>7): utils.nprint("\nDB: num helds = ", len(allHelds));
    hDetails = [{"id": t.id, "id_name": t.pipe_a.id, "name": t.pipe_a.name, "vlan_expression":t.pipe_a.vlan_expression} for t in allHelds]
    if (nrm_config["debug"]>9): print(json.dumps(hDetails, indent = 4))
    if (nrm_config["debug"]>7): utils.nprint("DB: Printed database successfully")

