#
# SENSE Resource Manager (SENSE-RM) Copyright (c) 2018-2019, The Regents
# of the University of California, through Lawrence Berkeley National
# Laboratory (subject to receipt of any required approvals from the
# U.S. Dept. of Energy).  All rights reserved.
#
# If you have questions about your rights to use or distribute this
# software, please contact Berkeley Lab Innovation & Partnerships
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
# Tue Apr  9 18:02:30 PDT 2019
# sdmsupport@lbl.gov
#
##########################################################################
# e.g. 
# python sensenrm_client_esnet.py --one netlab-mx960-rt1:xe-11_2_0 2010 \
# --two netlab-7750sr12-rt1:9_1_1 2020 --bandwidth 1000 \
# --deltas

'''
SENSE NRM-OSCARS Client Command-line Tool

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         version info
  -d, --debug           Debug flag. Default=False
  --capath CA_PATH      CA path. Default=/etc/grid-security/certificates
  --cert CERT_PATH      User certificate path. Must be paired with --key.
  --key KEY_PATH        User certificate key path. Must be paired with --cert.
  -s NRMSERVICE_ENDPOINT, --service NRMSERVICE_ENDPOINT
                        NRM service endpoint info. 
                        e.g. dev-sense-nrm.es.net:443
  --info                Collect service info over SSL. Default=False
  --sslinfo             Collect service info over SSL. Default=False
  --models              Get Models. Default=False
  --model MODELID       Get Model with model ID
  -i INPUTFILE, --input INPUTFILE
                        Delta request input file path
  --deltas              Delta request submission. Default=False
  --reduction           Delta request for reduction. Default=False
  -c COMMITID, --commit COMMITID
                        Delta commit. Requires request ID
  --status STATUSID     Delta summary status. Requires request ID
  --cancel CANCELID     Cancel delta request. requires request ID
  --clear CLEARID       Clear delta hold. Requires request ID
  --one FROMSWITCH [FROMSWITCH ...]
                        First switch info: switch_name vlan_port. Cannot have
                        --input option together
  --two TOSWITCH [TOSWITCH ...]
                        Second switch info: switch_name vlan_port. When --one
                        is provided, --two must be provided as a pair.
  --bandwidth BANDWIDTH
                        Connection bandwidth in Mbps
  --duration DURATION   Connection duration in hours
  --create-commit       Request creation, submission and commit. Default=False
  --release RELEASEID   Release and terminate the request. requires request ID
  --collectall          Collect all active request IDs. Default=False
  --cancelall           Cancel all active requests. Default=False
  --testall             Test all interfaces. Default=False

'''

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
from datetime import datetime
from time import mktime
from datetime import tzinfo, timedelta, datetime
import dateutil.parser
import pytz

import base64
import gzip
import zlib

################################################################
### If you know the below iterms, you may want to update them 
###    so that you do not need those command options
capath = './certs'
mycerts = ('./usercert.pem', './userkey.pem')
### proxy is not used currently
### myproxy = './userproxy'
################################################################
### If you know what is happening, you may want to edit the followings
switches = ["netlab-mx960-rt2:xe-0_0_0", "netlab-7750sr12-rt2:10_1_5"]
ports = ["2010", "2010"]
### 1 Gbps in bps
bandwidth="1000000000" # in bps = 1Gbps
#############################################
nrmservice_http = "dev-sense-nrm.es.net:8443"
urnprefix = "urn:ogf:network:es.net:2019"
################################################################
################################################################
# Do NOT edit below this line
versioninfo = "NRM client v1.0 on Apr 25, 2019"
urllib3.disable_warnings(urllib3.exceptions.SubjectAltNameWarning)
debug=False

def myprint(s):
    if (debug):
        print(s)
        
def service_end_point():
    myept = "https://" + nrmservice_http
    return myept

#### data time for RFC_1123 and ISO_8601
tZERO = timedelta(0)
class UTC(tzinfo):
  def utcoffset(self, dt):
    return tZERO
  def tzname(self, dt):
    return "UTC"
  def dst(self, dt):
    return tZERO
utc = UTC()

def time_rfc1123():
    now = datetime.now()
    stamp = mktime(now.timetuple())
    rfc1123_time = format_date_time(stamp)
    return rfc1123_time

