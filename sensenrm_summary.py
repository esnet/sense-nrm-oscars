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
## 
# To be completed

from datetime import tzinfo, timedelta, datetime
import time
import uuid
import sys
import os
import fileinput
from sensenrm_config import log_config, nrm_config

class nrmSummary(object):
    basePath = os.path.dirname(os.path.realpath(__file__))
    
    def __init__(self):
        self.obj=" "

    def getUUID(self):
        nrmmodel_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "nrmmodel")
        return nrmmodel_uuid
        
    def getURL(self, uuid):
        nrmmodel_url = 'https://' + nrm_config["host"] + ':' + str(nrm_config["port"]) + '/sense-rm/api/sense/v1/deltas/:' + str(uuid)+'?summary=true'
        return nrmmodel_url
        
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
        
    def getDelta(self, nrm_uuid):
        inputdelta = basePath+"/delta_" + nrm_uuid + ".txt"
        if not os.path.isfile(inputdelta):
            if (nrm_config["debug"]>7): print "SUMM: no such delta input file: ", nrm_uuid, " in ", basePath
            exit()
        fi = fileinput.FileInput(inputdelta)
        deltacontent = fi.readline()
                
        return deltacontent
