#
# SENSE Resource Manager (SENSE-RM) Copyright (c) 2018-2020, The Regents
# of the University of California, through Lawrence Berkeley National
# Laboratory (subject to receipt of any required approvals from the
# U.S. Dept. of Energy).  All rights reserved.
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
# Fri Sep 14 08:06:59 PDT 2018
# sdmsupport@lbl.gov
#
## sensenrm_oscars tester

import sensenrm_oscars
import sensenrm_db
import argparse
import fileinput
from datetime import tzinfo, timedelta, datetime
import time

def nprint(*args):
    print(''.join(str(e) for e in args))

oscars_tester = sensenrm_oscars.nrm_oscars_connection()
mydb_session = sensenrm_db.db_session

inputfile = ""
outputfile = ""
connid = "" # Connection ID holder
deltaid = "mytest" # user request ID from the user
nrminfo = False
nrmsslinfo = False
nrmsecureinfo = False
nrmavailtopo = False
nrmreservedlist = False
gettoken = False   # user id token
getconnid=False     # connection id
getpce=False     # path computation
pcesrc = "netlab-mx960-rt2:xe-0/0/0"
pcedest = "netlab-7750sr12-rt1:9/1/1"
pcelist2 = ["netlab-mx960-rt1:xe-11/2/0", "netlab-mx960-rt1:xe-11/2/0"]
vlanid2 = [2020, 2030]
pcelist3 = ["netlab-mx960-rt2:xe-0/0/0", "netlab-7750sr12-rt1:9/1/1", "netlab-7750sr12-rt2:10/1/5"]
vlanid3 = [2100, 2100, 2100]
ingr=10000  # Mbps
egr=10000   # Mbps

pcedone=False    # indicating if getpce is done previously, used for held
getheld=False     # holding the conn first time
getheldmulti=False     # holding the conn first time for multipoint
getcommit=False     # connection commit
getclear=False     # connection clear
getcancel=False     # connection cancel
getstatus=False     # connection status

parser = argparse.ArgumentParser(description='sensenrm test client')
parser.add_argument("-i", "--input", action="store", dest="inputfile", required=False, help="input file path")
parser.add_argument("-o", "--save", action="store", dest="outputfile", required=False, help="output file path")
parser.add_argument("--deltaid", action="store", dest="deltaid", required=False, help="Request (Delta) ID from the user for HELD")
parser.add_argument("--connid", action="store", dest="connid", required=False, help="Request ID for OSCARS HELD")
parser.add_argument("--src", action="store", dest="pcesrc", required=False, help="Source junction name for PCE")
parser.add_argument("--dest", action="store", dest="pcedest", required=False, help="Destination junction name for PCE")
parser.add_argument("--info", action="store_true", dest="nrminfo", required=False, help="Collect service info. Default is False") 
parser.add_argument("--sslinfo", action="store_true", dest="nrmsslinfo", required=False, help="Collect SSL service info. Default is False") 
parser.add_argument("--secureinfo", action="store_true", dest="nrmsecureinfo", required=False, help="Collect Secure info. Default is False") 
parser.add_argument("--availtopo", action="store_true", dest="nrmavailtopo", required=False, help="Collect available topology info. Default is False") 
parser.add_argument("--reservedlist", action="store_true", dest="nrmreservedlist", required=False, help="Collect reserved list info. Default is False") 
parser.add_argument("--gettoken", action="store_true", dest="gettoken", required=False, help="Get Token. Default is False") 
parser.add_argument("--getconnid", action="store_true", dest="getconnid", required=False, help="Get connection id. Default is False") 
parser.add_argument("--getheld", action="store_true", dest="getheld", required=False, help="Get connection held. Default is False") 
parser.add_argument("--getheldmulti", action="store_true", dest="getheldmulti", required=False, help="Get connection held for mutipoint. Default is False") 
parser.add_argument("--getpce", action="store_true", dest="getpce", required=False, help="Get path computation. Default is False") 
parser.add_argument("--getcommit", action="store_true", dest="getcommit", required=False, help="Get connection commit. Default is False") 
parser.add_argument("--getclear", action="store_true", dest="getclear", required=False, help="Get connection clear. Default is False") 
parser.add_argument("--getcancel", action="store_true", dest="getcancel", required=False, help="Get connection cancel. Default is False") 
parser.add_argument("--getstatus", action="store_true", dest="getstatus", required=False, help="Get connection status. Default is False") 
parser.add_argument("--ingress", action="store", dest="ingress", required=False, help="ingress bandwidth")
parser.add_argument("--egress", action="store", dest="egress", required=False, help="egress bandwidth")

args = parser.parse_args()

if (args.inputfile):
    inputfile = args.inputfile
if (args.outputfile):
    outputfile = args.outputfile
if (args.deltaid):
    deltaid = args.deltaid
if (args.connid):
    connid = args.connid
if (args.pcesrc):
    pcesrc = args.pcesrc
if (args.pcedest):
    pcedest = args.pcedest
if (args.nrminfo):
    nrminfo = True
if (args.nrmsslinfo):
    nrmsslinfo = True
if (args.nrmsecureinfo):
    nrmsecureinfo = True
if (args.nrmavailtopo):
    nrmavailtopo = True
if (args.nrmreservedlist):
    nrmreservedlist = True
if (args.gettoken):
    gettoken = True
if (args.getconnid):
    getconnid = True
if (args.getheld):
    getheld = True
if (args.getheldmulti):
    getheldmulti = True
if (args.getpce):
    getpce = True
if (args.getcommit):
    getcommit = True
if (args.getclear):
    getclear = True
