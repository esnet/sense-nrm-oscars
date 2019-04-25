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
## NRM Delta Request Handle

from datetime import tzinfo, timedelta, datetime
import time
import uuid
import sys
import os
import fileinput
import pytz
from wsgiref.handlers import format_date_time
from time import mktime
import dateutil.parser
import rdflib
import sensenrm_oscars
import sensenrm_db
import sensenrm_cancel
import json

from sensenrm_config import log_config, nrm_config, nrm_service

oscars_conn = sensenrm_oscars.nrm_oscars_connection()
mydb_session = sensenrm_db.db_session
nrmcancel = sensenrm_cancel.nrmCancel()

class delta_switch(object):
    id = "" # (switch.id)
    deltaid = ""
    modelid = ""
    reservedbw = 0
    vlanport = 0

    def __init__(self, sid, did, mid, bw, vport):
        self.id = sid
        self.deltaid = did
        self.modelid = mid
        self.reservedbw = bw
        self.vlanport = vport

    def assign(self, key, value):
        if (key.lower() == "id"):
            self.id = value
        elif (key.lower() == "deltaid"):
            self.deltaid = value
        elif (key.lower() == "modelid"):
            self.modelid = value
        elif (key.lower() == "reservedbw"):
            self.reservedbw = value
        elif (key.lower() == "vlanport"):
            self.vlanport = value
        else:
            return "Held key not found: ", key, ", ", value