def time_rfc1123_from_datetime(dt):
    udt = dt.astimezone(pytz.utc)
    local_tz = pytz.timezone('US/Pacific')
    local_dt = udt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    stamp = mktime(local_dt.timetuple())
    rfc1123_time = format_date_time(stamp)
    return rfc1123_time

def get_rfc1123_with_delay(delay_hours):
    mytime1=datetime.now(self.utc)
    if delay_days == 0:
        mytime11=time.mktime(mytime1.timetuple())
    else:
        mytime2=datetime(mytime1.year, mytime1.month, mytime1.day, mytime1.hour_delay_hours, mytime1.minute, mytime1.second, tzinfo=utc)
        mytime11=time.mktime(mytime2.timetuple())
    return mytime11

def time_iso8601(dt):
    """YYYY-MM-DDThh:mm:ssTZD (1997-07-16T19:20:30-03:00)"""
    if dt is None:
        return ""
    fmt_datetime = dt.strftime('%Y-%m-%dT%H:%M:%S')
    tz = dt.utcoffset()
    if tz is None:
        fmt_timezone = "+00:00"
    else:
        fmt_timezone = str.format('{0:+06.2f}', float(tz.total_seconds() / 3600)) 
    return fmt_datetime + fmt_timezone

time_iso8601 = time_iso8601(datetime.now(utc)) # 2017-10-09T19:56:17+00.00

def get_my_time():
    mytime = datetime.fromtimestamp(time.mktime(datetime.now().timetuple())).strftime('%Y%m%d-%H%M%S')
    return str(mytime)
    
#### UUID
def getUUID():
    seed = "delta" + str(datetime.now(utc).strftime('%Y-%m-%dT%H:%M:%S'))
    deltas_uuid = uuid.uuid5(uuid.NAMESPACE_URL, seed)
    #myprint("MY_UUID=" + deltas_uuid + "\n\n")
    return str(deltas_uuid)

#### gzip and base64
def data_gzip_b64encode(tcontent):
    gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    gzipped_data = gzip_compress.compress(tcontent) + gzip_compress.flush()
    b64_gzip_data = base64.b64encode(gzipped_data).decode()
    return b64_gzip_data

def data_b64decode_gunzip(tcontent):
    unzipped_data = zlib.decompress(base64.b64decode(tcontent), 16+zlib.MAX_WBITS)
    return unzipped_data

# output of json
#def dump(obj, nested_level=0, output=sys.stdout):
#    spacing = '   '
#    if type(obj) == dict:
#        print >> output, '%s{' % ((nested_level) * spacing)
#        for k, v in obj.items():
#            if hasattr(v, '__iter__'):
#                print >> output, '%s%s:' % ((nested_level + 1) * spacing, k)
#                dump(v, nested_level + 1, output)
#            else:
#                print >> output, '%s%s: %s' % ((nested_level + 1) * spacing, k, v)
#        print >> output, '%s}' % (nested_level * spacing)
#    elif type(obj) == list:
#        print >> output, '%s[' % ((nested_level) * spacing)
#        for v in obj:
#            if hasattr(v, '__iter__'):
#                dump(v, nested_level + 1, output)
#            else:
#                print >> output, '%s%s' % ((nested_level + 1) * spacing, v)
#        print >> output, '%s]' % ((nested_level) * spacing)
#    else:
#        print >> output, '%s%s' % (nested_level * spacing, obj)
#
def dump(obj, nested_level=0):
    spacing = '   '
    if type(obj) == dict:
        print('%s{' % ((nested_level) * spacing))
        for k, v in obj.items():
            if hasattr(v, '__iter__'):
                print('%s%s:' % ((nested_level + 1) * spacing, k))
                dump(v, nested_level + 1)
            else:
                print('%s%s: %s' % ((nested_level + 1) * spacing, k, v))
        print('%s}' % (nested_level * spacing))
    elif type(obj) == list:
        print('%s[' % ((nested_level) * spacing))
        for v in obj:
            if hasattr(v, '__iter__'):
                dump(v, nested_level + 1)
            else:
                print('%s%s' % ((nested_level + 1) * spacing, v))
        print('%s]' % ((nested_level) * spacing))
    else:
        print('%s%s' % (nested_level * spacing, obj))

