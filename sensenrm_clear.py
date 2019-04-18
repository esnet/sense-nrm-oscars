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
## HOLD Clear
## clear: after hold, before commit. removes connid entirely
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

class nrmClear(object):
    basePath = log_config["basepath"]
    
    def __init__(self):
        self.obj=" "

    def getUUID(self):
        nrmcommit_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "nrmclear")
        return nrmcommit_uuid
        
    def getURL(self, uuid):
        nrmclear_url = 'https://' + nrm_config["host"] + ':' + str(nrm_config["port"]) + '/sense-rm/api/sense/v1/deltas/:' + str(uuid)+'/actions/clear'
        return nrmclear_url
        
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
    
    def clear(self, nrm_deltaid, uid):
        with mydb_session() as s:            
            delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.id == nrm_deltaid).first()
            if delta is None:
                if (nrm_config["debug"]>0): print "CLEAR_DELTAID_NOTFOUND=", nrm_deltaid
                return False
            if (nrm_config["debug"]>1):
                print "CLEAR_DELTA_ID=", nrm_deltaid, "=", delta.id
                print "CLEAR_HELD_ID=", delta.heldid
                print "CLEAR_DELTA_USERID=", delta.userid
            if (delta.userid == uid) or (sensenrm_db.is_admin(s,uid)):
                groupid = sensenrm_db.get_user_group(s,uid)
                try:
                    status, resp = oscars_conn.get_clear(delta.heldid, groupid)
                except Exception as e:
                    if (nrm_config["debug"]>0): print "CLEAR EXCEPT: ", e
                    status = 600

                if status != 200:
                    if (nrm_config["debug"]>0):
                        print "CLEAR_FAILED=", status
                else:
                    if (nrm_config["debug"]>0):
                        print "CLEAR_STATUS=", status
                        print "CLEAR_RESP=", resp
            else:
                if (nrm_config["debug"]>0):
                    print "CLEAR_UNAUTHORIZED_USER: ", uid
                resp = "UNAUTHORIZED_USER:" + str(uid)
                status = 403

        return status, resp
    
    def getStatus(self, nrm_deltaid):
        deltacontent = ""
        return deltacontent