class nrmDelta(object):
    basePath = log_config["basepath"]
    
    def __init__(self):
        self.obj=" "
        import os
        if not os.path.exists(self.basePath):
            os.makedirs(self.basePath)

    def getUUID(self):
        nrmdelta_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "nrmdelta")
        return nrmdelta_uuid
        
    def getURL(self):
        nrmdelta_url = 'https://' + nrm_config["host"] + ':' + str(nrm_config["port"]) + '/sense-rm/api/sense/v1/deltas/' + str(self.getUUID())
        return nrmdelta_url
        
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

    def time_rfc1123(self):
        now = datetime.now()
        stamp = mktime(now.timetuple())
        rfc1123_time = format_date_time(stamp)
        return rfc1123_time

    def time_rfc1123_from_datetime(self, dt):
        udt = dt.astimezone(pytz.utc)
        local_tz = pytz.timezone('US/Pacific')
        local_dt = udt.replace(tzinfo=pytz.utc).astimezone(local_tz)
        stamp = mktime(local_dt.timetuple())
        rfc1123_time = format_date_time(stamp)
        return rfc1123_time

    def time_iso8601(self, dt):
        """YYYY-MM-DDThh:mm:ssTZD (1997-07-16T19:20:30-03:00)"""
        if dt is None:
            return ""
        fmt_datetime = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        tz = dt.utcoffset()
        if tz is None:
            fmt_timezone = "-0000"
        else:
            fmt_timezone = "-0000"
        return fmt_datetime + fmt_timezone

    def get_delayed_time(self, delay_hours):
        mytime1=datetime.now(self.utc)
        if delay_hours != 0:
            adays = int((mytime1.hour+delay_hours) / 24)
            amonth=0
            year=0
            days=0
            months=0
            daycomp = 30
            if (mytime1.month == 2):
                daycomp = 28
            if (mytime1.day+adays > daycomp):
                amonth=1
                days=mytime1.day + adays - daycomp
            else:
                days=mytime1.day + adays
            if ((mytime1.month+amonth) > 12):
                year=1
                months = mytime1.month + amonth - 12
            else:
                months = mytime1.month + amonth
            hours = delay_hours - 24*(int(delay_hours/24))
            if (nrm_config["debug"]>7):
                print "DELTA: DELAYED time=", mytime1.hour
                print "DELTA: DELAYED input=", delay_hours
                print "DELTA: DELAYED days=", days
                print "DELTA: DELAYED hours=", hours
            mytime1=datetime(mytime1.year+year, months, days, mytime1.hour+hours, mytime1.minute, mytime1.second, tzinfo=self.utc)
        return mytime1

    def get_delayed_time_5min(self):
        mytime1=datetime.now(self.utc)
        hours = int((mytime1.minute+3) / 60)
        if hours > 0:
            mytime1=datetime(mytime1.year, mytime1.month, mytime1.day, mytime1.hour+1, mytime1.minute+3-60, mytime1.second, tzinfo=self.utc)
        else:
            mytime1=datetime(mytime1.year, mytime1.month, mytime1.day, mytime1.hour, mytime1.minute+3, mytime1.second, tzinfo=self.utc)

        if (nrm_config["debug"]>7):
            print "DELTA: DELAYED 3 min time=", mytime1
        return mytime1

    def get_unixtime(self, delay_days):
        mytime1=datetime.now(self.utc)
        if delay_days == 0:
            mytime11=time.mktime(mytime1.timetuple())
        else:
            from datetime import date
            today = date.fromtimestamp(time.time())
            mytime2=datetime(mytime1.year, mytime1.month, mytime1.day+delay_days, mytime1.hour, mytime1.minute, mytime1.second, tzinfo=utc)
            mytime11=time.mktime(mytime2.timetuple())
        return mytime11

    def get_unixtime_from_datetime(self, dt):
        udt = dt.astimezone(pytz.utc) 
        mytime11=time.mktime(udt.timetuple())
        return mytime11

    def get_datetime(self, unixtime):
        fmt_datetime=datetime.fromtimestamp(float(str(unixtime))).strftime('%Y-%m-%d %H:%M:%S')
        fmt_timezone = "+00:00"
        return fmt_datetime + fmt_timezone

    def convert_str_to_datetime(self, mystr):
        if (nrm_config["debug"]>6): print "DELTA: convert_time: ", mystr
        date_with_tz = mystr
        date_str, tz = date_with_tz[:-5], date_with_tz[-5:]
        dt_utc = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
        dt = dt_utc.replace(tzinfo=self.FixedOffset(tz))
        return dt

    # t0="2019-01-08T20:02:25.027-0500"
    # tx=convert_str_to_datetime(t0)
    # tx= 2019-01-08 20:02:25.027000-05:00
    # t1=datetime.now(utc)
    # t1= 2019-01-09 01:05:28.958184+00:00
    # t1-tx= 183.931184
    def get_time_diff(self, t0):
        t1 = datetime.now(utc)
        td = t1 - t0
        return td.total_seconds()

    def getDelta(self, nrm_deltaid, uid):
        phase = "RESERVED"
        with mydb_session() as s:
            delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.id == nrm_deltaid).first()
            mydid = nrm_deltaid
            if delta is None:
                if (nrm_config["debug"]>2): print "DELTA: STATUS_ID_NOT_FOUND=", nrm_deltaid
                delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.altid == nrm_deltaid).first()
                if delta is None:
                    if (nrm_config["debug"]>2): print "DELTA: STATUS_ALTID_NOT_FOUND=", nrm_deltaid
                    active_delta_status = sensenrm_db.is_delta_active(s, nrm_deltaid, False)
                    if not active_delta_status:
                        if (nrm_config["debug"]>2): print "DELTA: STATUS_ID:"+nrm_deltaid+":NOT_ATIVE"
                        idelta = s.query(sensenrm_db.oiDelta).filter(sensenrm_db.oiDelta.id == nrm_deltaid).first()
                        if idelta is None:
                            if (nrm_config["debug"]>2): print "DELTA: iSTATUS_ID_NOT_FOUND=", nrm_deltaid
                            idelta = s.query(sensenrm_db.oiDelta).filter(sensenrm_db.oiDelta.altid == nrm_deltaid).first()
                            if idelta is None:
                                if (nrm_config["debug"]>2): print "DELTA: iSTATUS_ALTID_NOT_FOUND=", nrm_deltaid
                                idelta = s.query(sensenrm_db.oiDelta).filter(sensenrm_db.oiDelta.cancelid == nrm_deltaid).first()
                                if idelta is None:
                                    if (nrm_config["debug"]>2): print "DELTA: iSTATUS_CANCELID_NOT_FOUND=", nrm_deltaid
                                    phase = "ERROR_DELTAID_NOT_FOUND"
                                    return 201, phase
                                if (nrm_config["debug"]>2): print "DELTA: iSTATUS_CANCELID_FOUND=", nrm_deltaid
                                phase = "COMMITTED" # instead of idelta.status
                                return 200, phase
                            else:
                                phase = idelta.status
                                return 200, phase
                        else:
                            phase = idelta.status
                            return 200, phase

                    phase = "ERROR_DELTAID_NOT_FOUND"
                    return 201, phase
                else:
                    if (nrm_config["debug"]>2): print "DELTA: STATUS_ALTID_FOUND=", delta.altid
                    mydid = delta.id
            if (nrm_config["debug"]>2):
                print "DELTA: STATUS_DELTA_ID=", nrm_deltaid, "=", mydid
                print "DELTA: STATUS_HELD_ID=", delta.heldid
                print "DELTA: STATUS_DELTA_USERID=", delta.userid
                print "DELTA: STATUS_DELTA_STATUS=", delta.status

            if (delta.userid == uid) or (sensenrm_db.is_admin(s,uid)):
                try:
                    resp = oscars_conn.get_status(delta.heldid)
                except Exception as e:
                    if (nrm_config["debug"]>0): print "DELTA STATUS EXCEPT: ", e
                    return 600, "DELTA_STATUS_QUERY_ERROR"
                if resp.status_code != 200:
                    if (nrm_config["debug"]>2):
                        print "DELTA: STATUS_FAILED=", resp.status_code
                else:
                    if (nrm_config["debug"]>2):
                        print "DELTA: STATUS_STATUS=", resp.status_code
                    jstr = resp.json()
                    for key in jstr:
                        if (key == "phase"):
                            if (nrm_config["debug"]>2):
                                print "DELTA: STATUS_PHASE=", jstr[key]
                            if jstr[key] == "RESERVED":
                                phase = "COMMITTED"
                                return resp.status_code, phase
                            elif jstr[key] == "HELD":
                                phase = "REQUESTED"
                                return resp.status_code, phase
                            else:
                                return resp.status_code, jstr[key]
            else:
                if (nrm_config["debug"]>2):
                    print "DELTA: STATUS_UNAUTHORIZED_USER: ", uid
                status = 403
                phase = "UNAUTHORIZED_USER:" + str(uid)
                return status, phase

        return resp.status_code, phase

    def processDeltaReduction(self, deltaContent):
        print "DELTA: Reduction Processing"
        cancelID = ""
        gr = None
        gr = rdflib.Graph()
        result = gr.parse(data=deltaContent, format='ttl')
        if (nrm_config["debug"]>7): print "DELTA: REDUC_LENGTH=", len(gr)
        for subject,predicate,obj in gr:
            #if "urn:ogf:network:es.net:2013::" in str(subject):
            urnsearch = nrm_config["urnprefix"]+"::"
            if urnsearch in str(subject):
                if (nrm_config["debug"]>6): print "DELTA: Cancellation_Subject=", subject
                if "existsDuring" in str(subject):
                    subj2 = subject.split("conn+")
                    subj3 = subj2[1].split(":")
                    cancelID = subj3[0]
                    if (nrm_config["debug"]>4): print "DELTA: Cancellation ID=", cancelID
                    return cancelID
        return cancelID

    def processDelta(self, nrmargs, udn):
        #uid = "defaultuser"
        uid = udn
        timed_file = datetime.fromtimestamp(time.mktime(datetime.now().timetuple())).strftime('%Y%m%d-%H%M%S')
        output_file = self.basePath+"/delta_" + str(timed_file) + "_" + str(nrmargs['id']) + ".txt"
        if (nrm_config["debug"]>2):
            print "DELTA: OUTPUT_PATH=", output_file 
            print "DELTA: UID=", udn
        fo = open(output_file, 'w')
        outputcontent = '[{\"id\":\"' + str(nrmargs['id']) + '\",\"lastModified\":\"' + nrmargs['lastModified'] + '\",\"modelId\":\"' + nrmargs['modelId'] + '\",\"reduction\":' + nrmargs['reduction'] + ',\"addition\":\"' + nrmargs['addition']+ '}]'
        fo.write(outputcontent)
        fo.close()

        deltacontent = ""
        reductionFlag = False
        cancelid = ""
        if nrmargs['reduction'] == "null" or nrmargs['reduction'] == None:
            deltacontent = nrmargs['addition']
        else:
            deltacontent = nrmargs['reduction']
            cancelid = self.processDeltaReduction(deltacontent)
            if cancelid == "":
                deltacontent = nrmargs['addition']
                print "Create_DeltaID=", nrmargs['id']
            else:
                print "Termination_DeltaID=", cancelid
                reductionFlag = True
        
        if (nrm_config["debug"]>2):
            print "DELTA: ID=", nrmargs['id']
            print "DELTA: MODEL_ID=", nrmargs['modelId']
        if (nrm_config["debug"]>8):
            print "DELTA: CONTENT=", deltacontent

        if reductionFlag: # Reduction/cancel
            heldid = ""
            res_msg = ""
            if cancelid == "":
                if (nrm_config["debug"]>6): print "DELTA: Cancel_DeltaID is NONE"
            else:
                if (nrm_config["debug"]>2): print "DELTA: Cancel_DeltaID=", cancelid
                with mydb_session() as s:            
                    founddelta=False
                    active_delta_status = sensenrm_db.is_delta_active(s, cancelid, False)
                    
                    delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.id == cancelid).first()
                    if delta is None:
                        if (nrm_config["debug"]>6): print "DELTA: ID_NOT_FOUND=", cancelid
                        delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.altid == cancelid).first()
                        if delta is None:
                            if (nrm_config["debug"]>6): print "DELTA: ALTID_NOT_FOUND=", cancelid
                        else:
                            founddelta=True
                    else:
                        founddelta=True

                    if founddelta:
                        heldid = delta.heldid
                        cancelid = delta.id
                        if (nrm_config["debug"]>2):
                            print "DELTA: CANCEL_DELTA_ID=", cancelid, "=", delta.id
                            print "DELTA: CANCEL_DELTA_ALTID=", cancelid, "=", delta.altid
                            print "DELTA: CANCEL_HELD_ID=", delta.heldid
                
                        status, resp = nrmcancel.cancel(cancelid, uid, str(nrmargs['id']))
                        if status == 200:
                            if (nrm_config["debug"]>2): print "DELTA: CANCELLED"
                            res_msg = str(resp)
                        elif status == 400:
                            status = 200
                            res_msg = "DeltaID:"+cancelid+":CANCELLED"
                            if (nrm_config["debug"]>2): print "DELTA: CANCELLED_with_400:", status
                        else:
                            if (nrm_config["debug"]>2): print "DELTA: CANCEL_FAILED:", status
                    else:
                        status = 500
                        if (not active_delta_status):
                            res_msg = "DeltaID:"+cancelid+":NOT_FOUND_BUT_EXPIRED"

            return [{"id":str(nrmargs['id']),"description":str("oscars:"+heldid),"lastModified":str(datetime.now()),"modelId":str(nrmargs['modelId']),"reduction":res_msg, "addition":""}], status
            
        else: # Addition/creation
            with mydb_session() as s:
                sensenrm_db.is_delta_active(s, nrmargs['id'], False)
            
            list_switches=None
            dict_switches={}
            list_switches=[]
            list_junctions=[]
            liststr_switches=""
            starttime=""
            endtime=""
            delta_connp = ""
            list_avlans=[]
            delta_avlan = ""
            list_urs=[]
            delta_urs = ""
        
            gac = None
            gac = rdflib.Graph()
            result = gac.parse(data=deltacontent, format='ttl')
            if (nrm_config["debug"]>7): print "DELTA: LENGTH=", len(gac)
            for subject,predicate,obj in gac:
                #if "urn:ogf:network:es.net:2013::" in str(subject):
                urnsearch = nrm_config["urnprefix"]+"::"
                if urnsearch in str(subject):
                    if "service+bw" in str(subject):
                        if (nrm_config["debug"]>9): print "DELTA: SUBJECT:", subject
                        subj2 = subject.split("::")
                        if (nrm_config["debug"]>9): print "DELTA: SUBJECT2:", subj2
                        subj3 = subj2[1].split(":")
                        if (nrm_config["debug"]>9): print "DELTA: SUBJECT3:", subj3

                        junction = subj3[0]+":"+subj3[1].replace('_', '/')
                        if (nrm_config["debug"]>9): print "DELTA: JUNC:", junction
                        tvport = int(subj3[3].split("+")[1])
                        if (nrm_config["debug"]>9): print "DELTA: TVPORT:", tvport
                        djunction = junction + ":" + str(tvport)
                        if (nrm_config["debug"]>9): print "DELTA: DJUNC:", djunction
                    
                        if "reservableCapacity" in str(predicate):
                            if (nrm_config["debug"]>6):
                                print "DELTA: JUNCTION=", junction
                                print "DELTA: reservation=", obj
                                print "DELTA: VLANPORT=", tvport
                            if djunction in dict_switches :
                                dict_switches[djunction].reservedbw = int(obj) #bps
                            else:
                                dsw = delta_switch(sid=djunction, did=nrmargs['id'], mid=nrmargs['modelId'], bw=int(obj), vport=tvport)
                                dict_switches[djunction] = dsw
                                if (nrm_config["debug"]>7):
                                    print "DELTA: ADD_SWITCH_LIST=", djunction
                                if not (junction in list_junctions):
                                    list_junctions.append(junction)
                                if len(list_switches) > 0:
                                    liststr_switches=liststr_switches+","+djunction
                                else:
                                    liststr_switches=djunction
                                list_switches.append(djunction)
                        
                        elif "unit" in str(predicate):
                            if (nrm_config["debug"]>7):
                                print "DELTA: JUNCTION=", djunction
                                print "DELTA: unit=", obj

                    elif "vlanport" in str(subject) or "vlantag" in str(subject):
                        subj2 = subject.split("::")
                        subj3 = subj2[1].split(":")
                        junction = subj3[0]+":"+subj3[1].replace('_', '/')
                        if "value" in str(predicate):
                            if (nrm_config["debug"]>6):
                                print "DELTA: SUBJECT=", subject
                                print "DELTA: JUNCTION=", junction
                                print "DELTA: VLANPORT=", obj
                            djunction = junction + ":" + str(obj)
                            if djunction in dict_switches :
                                dict_switches[djunction].vlanport = int(obj) #bps
                            else:
                                dsw = delta_switch(sid=djunction, did=nrmargs['id'], mid=nrmargs['modelId'], bw=0, vport=int(obj))
                                dict_switches[djunction] = dsw
                                if (nrm_config["debug"]>7):
                                    print "DELTA: ADD_SWITCH_LIST=", djunction
                                if not (junction in list_junctions):
                                    list_junctions.append(junction)
                                if len(list_switches) > 0:
                                    liststr_switches=liststr_switches+","+djunction
                                else:
                                    liststr_switches=djunction
                                list_switches.append(djunction)

                    elif "lifetime" in str(subject):
                        if "start" in str(predicate):
                            if (nrm_config["debug"]>4): print "DELTA: LIFETIME_START=", obj
                            starttime=obj
                        if "end" in str(predicate):
                            if (nrm_config["debug"]>4): print "DELTA: LIFETIME_END=", obj
                            endtime=obj
                    elif "ServiceDomain:EVTS.A-GOLE:conn+" in str(subject):
                        if (nrm_config["debug"]>9): print "DELTA: CONN_SUBJ:", subject
                        subj2 = subject.split("::")
                        if (nrm_config["debug"]>9): print "DELTA: CONN_SUBJ2:", subj2
                        subj3 = subj2[1].split(":")
                        if (nrm_config["debug"]>9): print "DELTA: CONN_SUBJ3:", subj3
                        delta_connp = subj3[2].split("+")[1]
                        if (nrm_config["debug"]>9): print "DELTA: CONN_ID+:", delta_connp

                        d_urs = subj3[3]
                        if (nrm_config["debug"]>9): print "DELTA: CONN_URI_STRING:", d_urs
                        if not (d_urs in list_urs):
                            list_urs.append(d_urs)
                            if len(delta_urs) > 0:
                                delta_urs=delta_urs+","+d_urs
                            else:
                                delta_urs=d_urs

                        d_avlan = subj3[4].split("+")[1]
                        if (nrm_config["debug"]>6): print "DELTA: CONN_ID+VLAN:", d_avlan
                        if not (d_avlan in list_avlans):
                            list_avlans.append(d_avlan)
                            if len(delta_avlan) > 0:
                                delta_avlan=delta_avlan+","+d_avlan
                            else:
                                delta_avlan=d_avlan
                
            if (len(list_switches) < 1):
                raise Exception('DELTA: ADDITION: NO SWITCHES FOUND.')
            if (len(starttime) == 0):
                starttime = str(self.time_iso8601(self.get_delayed_time_5min()))
                if (nrm_config["debug"]>3): print "DELTA: STARTTIME=", starttime
            if (len(endtime) == 0):
                endtime = str(self.time_iso8601(self.get_delayed_time(int(nrm_service["default_delta_lifetime"]))))
                if (nrm_config["debug"]>3): print "DELTA: ENDTIME=", endtime

            dt_s = self.convert_str_to_datetime(starttime)
            dt_e = self.convert_str_to_datetime(endtime)
        
            connid = None
            groupid = None
        
            with mydb_session() as s:
                groupid = sensenrm_db.get_user_group(s,uid)
                if (nrm_config["debug"]>3): print "DELTA: ### Get_Connection_ID ###"
                try:
                    connid = oscars_conn.get_conn_id(groupid)
                except Exception as e:
                    if (nrm_config["debug"]>0): print "DELTA: Get_Conn_ID EXCEPT: ", e
                    raise 

                if len(delta_connp) > 0:
                    d_mainid = nrmargs['id']
                    d_altid = delta_connp
                else:
                    d_mainid = nrmargs['id']
                    d_altid = delta_connp
                sensenrm_db.insert_delta(s, uid, d_mainid, nrmargs['modelId'], liststr_switches, starttime, endtime, d_altid, delta_avlan, delta_urs)
                sensenrm_db.insert_delta_value(s, d_mainid, "heldid", connid)

    ############
    # P2P and Multipoint
            mypce=[]
            if (nrm_config["debug"]>3): 
                print "DELTA: ### Getting_PCE ###"
                print "DELTA: num_list_switches=", len(list_switches)
                print "DELTA: list_switches=", list_switches
                print "DELTA: list_junctions=", list_junctions
            if (len(list_junctions) > 1) :
                try:
                    mypce = oscars_conn.get_pcelist(connid, nrmargs['id'], list_switches, starttime, endtime)
                except Exception as e:
                    if (nrm_config["debug"]>0): print "DELTA: PCE EXCEPT: ", e
                    raise

            myfix=[]
            for a in list_switches:
                if (nrm_config["debug"]>4): print "DELTA: junction=", a, " / ", a.split(':')[0], " / vlanId=", dict_switches[a].vlanport, " / bw=", dict_switches[a].reservedbw
                pt = dict_switches[a].vlanport
                rbw=(int) (dict_switches[a].reservedbw / 1000000.0)
                tn = a.split(':')
                tpurn = tn[0]+":"+tn[1]
                nfix = sensenrm_oscars.nrm_fixture(tn[0], rbw, rbw, tpurn, pt)
                myfix.append(nfix)

            if (nrm_config["debug"]>3): print "DELTA: ### HELD ####"
            try:
                resp = oscars_conn.get_conn_held(connid, nrmargs['id'], dict_switches, mypce, myfix, starttime, endtime, groupid)
            except Exception as e:
                if (nrm_config["debug"]>0): print "DELTA: HELD EXCEPT: ", e
                raise
        
            if (resp.status_code == 200):
                if (nrm_config["debug"]>4): print "DELTA: HELD_OK_CONTENT=", resp._content
                with mydb_session() as s:
                    for k in dict_switches.keys():
                        mysw=dict_switches[k]
                        sensenrm_db.insert_switch(s, mysw.deltaid, mysw.id, mysw.vlanport, mysw.reservedbw, starttime, endtime, connid)
                    sensenrm_db.insert_junction_bidports(s, nrmargs['id'], list_switches)
            else:
                if (nrm_config["debug"]>3): 
                    print "DELTA: HELD_FAILED_CONTENT=", resp.status_code
                    print "DELTA: HELD_FAILED_CONTENT=", resp._content
            return [{"id":str(nrmargs['id']),"description":str("oscars:"+connid),"lastModified":str(datetime.now()),"modelId":str(nrmargs['modelId']),"reduction":"", "addition":str(resp._content)}], resp.status_code

        return [{"id":str(nrmargs['id']),"description":str("something_went_wrong_"+str(reductionFlag)),"lastModified":str(datetime.now()),"modelId":str(nrmargs['modelId']),"reduction":"", "addition":""}], status
        
