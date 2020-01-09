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
from flask import Flask, jsonify, abort, make_response, request, Response
#from flask import Flask, jsonify, abort, make_response, request
from flask_restful import Api, Resource, reqparse, fields, marshal

import ssl

from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
from datetime import tzinfo, timedelta, datetime
import dateutil.parser

import base64
import gzip
import zlib
#import json

import sensenrm_utils as utils
from sensenrm_config import ssl_config, nrm_config
import sensenrm_db
import sensenrm_oscars
import sensenrm_model
import sensenrm_delta
import sensenrm_commit
import sensenrm_clear
import sensenrm_cancel

title_info = "SENSE Network Resource Manager for OSCARS"
version_info = "v1.0.0 on 23 April 2019"
errors = {
    'NotFound': {
        'message': "A resource with that ID do not exist.",
        'status': 404,
        'extra': "Any extra information",
    },
}

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_verify_locations(capath=ssl_config["capath"])
context.load_cert_chain(ssl_config["hostcertpath"], ssl_config["hostkeypath"])
#2.7
#ssl._https_verify_certificates(enable=ssl_config["httpsverify"])
if (ssl_config["httpsverify"]):
    context.verify_flags=ssl.VERIFY_X509_TRUSTED_FIRST
else:
    context.verify_flags=ssl.VERIFY_DEFAULT

nrm_application = Flask(__name__)
api = Api(nrm_application, errors=errors)

mydb_session = sensenrm_db.db_session

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
    import pytz
    udt = dt.astimezone(pytz.utc)
    local_tz = pytz.timezone('US/Pacific')
    local_dt = udt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    stamp = mktime(local_dt.timetuple())
    rfc1123_time = format_date_time(stamp)
    return rfc1123_time

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

#### gzip and base64
def data_gzip_b64encode(tcontent):
    gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    gzipped_data = gzip_compress.compress(tcontent) + gzip_compress.flush()
    b64_gzip_data = base64.b64encode(gzipped_data).decode()
    return b64_gzip_data

def data_b64decode_gunzip(tcontent):
    unzipped_data = zlib.decompress(base64.b64decode(tcontent), 16+zlib.MAX_WBITS)
    return unzipped_data
    
model_fields = {
    'id': fields.Raw,
    'href': fields.Raw,
    'creationTime': fields.Raw,
    'model': fields.Raw
}

modelno_fields = {
    'model': fields.Raw
}

delta_fields = {
    'id': fields.Raw,
    'lastModified': fields.Raw,
    'description': fields.Raw,
    'modelId': fields.Raw,
    'reduction': fields.Raw,
    'addition': fields.Raw
}

nrmmodels = sensenrm_model.nrmModel()
nrmdeltas = sensenrm_delta.nrmDelta()
nrmcommits = sensenrm_commit.nrmCommit()
nrmclear = sensenrm_clear.nrmClear()
nrmcancel = sensenrm_cancel.nrmCancel()