########################################

def _url(path):
    return service_end_point() + '/sense-rm/api/sense/v1' + path

def _surl(path):
    return service_end_point() + '/sense-rm/api/sense/v1' + path

def get_info():
    rurl = service_end_point() + '/info'
    resp = requests.get(rurl)
    myprint("NRM info status: " + str(resp.status_code))
    if resp.status_code != 200:
        raise Exception('/info Error: {}'.format(resp.status_code))
    print("NRM info response: " + str(resp._content)) 
    
def get_sslinfo():
    rurl = service_end_point() + '/sslinfo'
    resp = requests.get(rurl, cert=mycerts, verify=capath)
    myprint("NRM sslinfo status: " + str(resp.status_code))
    if resp.status_code != 200:
        raise Exception('/sslinfo Error: {}'.format(resp.status_code))
    #print("heressl: " + str(resp.headers['content-type']))
    print("NRM sslinfo response: " +str(resp._content))

def get_models():
    myheaders = {'If-Modified-Since': time_rfc1123() }
    resp = requests.get(_surl('/models?current=true&summary=false&encode=false'), cert=mycerts, verify=capath)
    myprint("NRM models status: " + str(resp.status_code))
    if resp.status_code == 304:
        myprint("NRM models response header: " + str(resp.headers))
        myprint("NRM models response content: " + str(resp._content))
        #myprint("NRM models response header Last-Modified: " + str(resp.headers['Last-Modified']))
        #myprint("NRM models response header content-type: " + str(resp.headers['content-type']))
        dump(resp.json())
        return True
    #elif resp.status_code != 200:
    #    raise Exception('/models Error: {}'.format(resp.status_code))
    myprint("NRM models result: " + str(resp.headers['content-type']))
    myprint("NRM models result headers: " + str(resp.headers))
    models=resp.json()

    sys.stdout = open('models-'+get_my_time()+'.txt', 'w')
    dump(resp.json())
    return True
    
def get_model(model_id):
    resp = requests.get(_surl('/models/{:d}'.format(model_id)), cert=mycerts, verify=capath)
    myprint("NRM model status: " + str(resp.status_code))
    if resp.status_code != 200:
        raise Exception('/models/id Error {}'.format(resp.status_code))
    myprint("NRM model result: " +str(resp.headers['content-type']))

    sys.stdout = open('model-'+get_my_time()+'.txt', 'w')
    dump(resp.json())
    
def post_deltas_request(deltacontent, deltaid, reduction):
    if reduction: # delta reduction = cancel
        resp = requests.post(_surl('/deltas'), json={
            'id': str(deltaid),
            'lastModified': time_iso8601,
            'modelId': "75d898e1-e60d-4411-85ef-9b2575cec43f",
            'reduction': deltacontent,
            'addition': "null"
            }, cert=mycerts, verify=capath)
    else:
        resp = requests.post(_surl('/deltas'), json={
            'id': str(deltaid),
            'lastModified': time_iso8601,
            'modelId': "75d898e1-e60d-4411-85ef-9b2575cec43f",
            'reduction': "null",
            'addition': deltacontent
            }, cert=mycerts, verify=capath)
            
    myprint("NRM request deltas status: " + str(resp.status_code))
    if resp.status_code != 201:
        print('NRM request deltas non-successful response:')
        dump(resp.json())
        raise Exception('/deltas Error {}'.format(resp.status_code))
    myprint("NRM request deltas response header: " + str(resp.headers['content-type']))
    myprint("NRM request deltas response content: " + str(resp._content))
    print('NRM request deltas response:')
    print(json.dumps(resp.json(), indent = 4))
    
def commit_delta(deltaid):
    resp = requests.put(_surl('/deltas/'+deltaid+'/actions/commit'), cert=mycerts, verify=capath)
    myprint("NRM commit status: " + str(resp.status_code))
    if resp.status_code != 200:
        print('NRM commit non-successful response:')
        dump(resp.json())
        print('/deltas/actions/commit Error {}'.format(resp.status_code))
        return False
    print('NRM commit result : {}'.format(resp.json()["result"]))
    myprint('NRM commit response:')
    myprint(json.dumps(resp.json(), indent = 4))
    return True
    