if (args.getcancel):
    getcancel = True
if (args.getstatus):
    getstatus = True
if (args.ingress):
    ingr = args.ingress
if (args.egress):
    egr = args.egress

##############################
class UTC(tzinfo):
  def utcoffset(self, dt):
    return timedelta(0)
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return timedelta(0)
utc = UTC()

def time_iso8601(dt):
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

def get_delayed_time(delay_hours):
    mytime1=datetime.now(utc)
    if delay_hours != 0:
        days = int((mytime1.hour+delay_hours) / 24)
        hours = delay_hours - 24*(int(delay_hours/24))
        if (nrm_config["debug"]>4):
            nprint("DELAYED time=", mytime1.hour)
            nprint("DELAYED input=", delay_hours)
            nprint("DELAYED days=", days)
            nprint("DELAYED hours=", hours)
        mytime1=datetime(mytime1.year, mytime1.month, mytime1.day+days, mytime1.hour+hours, mytime1.minute, mytime1.second, tzinfo=self.utc)
    return mytime1
##############################


if (nrminfo):
    nprint("INFO tester")
    resp = oscars_tester.get_info()

if (nrmsslinfo):
    nprint("SSL_INFO tester")
    resp = oscars_tester.get_sslinfo()

if (nrmsecureinfo):
    nprint("PROTECTED_INFO tester")
    resp = oscars_tester.get_protected_info()

if (nrmavailtopo):
    nprint("TOPO tester")
    resp = oscars_tester.get_avail_topo()

if (nrmreservedlist):
    nprint("ReservedList tester")
    resp = oscars_tester.get_reserved()

if (gettoken):
    nprint("Token tester")
    uid = ""
    upasswd = ""
    resp = oscars_tester.get_token(uid, upasswd)

if (getconnid):
    nprint("ConnectionID tester")
    connid = oscars_tester.get_conn_id()
    nprint("CONNECTION_ID=", connid)

if (getheld):
    connid = None
    if (connid is None) or (len(connid) == 0):
        nprint("Getting Connection ID first")
        connid = oscars_tester.get_conn_id()
    nprint("CONNECTION_ID=", connid)
    
    starttime = str(time_iso8601(datetime.utcnow()))
    endtime = str(time_iso8601(get_delayed_time(24)))
    mypce=[]
    if pcedone is False:
        nprint("Getting PCE next")
        mypce = oscars_tester.get_pcelist(connid, deltaid, pcelist2, starttime, endtime)
        pcedone=True
        
    myfix=[]
    for a in pcelist2:
        nprint("junction=", a, " / ", a.split(':')[0], " / vlanId=", vlanid2[pcelist2.index(a)])
        nfix = sensenrm_oscars.nrm_fixture(a.split(':')[0], ingr, egr, a, vlanid2[pcelist2.index(a)])
        myfix.append(nfix)
            
    nprint("HELD tester")
    resp = oscars_tester.get_conn_held(connid, deltaid, pcelist2, mypce, myfix, starttime, endtime)


if (getheldmulti):
    connid = None
    if (connid is None) or (len(connid) == 0):
        nprint("Getting Connection ID first")
        connid = oscars_tester.get_conn_id()
    nprint("CONNECTION_ID=", connid)
    
    starttime = str(time_iso8601(datetime.utcnow()))
    endtime = str(time_iso8601(get_delayed_time(24)))
    
    mypce=[]
    if pcedone is False:
        nprint("Getting PCE next for multipoint")
        mypce = oscars_tester.get_pcelist(connid, deltaid, pcelist3, starttime, endtime)
        pcedone=True
        
    myfix=[]
    for a in pcelist3:
        nprint("junction=", a, " / ", a.split(':')[0], " / vlanId=", vlanid3[pcelist3.index(a)])
        nfix = sensenrm_oscars.nrm_fixture(a.split(':')[0], ingr, egr, a, vlanid3[pcelist3.index(a)])
        myfix.append(nfix)

    nprint("HELD tester")
    resp = oscars_tester.get_conn_held(connid, deltaid, pcelist3, mypce, myfix, starttime, endtime)


if (getpce):
    nprint("PCE tester")
    if (len(connid) == 0) or (connid is None):
        nprint("Getting Connection ID first")
        connid = oscars_tester.get_conn_id()
    nprint("CONNECTION_ID=", connid)

    starttime = str(time_iso8601(datetime.utcnow()))
    endtime = str(time_iso8601(get_delayed_time(24)))
    pcelist2 = ["netlab-mx960-rt1:xe-11/2/0", "netlab-mx960-rt1:xe-11/2/0"]
    pcedone = oscars_tester.get_pcelist(connid, deltaid, pcelist2, starttime, endtime)

if (getcommit):
    nprint("Commit testger")
    if (len(connid) == 0) or (connid is None):
        nprint("Getting Connection ID first")
        exit(1)
    nprint("CONNECTION_ID=", connid)
    resp = oscars_tester.get_commit(connid)

if (getclear):
    nprint("Clear tester")
    if (len(connid) == 0) or (connid is None):
        nprint("Getting Connection ID first")
        exit(1)
    status, resp = oscars_tester.get_clear(connid)

if (getcancel):
    nprint("Cancel tester")
    if (len(connid) == 0) or (connid is None):
        nprint("Getting Connection ID first")
        exit(1)
    status, resp = oscars_tester.get_cancel(connid)

if (getstatus):
    nprint("Status tester")
    if (len(connid) == 0) or (connid is None):
        nprint("Getting Connection ID first")
        exit(1)
    resp = oscars_tester.get_status(connid)

