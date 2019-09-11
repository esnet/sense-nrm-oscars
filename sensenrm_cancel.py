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
## Cancel
## after commit, tear down immediately after start time. 
## can be used before start time (archived after cancel).
## Note on uncommit: after commit, before start time arrives. 
##                   throws an error after start time. 
##                   (going back to hold stage).
#
from datetime import tzinfo, timedelta, datetime
import time
import uuid
import sys
import os
import fileinput

import sensenrm_oscars
import sensenrm_db
import json
from sensenrm_config import log_config, nrm_config

oscars_conn = sensenrm_oscars.nrm_oscars_connection()
mydb_session = sensenrm_db.db_session

class nrmCancel(object):
    basePath = log_config["basepath"]
    
    def __init__(self):
        self.obj=" "

    def getUUID(self):
        nrmcancel_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "nrmcancel")
        return nrmcancel_uuid
        
    def getURL(self, uuid):
        nrmcancel_url = 'https://' + nrm_config["host"] + ':' + str(nrm_config["port"]) + '/sense-rm/api/sense/v1/deltas/:' + str(uuid) + '/actions/cancel'
        return nrmcancel_url
        
    def getTime(self):
        tZERO = timedelta(0)
        class UTC(tzinfo):
          def utcoffset(self, dt):
            return tZERO
          def tzname(self, dt):
            return "UTC"
          def dst(self, dt):
            return tZERO
        utc = UTC()
        
        dt = datetime.now(utc)
        fmt_datetime = dt.strftime('%Y-%m-%dT%H:%M:%S')
        tz = dt.utcoffset()
        if tz is None:
            fmt_timezone = "+00:00"
            #fmt_timezone = "Z"
        else:
            fmt_timezone = "+00:00"
        time_iso8601 = fmt_datetime + fmt_timezone
        return time_iso8601
    
    def cancel(self, nrm_deltaid, uid, cid):
        with mydb_session() as s:            
            delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.id == nrm_deltaid).first()
            if delta is None:
                delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.altid == cancelid).first()
                if delta is None:
                    resp = "CANCEL_DELTAID_NOTFOUND:" + str(nrm_deltaid)
                    if (nrm_config["debug"]>0): print "CANCEL_DELTAID_NOTFOUND=", nrm_deltaid
            if (nrm_config["debug"]>0):
                print "CANCEL_DELTA_ID=", nrm_deltaid, "=", delta.id
                print "CANCEL_HELD_ID=", delta.heldid
                print "CANCEL_DELTA_USERID=", delta.userid

            if (delta.userid == uid) or (sensenrm_db.is_admin(s,uid)):
                gid = sensenrm_db.get_user_group(s,uid)
                try:
                    status, resp = oscars_conn.get_cancel(delta.heldid, gid)
                except Exception as e:
                    if (nrm_config["debug"]>0): print "CANCEL EXCEPT: ", e
                    status = 600
                    resp = "CANCEL_OSCARS_EXCEPTION: " + str(status)
                did = delta.id

                if (status == 400) or (status == 404):
                    sensenrm_db.update_switch(s, did, 0)
                    sensenrm_db.remove_junction_bidports_with_delta(s, did)
                    sensenrm_db.insert_idelta_remove_delta(s, did, True, cid)
                    if (nrm_config["debug"]>0): 
                        print "Cannot_CANCEL_BUT_Cancelled_400_404: ", status
                elif status != 200:
                    if (nrm_config["debug"]>0): 
                        print "Cannot_CANCEL: ", status
                else:
                    sensenrm_db.update_switch(s, did, 0)
                    sensenrm_db.remove_junction_bidports_with_delta(s, did)
                    sensenrm_db.insert_idelta_remove_delta(s, did, True, cid)
                    if (nrm_config["debug"]>0): 
                        print "CANCEL_STATUS=", status
                        print "CANCEL_RESP=", resp
                        print "CANCELALL_TIMEDELAY_60"
                    time.sleep(60) # time delay 60 seconds for the OSCARS switch reset delay time issue, after "cancel" for committed vlans
            else:
                if (nrm_config["debug"]>0):
                    print "CANCEL_UNAUTHORIZED_USER: ", uid
                resp = "UNAUTHORIZED_USER:" + str(uid)
                status = 403
            return status, resp

        return 201, ""
    
    def cancelall(self, uid):
        # status, resp = nrmcancel.cancelall(udn)
        with mydb_session() as s:
            alldeltas = None
            allids = ""
            if (sensenrm_db.is_admin(s,uid)):
                alldeltas = s.query(sensenrm_db.oDelta).all()
            else:
                alldeltas = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.userid == uid).all()
            result = ""
            mydelay = False
            if len(alldeltas) > 0:
                gid = sensenrm_db.get_user_group(s,uid)
                for delta in alldeltas:
                    if (nrm_config["debug"]>0):
                        print "CANCELALL_DELTA_ID=", delta.id
                        print "CANCELALL_HELD_ID=", delta.heldid

                    try:
                        status, resp = oscars_conn.get_cancel(delta.heldid, gid)
                    except Exception as e:
                        if (nrm_config["debug"]>0): print "CANCEL EXCEPT: ", e
                        status = 600

                    did = delta.id
                    if status == 400:
                        sensenrm_db.update_switch(s, did, 0)
                        sensenrm_db.remove_junction_bidports_with_delta(s, did)
                        sensenrm_db.insert_idelta_remove_delta(s, did, True, "")
                        if (nrm_config["debug"]>0):
                            print "Cannot_CANCELALL_BUT_Cancelled_400: ", status
                        result = result + "OK2"
                    elif status != 200:
                        if (nrm_config["debug"]>0):
                            print "Cannot_CANCELALL: ", status
                        result = result + "FAILED"
                    else:
                        sensenrm_db.update_switch(s, did, 0)
                        sensenrm_db.remove_junction_bidports_with_delta(s, did)
                        sensenrm_db.insert_idelta_remove_delta(s, did, True, "")
                        if (nrm_config["debug"]>0):
                            print "CANCELALL_STATUS=", status
                            print "CANCELALL_RESP=", resp
                        result = result + "OK"
                        mydelay = True

                    allids = allids + delta.id
                    if alldeltas.index(delta) != len(alldeltas)-1:
                        allids = allids + ','
                        result = result + ','
                if (mydelay):
                    if (nrm_config["debug"]>0): 
                        print "CANCELALL_TIMEDELAY_60"
                    time.sleep(60)	#time delay (60 seconds) for the OSCARS switch reset delay time issue, after "cancel" for committed vlans
            else:
                result = "CANCELALL_DELTAS_NOT_FOUND"
            return result, allids
        return result, allids

    def getStatus(self, nrm_deltaid):
        deltacontent = ""
        return deltacontent