def status_delta(statusid):
    resp = requests.get(_surl('/deltas/'+statusid+'?summary=true'), cert=mycerts, verify=capath)
    myprint("NRM summary status: " + str(resp.status_code))
    if resp.status_code != 200:
        print('NRM summary non-successful response:')
        dump(resp.json())
        raise Exception('Status Delta Error {}'.format(resp.status_code))
    print('NRM summary result: {}'.format(resp.json()["state"]))
    myprint('NRM summary response:')
    myprint(json.dumps(resp.json(), indent = 4))
    return True
    
def clear_hold(deltaid):
    resp = requests.put(_surl('/deltas/'+deltaid+'/actions/clear'), cert=mycerts, verify=capath)
    myprint("NRM clear status: " + str(resp.status_code))
    if resp.status_code != 200:
        print('NRM clear non-successful response:')
        dump(resp.json())
        print('/deltas/actions/clear Error {}'.format(resp.status_code))
        return False
    print('NRM clear result: {}'.format(resp.json()["result"]))
    myprint('NRM clear response:')
    myprint(json.dumps(resp.json(), indent = 4))
    return True

def cancel_delta(deltaid):
    resp = requests.put(_surl('/deltas/'+deltaid+'/actions/cancel'), cert=mycerts, verify=capath)
    myprint("NRM cancel status: " + str(resp.status_code))
    if resp.status_code != 200:
        print('NRM cancel non-successful response:')
        print(str(resp._content))
        #dump(resp.json())
        raise Exception('/deltas/actions/cancel Error {}'.format(resp.status_code))
    print('NRM cancel result: {}'.format(resp.json()["result"]))
    myprint('NRM cancel response:')
    myprint(json.dumps(resp.json(), indent = 4))
    return True

def delete_model(model_id):
    print("NRM delete model ID: " + str(model_id))
    resp = requests.delete(_surl('/models/{:d}'.format(model_id)), cert=mycerts, verify=capath)
    myprint("NRM delete model  status: " + str(resp.status_code))
    if resp.status_code != 200:
        print('NRM delete non-successful response:')
        dump(resp.json())
        raise Exception('/models/id via delete Error {}'.format(resp.status_code))
    print('NRM delete model result: {}'.format(resp.json()["result"]))
    myprint('NRM delete model response:')
    myprint(json.dumps(resp.json(), indent = 4))
    myprint("NRM delete model DONE")
    return True

def read_delta(inputfile):
    if not os.path.isfile(inputfile):
        print("Delta input file error: " + str(inputfile))
        exit()
    with open(inputfile, 'r') as content_file:
        deltacontent = content_file.read()
    return deltacontent
    
