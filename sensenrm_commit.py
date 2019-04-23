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
## Commit

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

class nrmCommit(object):
    basePath = log_config["basepath"]
    
    def __init__(self):
        self.obj=" "

    def getUUID(self):
        nrmcommit_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "nrmcommit")
        return nrmcommit_uuid
        
    def getURL(self, uuid):
        nrmcommit_url = 'https://' + nrm_config["host"] + ':' + str(nrm_config["port"]) + '/sense-rm/api/sense/v1/deltas/:' + str(uuid)+'/actions/commit'
        return nrmcommit_url
        
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
    
    def commit(self, nrm_deltaid, uid):
        with mydb_session() as s:            
            delta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.id == nrm_deltaid).first()
            if delta is None:
                if (nrm_config["debug"]>0): print "COMMIT_DELTAID_NOTFOUND=", nrm_deltaid
                delta = s.query(sensenrm_db.oiDelta).filter(sensenrm_db.oiDelta.cancelid == nrm_deltaid).first()
                if delta is None:
                    if (nrm_config["debug"]>0): print "COMMIT_iDELTAID_NOTFOUND=", nrm_deltaid
                else:
                    if (nrm_config["debug"]>0):
                        print "COMMIT_CANCELLED_DELTA_ID=", nrm_deltaid, "=", delta.id, "=", delta.cancelid
                    return True
                return False
            if (nrm_config["debug"]>0):
                print "COMMIT_DELTA_ID=", nrm_deltaid, "=", delta.id
                print "COMMIT_HELD_ID=", delta.heldid
                print "COMMIT_DELTA_USERID=", delta.userid
            if (delta.userid == uid) or (sensenrm_db.is_admin(s,uid)):
                gid = sensenrm_db.get_user_group(s,uid)
                try:
                    status, resp = oscars_conn.get_commit(delta.heldid, gid)
                    if (nrm_config["debug"]>0):
                        print "COMMIT_STATUS=", status
                        print "COMMIT_RESP=", resp
                except Exception as e:
                    if (nrm_config["debug"]>0): print "COMMIT EXCEPT: ", e
                    status = 600
                if status == 200:
                    sensenrm_db.insert_delta_value(s, nrm_deltaid, "status", "COMMITTED")
                    sensenrm_db.update_switch(s, nrm_deltaid, 1)
                    return True
                else:
                    sensenrm_db.update_switch(s, nrm_deltaid, 0)
                    return False
            else:
                if (nrm_config["debug"]>0):
                    print "COMMIT_UNAUTHORIZED_USER: ", uid
                return False
        return True
    
    def getStatus(self, nrm_deltaid):
        deltacontent = ""
        return deltacontent