class ModelsAPI(Resource):
    def __init__(self):
        # current=true&summary=false&encode=false
        if (nrm_config["debug"]>3): 
            utils.nprint("SVC:MODELS INIT")
            #request.environ.get('HTTP_X_MYHOST')
            #request.environ.get('HTTP_X_SSL_CLIENT_VERIFY')
            #request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
            #request.environ.get('HTTP_X_REAL_IP')
            utils.nprint("SVC: MODEL_SSL_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
            utils.nprint("SVC: MODEL_SSL_IP:", request.environ.get('HTTP_X_REAL_IP'))
        #udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        #with mydb_session() as s:
        #    results = sensenrm_db.validate_user(s, udn)
        #    if results:
        #        self.reqparse = reqparse.RequestParser()
        #        self.reqparse.add_argument('current', type = str, default = "true")
        #        self.reqparse.add_argument('summary', type = str, default = "false")
        #        self.reqparse.add_argument('encode', type = str, default = "false")
        #        self.models = nrmmodels.getModel()
        #        if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS INIT DONE")
        #    else:
        #        self.models = "UNAUTHORIZED_USER"
        super(ModelsAPI, self).__init__()
    
    def get(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS GET")

        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                mymodels,status = nrmmodels.getModel()
                #mymodels,last_modtime,status = nrmmodels.getModel()
                if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS INIT DONE")
                if status:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS RETURNED")
                    #if (nrm_config["debug"]>9): utils.nprint(mymodels)
                    return marshal(mymodels, model_fields)
                    #mycontent = marshal(mymodels, model_fields)
                    #myresp = make_response(jsonify(mycontent))
                    #myresp.status_code = 200
                    #return myresp
                else:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS NO_CHANGES HERE")
                    return marshal(mymodels, model_fields)
                    #return {'model': str("NO_CHANGES")}, 304
                    #my_lasttime = time_rfc1123_from_datetime(last_modtime)
                    #mymodels = [{"id":str(""),"href":str(""),"creationTime":str(time_rfc1123()),"model":str("")}]
                    #mycontent = marshal(mymodels, model_fields)
                    #myresp = make_response(jsonify(mycontent))
                    #myresp.headers["Last-Modified"] = str(my_lasttime)
                    #myresp.headers["content-type"] = "application/json"
                    #myresp.status_code = 200
                    ##myresp.status_code = 304
                    #return myresp
            else:
                mymodels = "UNAUTHORIZED_USER"
                if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS 403 INVALID_USER")
                return {'model': str("UNAUTHORIZED_USER")}, 403

    def post(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: MODELS POST")
        args = self.reqparse.parse_args()
        return {'models': marshal(self.models, model_fields)}, 201

class DeltasAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: DELTAS INIT")
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('id', type = str, location = 'json')
        self.reqparse.add_argument('lastModified', type = str, location = 'json')
        self.reqparse.add_argument('modelId', type = str, location = 'json')
        self.reqparse.add_argument('reduction', type = str, location = 'json')
        self.reqparse.add_argument('addition', type = str, location = 'json')
        super(DeltasAPI, self).__init__()
    
    def get(self):
        if (nrm_config["debug"]>3): 
            utils.nprint("SVC: DELTAS GET ID=", deltaid)
        return {'deltas': marshal(deltas, delta_fields)}

    def post(self):
        args = self.reqparse.parse_args()
        if (nrm_config["debug"]>3):
            utils.nprint("SVC: DELTAS POST ID: ", args['id'])
            utils.nprint("SVC: DELTAS_SSL_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                deltas, mystatus =nrmdeltas.processDelta(args, udn)
                if (nrm_config["debug"]>7): utils.nprint("SVC: DELTA_POST=", mystatus)
                rstatus = 201
                if int(mystatus) != 200: 
                    if (nrm_config["debug"]>3): utils.nprint("SVC: DELTA_POST_ERROR=", mystatus)
                    rstatus = mystatus
                return {'deltas': marshal(deltas, delta_fields)}, rstatus
            else:
                return {'deltas': str("UNAUTHORIZED_USER")}, 403
                


class DeltaAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: DELTA SUMMARY")
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('summary', type = str, default = "true")
        self.reqparse.add_argument('deltaid', type = str, location = 'json')
        super(DeltaAPI, self).__init__()

    def get(self, deltaid):
        if (nrm_config["debug"]>3): 
            utils.nprint("SVC: DELTA GET_ID=", deltaid)
            utils.nprint("SVC: DELTA_SSL_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                status, phase = nrmdeltas.getDelta(deltaid, udn) # Status
                if (nrm_config["debug"]>3): utils.nprint("SVC: DELTA SUMMARY=", status)
                return {'state': str(phase), 'deltaid': str(deltaid)}, status
            else:
                return {'state': str("UNAUTHORIZED_USER"), 'deltaid': str(deltaid)}, 403

class CommitsAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: COMMIT")
        super(CommitsAPI, self).__init__()

    def put(self, deltaid):
        if (nrm_config["debug"]>3): 
            utils.nprint("SVC: COMMIT PUT ID=", deltaid)
            utils.nprint("SVC: COMMIT_SSL_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                status = nrmcommits.commit(deltaid, udn)
                if status:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: COMMIT_OK")
                    return {'result': "COMMITTED"}, 200
                else:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: COMMIT_FAILED")
                    return {'result': "FAILED"}, 404
            else:
                return {'result': str("FAILED:UNAUTHORIZED_USER")}, 403

        return {'result': True}, 200

    def get(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: COMMIT GET")
        return {'result': True}, 200

    def post(self):
        args = self.reqparse.parse_args()
        if (nrm_config["debug"]>3):
            utils.nprint("SVC: COMMIT POST ID=", args['id'])
        return {'result': True}, 201

class CancelAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: CANCEL")
        super(CancelAPI, self).__init__()

    def put(self, deltaid):
        if (nrm_config["debug"]>3): 
            utils.nprint("SVC: CANCEL PUT ID=", deltaid)
            utils.nprint("SVC: CANCEL_SSL_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                status, resp = nrmcancel.cancel(deltaid, udn, "")
                if status == 200:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: CANCEL_OK:", status)
                    return {'result': "CANCELED" }, status
                elif status == 400:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: CANCELLED_with_400:", status)
                    return {'result': "CANCELED" }, 200
                else:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: CANCEL_FAILED:", status)
                    return {'result': "FAILED", 'mesg': str(resp)}, status
            else:
                return {'result': str("FAILED"), 'mesg': str("UNAUTHORIZED_USER")}, 403

        return {'result': True}, 200

    def get(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: CANCEL GET")
        return {'result': True}, 200

    def post(self, deltaid):
        if (nrm_config["debug"]>3): utils.nprint("SVC: CANCEL POST ID=", deltaid)
        return {'result': True}, 201

class ClearAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: CLEAR")
        super(ClearAPI, self).__init__()

    def put(self, deltaid):
        if (nrm_config["debug"]>3):
            utils.nprint("SVC: CLEAR PUT ID=", deltaid)
            utils.nprint("SVC: CLEAR_SSL_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                status, resp = nrmclear.clear(deltaid, udn)
                if status == 200:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: CLEARED")
                    return {'result': "CLEARED"}, status
                else:
                    if (nrm_config["debug"]>3): utils.nprint("SVC: CLEAR_FAILED")
                    return {'result': "FAILED", 'mesg': str(resp)}, status
            else:
                return {'result': str("FAILED"), 'mesg': str("UNAUTHORIZED_USER")}, 403

        return {'result': True}, 200

    def get(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: CLEAR GET")
        return {'result': True}, 200

    def post(self, deltaid):
        if (nrm_config["debug"]>3): 
            utils.nprint("SVC: CLEAR POST ID=", deltaid)
        return {'result': True}, 201

## Administrative calls for authorized users
class AllDeltasAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: ALL_DELTAS")
        super(AllDeltasAPI, self).__init__()

    def get(self):
        if (nrm_config["debug"]>3):
            utils.nprint("SVC: ALL_DELTAS GET: ", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            isauthz = sensenrm_db.validate_user(s, udn)
            if isauthz:
                alldeltas = sensenrm_db.get_all_active_deltas(s, udn)
                rstatus = 200
                return {'deltas': str(alldeltas)}, rstatus
            else:
                return {'deltas': str("UNAUTHORIZED_USER")}, 403

    def post(self):
        if (nrm_config["debug"]>3):
            utils.nprint("SVC: ALL_DELTAS POST: ", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        return {'deltas': str("UNAUTHORIZED_ACCESS")}, 403

## Administrative calls for authorized users
class AllCancelAPI(Resource):
    def __init__(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: ALL_CANCEL")
        super(AllCancelAPI, self).__init__()

    def put(self):
        if (nrm_config["debug"]>3):
            utils.nprint("SVC: ALL_CANCEL PUT: ", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
        with mydb_session() as s:
            results = sensenrm_db.validate_user(s, udn)
            if results:
                status, allids = nrmcancel.cancelall(udn)
                if (nrm_config["debug"]>3): utils.nprint("SVC: ALL_CANCEL:", status)
                return {'result': str(status), 'deltas': str(allids) }, 200
            else:
                return {'result': str("FAILED"), 'mesg': str("UNAUTHORIZED_USER")}, 403

        return {'result': False}, 201

    def get(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: ALL_CANCEL GET")
        return {'result': False}, 201

    def post(self):
        if (nrm_config["debug"]>3): utils.nprint("SVC: ALL_CANCEL POST")
        return {'result': False}, 201

## ########################
api.add_resource(ModelsAPI, '/sense-rm/api/sense/v1/models', endpoint = 'models')
api.add_resource(DeltasAPI, '/sense-rm/api/sense/v1/deltas', endpoint = 'deltas')
api.add_resource(DeltaAPI, '/sense-rm/api/sense/v1/deltas/<string:deltaid>', endpoint = 'delta')
api.add_resource(CommitsAPI, '/sense-rm/api/sense/v1/deltas/<string:deltaid>/actions/commit', endpoint = 'commits')
api.add_resource(ClearAPI, '/sense-rm/api/sense/v1/deltas/<string:deltaid>/actions/clear', endpoint = 'clear')
api.add_resource(CancelAPI, '/sense-rm/api/sense/v1/deltas/<string:deltaid>/actions/cancel', endpoint = 'cancel')
api.add_resource(AllDeltasAPI, '/sense-rm/api/protected/alldeltas', endpoint = 'alldeltas')
api.add_resource(AllCancelAPI, '/sense-rm/api/protected/cancelall', endpoint = 'cancelall')

@nrm_application.route('/sense-rm')
def index():
    return "Hi there!"

@nrm_application.route('/info')
def info():
    if (nrm_config["debug"]>2):
        #utils.nprint("SVC: INFO_1: ", request.__dict__)
        utils.nprint("SVC: INFO_2: ", request.headers)
        #utils.nprint("SVC: INFO_3: ", request.environ)
    return """
MRM-info: {}
Version-info: {}
NRMHost: {}
IP: {}
""".format(
    title_info,
    version_info,
    request.environ.get('HTTP_X_MYHOST'),
    request.environ.get('HTTP_X_REAL_IP'))

@nrm_application.route('/sslinfo')
def sslinfo():
    if (nrm_config["debug"]>0):
        utils.nprint("SVC: SSLINFO_DN:", request.environ.get('HTTP_X_SSL_CLIENT_S_DN'))
        #utils.nprint("SSL_0: ", request.__dict__)
        #utils.nprint("SSL_1: ", request.headers)
        #utils.nprint("SSL_2: ", request.environ)
    udn = request.environ.get('HTTP_X_SSL_CLIENT_S_DN')
    vuser = "UNAUTHORIZED_USER"
    with mydb_session() as s:
        results = sensenrm_db.validate_user(s, udn)
        if results:
            vuser = "AUTHORIZED_USER"
    return """
MRM-info: {}
Version-info: {}
NRMHost: {}
SSL-Verified: {}
SSL-DN: {}
IP: {}
AUTHZ-USER: {}
""".format(
    title_info,
    version_info,
    request.environ.get('HTTP_X_MYHOST'),
    request.environ.get('HTTP_X_SSL_CLIENT_VERIFY'),
    request.environ.get('HTTP_X_SSL_CLIENT_S_DN'),
    request.environ.get('HTTP_X_REAL_IP'),
    vuser)

if __name__ == '__main__':
    #application.run(port=8080, debug=True)
    application.run(port=nrm_config["port"], ssl_context=context, threaded=True, debug=True)