def compose_delta(swithes, ports, bandwidth, duration, urnprefix, deltaid):
    # urnprefix = "urn:ogf:network:es.net:2019"
    # sets pair num, the number of switch port pairs are passed in
    pair_num = 0
    if len(switches) == 2:
        pair_num = 2

    # <urn:ogf:network:es.net:2019::netlab-mx960-rt1:xe-11_2_0:+:vlanport+2687:service+bw>
    # <http://schemas.ogf.org/mrs/2013/12/topology#reservableCapacity> "1000000000"^^xsd:long ;
    # <urn:ogf:network:es.net:2019::netlab-mx960-rt1:xe-11_2_0:+:vlanport+2687> "2589"
    # <urn:ogf:network:es.net:2013::ServiceDomain:EVTS.A-GOLE:subnet+vlan-2010:lifetime>
    #       nml:end             "2018-06-27T10:37:01.000-0400"^^xsd:string  ;
    #       nml:start            "2018-06-24T10:37:01.000-0400"^^xsd:string  .
    # <urn:ogf:network:es.net:2019::ServiceDomain:EVTS.A-GOLE:conn+be01868d-c851-49fa-a88a-4e2e3f687bfe:resource+links-connection_1_2:vlan+2589>

    # initializes the parts of the file
    beg_part = '@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n    @prefix owl:   <http://www.w3.org/2002/07/owl#> .\n    @prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .\n    @prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .\n    @prefix nml:   <http://schemas.ogf.org/nml/2013/03/base#> .\n    @prefix mrs:   <http://schemas.ogf.org/mrs/2013/12/topology#> .\n\n    <urn:ogf:network:es.net:2018::ServiceDomain:EVTS.A-GOLE>\n           mrs:providesSubnet <' + urnprefix + '::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[0] + '>.\n\n    <urn:ogf:network:es.net:2018::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[0] + '> \n           a                  mrs:SwitchingSubnet ;\n           nml:existsDuring <' + urnprefix + '::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[0] + ':lifetime>;\n            nml:labelSwapping         true ;\n            nml:encoding              <http://schemas.ogf.org/nml/2012/10/ethernet> ;\n            nml:labeltype             <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> ;\n            nml:hasBidirectionalPort '
    bandwidth_part = ''
    mid_part = ''

    # creates the parts of the file
    for x in range(0, pair_num):
        myprint("SWITCH: " + switches[x]+":"+ports[x])
        beg_part += '<' + urnprefix + '::' + switches[x] + ':+:vlan+' + ports[x] + '>'
        if x != pair_num - 1:
            beg_part+= ', '
        mid_part += '\n    <' + urnprefix + '::' + switches[x] + ':+>\n           nml:hasBidirectionalPort <' + urnprefix + '::' + switches[x] + ':+:vlan+' + ports[x] + '>.\n\n     <' + urnprefix + '::' + switches[x] + ':+:vlan+' + ports[x] + '>\n           a                  nml:BidirectionalPort ;\n           nml:existsDuring <' + urnprefix + '::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[0] + ':lifetime>;\n           nml:hasLabel     <' + urnprefix + '::' + switches[x] + ':+:vlan+' + ports[x] + ':vlantag+''' + ports[x] + '>;\n           nml:hasService     <' + urnprefix + '::' + switches[x] + ':+:vlan+' + ports[x] + ':service+bw> .\n\n    <' + urnprefix + '::' + switches[x] + ':+:vlan+' + ports[x] + ':vlantag+' + ports[x] + '>\n           a              nml:Label ;\n           nml:existsDuring <' + urnprefix + '::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[0] + ':lifetime>;\n           nml:labeltype  <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> ;\n           nml:value     "' + ports[x] + '" .\n    '
        bandwidth_part += '\n    <' + urnprefix + '::' + switches[x] + ''':+:vlan+''' + ports[x] + ':service+bw>\n            a       mrs:BandwidthService ;\n           mrs:reservableCapacity           "' + bandwidth + '"^^xsd:long ;\n           mrs:type               "guaranteedCapped" ;\n           mrs:unit              "bps" ;\n           nml:existsDuring <' + urnprefix + '::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[x] + ':lifetime>.\n    '
    beg_part += ' .\n'

    # creates optional time part
    time_part = ""
    start_time = ""
    end_time = ""
    
    if duration > 744 :  # one month
        time_part = '\n    <' + urnprefix + '::ServiceDomain:EVTS.A-GOLE:subnet+vlan-' + ports[0] + ':lifetime>\n           a      nml:Lifetime ;\n           nml:end             "' + end_time + '"^^xsd:string  ;\n           nml:start            "' + start_time + '"^^xsd:string  .\n    '

    delta_content = beg_part + mid_part + bandwidth_part + time_part

    output = open('delta-'+get_my_time()+'-'+deltaid+'.txt', 'w+')
    output.write(delta_content)
    output.close()
    
    return delta_content

##############################
# Administrative functions
def get_active_requests():
    rurl = service_end_point() + '/sense-rm/api/protected/alldeltas'
    resp = requests.get(rurl, cert=mycerts, verify=capath)
    myprint("NRM collect all active requests: " + str(resp.status_code))
    if resp.status_code != 200:
        raise Exception('/protercted/requests/active Error: {}'.format(resp.status_code))
    myprint("NRM collect all active requests response:" + str(resp._content))
    print('NRM collect all response:')
    print(json.dumps(resp.json(), indent = 4))
    
def cancel_all_requests():
    rurl = service_end_point() + '/sense-rm/api/protected/cancelall'
    resp = requests.put(rurl, cert=mycerts, verify=capath)
    myprint("NRM cancel all active requests: " + str(resp.status_code))
    if resp.status_code != 200:
        raise Exception('/protercted/requests/active Error: {}'.format(resp.status_code))
    myprint("NRM cancel all active requests response:" + str(resp._content))
    print('NRM cancel all response:')
    print(json.dumps(resp.json(), indent = 4))
    
##############################
inputfile = ""
nrminfo = False
nrmsslinfo = False
getmodels = False
getmodelid = None
postdeltasa = False
reduction = False
commitid = ""
statusid = ""
clearid = ""
cancelid = ""

releaseid = ""
create_commit = False
collectall = False
cancelall = False
testall = False

duration = 2 # hours
#switches=[]
#ports=[]
#bandwidth="1000000" # in bps

parser = argparse.ArgumentParser(description='SENSE NRM-OSCARS Client Command-line Tool')
parser.add_argument("-v", "--version", action="store_true", dest="versioninfo", required=False, help="version info")
parser.add_argument("-d", "--debug", action="store_true", dest="debugFlag", required=False, help="Debug flag. Default=False")
parser.add_argument("--capath", action="store", dest="ca_path", required=False, help="CA path. Default=/etc/grid-security/certificates")
parser.add_argument("--cert", action="store", dest="cert_path", required=False, help="User certificate path. Must be paired with --key.") 
parser.add_argument("--key", action="store", dest="key_path", required=False, help="User certificate key path. Must be paired with --cert.")

parser.add_argument("-s", "--service", action="store", dest="nrmservice_endpoint", required=False, help="NRM service endpoint info. e.g. dev-sense-nrm.es.net:443")

parser.add_argument("--info", action="store_true", dest="nrminfo", required=False, help="Collect service info over SSL. Default=False") 
parser.add_argument("--sslinfo", action="store_true", dest="nrmsslinfo", required=False, help="Collect  service info over SSL. Default=False") 

parser.add_argument("--models", action="store_true", dest="getmodels", required=False, help="Get Models. Default=False") 
parser.add_argument("--model", action="store", dest="modelid", required=False, help="Get Model with model ID") 

parser.add_argument("-i", "--input", action="store", dest="inputfile", required=False, help="Delta request input file path")
parser.add_argument("--deltas", action="store_true", dest="postdeltasa", required=False, help="Delta request submission. Default=False") 
parser.add_argument("--reduction", action="store_true", dest="reduction", required=False, help="Delta request for reduction. Default=False") 

parser.add_argument("-c", "--commit", action="store", dest="commitid", required=False, help="Delta commit. Requires request ID")
parser.add_argument("--status", action="store", dest="statusid", required=False, help="Delta summary status. Requires request ID")
parser.add_argument("--cancel", action="store", dest="cancelid", required=False, help="Cancel delta request. requires request ID")
parser.add_argument("--clear", action="store", dest="clearid", required=False, help="Clear delta hold. Requires request ID")

parser.add_argument("--one", nargs='+', action="store", dest="fromswitch", required=False, help="First switch info: switch_name vlan_port. Cannot have --input option together")
parser.add_argument("--two", nargs='+', action="store", dest="toswitch", required=False, help="Second switch info: switch_name vlan_port. When --one is provided, --two must be provided as a pair.")
parser.add_argument("--bandwidth", action="store", dest="bandwidth", required=False, help="Connection bandwidth in Mbps")
parser.add_argument("--duration", action="store", dest="duration", required=False, help="Connection duration in hours")
# --one switch vlan e.g. --one netlab-mx960-rt1:xe-11_2_0 2010 --bandwidth 3000 (in Mbps)

parser.add_argument("--create-commit", action="store_true", dest="create_commit", required=False, help="Request creation, submission and commit. Default=False") 
parser.add_argument("--release", action="store", dest="releaseid", required=False, help="Release and terminate the request. requires request ID")

parser.add_argument("--collectall", action="store_true", dest="collectall", required=False, help="Collect all active request IDs. Default=False") 
parser.add_argument("--cancelall", action="store_true", dest="cancelall", required=False, help="Cancel all active requests. Default=False") 
parser.add_argument("--testall", action="store_true", dest="testall", required=False, help="Test all interfaces. Default=False") 

args = parser.parse_args()

if (args.versioninfo):
    print(versioninfo)
if (args.debugFlag):
    debug = True

if (args.ca_path):
    capath = args.ca_path
if (args.cert_path):
    mycerts = (args.cert_path, args.key_path)

if (args.nrmservice_endpoint):
     nrmservice_http = args.nrmservice_endpoint

if (args.inputfile):
    inputfile = args.inputfile
if (args.nrminfo):
    nrminfo = True
if (args.nrmsslinfo):
    nrmsslinfo = True
if (args.getmodels):
    getmodels = True
if (args.modelid is not None):
    getmodelid = args.getmodelid
if (args.postdeltasa):
    postdeltasa = True
if (args.reduction):
    reduction = True

if (args.commitid):
    commitid = args.commitid
if (args.statusid):
    statusid = args.statusid
if (args.clearid):
    clearid = args.clearid
if (args.cancelid):
    cancelid = args.cancelid

if (args.create_commit):
    create_commit = args.create_commit
    postdeltasa = False
if (args.releaseid):
    releaseid = args.releaseid
    cancelid = ""
if (args.collectall):
    collectall = True
if (args.cancelall):
    cancelall = True

if (args.testall):
    testall = True
    postdeltasa = False

if (args.fromswitch):
    switches = [args.fromswitch[0], args.toswitch[0]]
    ports = [args.fromswitch[1], args.toswitch[1]]
if (args.bandwidth):
    bandwidth = args.bandwidth
    bandwidth += '000000'    # convert to bps from Mbps
        
if args.duration: # in hours
    duration = args.duration

##############################
if (nrminfo):
    myprint("NRM SSL info")
    get_sslinfo()
    myprint('NRM SSL info DONE')

if (nrmsslinfo):
    myprint("NRM sslinfo")
    get_sslinfo()
    myprint('NRM sslinfo DONE')

## Models
if (getmodels):
    myprint("NRM models")
    get_models()
    myprint('NRM models DONE')

if (getmodelid is not None):
    myprint("NRM model")
    get_model(getmodelid)
    myprint('NRM model DONE')

# Request Delta
if (postdeltasa):
    deltaid = getUUID()
    print("NRM Request deltas ID: " + str(deltaid))
    delta_content = ""
    if (args.inputfile):
        delta_content = read_delta(inputfile)
    else:
        delta_content = compose_delta(switches, ports, bandwidth, duration, urnprefix, deltaid)
    
    myprint("NRM Request deltas")
    post_deltas_request(delta_content, deltaid, reduction)
    print("\nNRM Request ID: " + str(deltaid) + "\n\n")
    myprint('NRM Request deltas DONE')

# Commit
if (commitid):
    myprint("NRM commit ID: " + str(commitid))
    commit_delta(commitid)
    myprint('NRM commit DONE')

# Status
if (statusid):
    myprint("NRM summary ID: " + str(statusid))
    status_delta(statusid)
    myprint('NRM summary DONE')

# Clear
if (clearid):
    myprint("NRM clear ID: " + str(clearid))
    clear_hold(clearid)
    myprint('NRM clear DONE')

# Cancel
if (cancelid):
    myprint("NRM cancel ID: " + str(cancelid))
    cancel_delta(cancelid)
    myprint('NRM cancel DONE')

### Request Submit and Commit
if (create_commit):
    print("### NRM Request Submit and Commit: " + str(service_end_point()))
    myprint("\tService prefix: " + urnprefix)
    myprint("\tDate/time: " + str(get_my_time()))
    myprint("############################################")
    if (debug): 
        print("### NRM SSLINFO")
        get_sslinfo()
        print("############################################")

    myuuid = getUUID()
    print("### NRM RequestID: " + str(myuuid))
    
    myprint("############################################")
    print("### NRM Request")
    delta_content = ""
    if (args.inputfile):
        delta_content = read_delta(inputfile)
    else:
        delta_content = compose_delta(switches, ports, bandwidth, duration, urnprefix, myuuid)
    post_deltas_request(delta_content, myuuid, reduction)

    print("############################################")
    print("### NRM Request COMMIT")
    commit_result = commit_delta(myuuid)
    if not commit_result:
        print("NRM Request Commit Error, and execute Clear")
        clear_result = clear_hold(myuuid)
        if not clear_result:
            print('NRM Request CLEAR ERROR')
        print('NRM Request CLEAR DONE after Commmit Error')

    print("############################################")
    print("### NRM Request SUMMARY")
    status_delta(myuuid)
    print("\n")    
    print("NRM RequestID: " + str(myuuid))

### Request Terminate
if (releaseid):
    print("### NRM Request Release and Terminate: " + service_end_point())
    myprint("\tService prefix: " + urnprefix)
    myprint("\tDate/time: " + str(get_my_time()))
    myprint("############################################")
    if (debug): 
        print("### NRM SSLINFO")
        get_sslinfo()
        print("############################################")

    print("### NRM RequestID for CANCEL: " + str(releaseid))
    cancel_delta(releaseid)
    
    print("############################################")
    print("### NRM Request SUMMARY")
    status_delta(releaseid)
    

######################################################################
# Adminisgrative functions
### Collect all active request IDs that belong to me
if (collectall):
    myprint("NRM collect all active request IDs")
    get_active_requests()
    myprint('NRM collect all DONE')

### Cancel all active requests that belong to me
if (cancelall):
    myprint("NRM cancel all active requests")
    cancel_all_requests()
    myprint('NRM cancel all DONE')

### Testing all interfaces sequentially
if (testall):
    print("### NRM Service Testing: " +str(service_end_point()))
    print("\tService prefix: " + urnprefix)
    print("\tDate/time: " + str(get_my_time()))
    print("############################################")
    print("### NRM_test SSLINFO: " + service_end_point() + "/sslinfo")
    get_sslinfo()
    print("\n")

    print("############################################")
    print("### NRM_test MODELS: " + _surl('/models?current=true&summary=false&encode=false'))
    try:
        get_models()
    except Exception as e:
        print("MODELs Error EXCEPT: " + str(e))
    #if resp.status_code != 200:
    #    print("MODEL_FAILED: " + str(resp.status_code))
    #else:
    #    print("MODEL_HEADER: ", str(resp.headers['content-type']))
    #    models=resp.json()
    #    dump(resp.json())
    print("\n")

    print("############################################")
    myuuid = getUUID()
    print("### NRM_test REQUESTID: " + str(myuuid))
    print("\n")
    
    print("############################################")
    print("NRM_test DELTAS: " + _surl('/deltas'))
    delta_content = ""
    if (args.inputfile):
        delta_content = read_delta(inputfile)
    else:
        delta_content = compose_delta(switches, ports, bandwidth, duration, urnprefix, myuuid)
    post_deltas_request(delta_content, myuuid, reduction)
    print("\n")

    print("############################################")
    print("### NRM_test COMMIT: " + str(_surl('/deltas/'+myuuid+'/actions/commit')))
    commit_result = commit_delta(myuuid)
    if not commit_result:
        print("NRM_test CLEAR_with_COMMIT_ERROR: " + _surl('/deltas/'+myuuid+'/actions/clear'))
        clear_result = clear_hold(myuuid)
        if not clear_result:
            print('NRM_test CLEAR_ERROR')
        print('NRM_test CLEAR_DONE_with_COMMIT_ERROR')
    print("\n")

    print("############################################")
    print("### NRM_test SUMMARY: " + _surl('/deltas/'+myuuid+'?summary=true'))
    status_delta(myuuid)
    print("\n")

    print("############################################")
    if commit_result:
        print("Timing 5 seconds before CANCEL")
        time.sleep(5)
        print("### NRM_test CANCEL: " + _surl('/deltas/'+myuuid+'/actions/cancel'))
        cancel_delta(myuuid)
        print("\n")
    
    print("### NRM_test REQUEST ID: " + str(myuuid))
    print('### NRM_test ALL_TEST DONE')

    #print("############################################")
    #print("NRM_test CLEAR: " + _surl('/deltas/'+myuuid+'/actions/clear'))
    #clear_hold(myuuid)
    #print("CLEAR_DONE: " + str(resp.status_code))
    #print("\n\n")
