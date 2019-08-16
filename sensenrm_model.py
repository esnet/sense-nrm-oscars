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
## 

from datetime import tzinfo, timedelta, datetime
import dateutil.parser
import time
import uuid
import sys
import os
import fileinput
import sensenrm_oscars
import sensenrm_db
import json
from sensenrm_config import log_config, nrm_config, nrm_service

oscars_conn = sensenrm_oscars.nrm_oscars_connection()
mydb_session = sensenrm_db.db_session

class nrmModel(object):
    basePath = log_config["basepath"]
    l3vpnPath = ""
    #inputmodel = basePath+"/sensenrm_model_input.txt"
    #last_time = datetime.now()
    
    def __init__(self):
        self.obj=" "
        #self.last_time = self.get_delayed_time(-1)
        if "l3vpn_model_insert" in nrm_service:
            print("nrm_service_L3VPN_insert:" + nrm_service["l3vpn_model_insert"])
            self.l3vpnPath = nrm_service["l3vpn_model_insert"]
        else:
            print("nrm_service_L3VPN_insert_does_not_exist")

    def getUUID(self):
        nrmmodel_uuid = uuid.uuid5(uuid.NAMESPACE_URL, str(self.getTime()))
        return nrmmodel_uuid
        
    def getURL(self):
        nrmmodel_url = 'https://' + nrm_config["host"] + ':' + str(nrm_config["port"]) + '/sense-rm/api/sense/v1/models/' + str(self.getUUID())
        return nrmmodel_url
        
    def getAvailOK(self):
        tZERO = timedelta(0)
        class UTC(tzinfo):
          def utcoffset(self, dt):
            return tZERO
          def tzname(self, dt):
            return "UTC"
          def dst(self, dt):
            return tZERO
        utc = UTC()
        #t21 = datetime.now(utc)
        t21 = datetime.now()
        t21 = t21.replace(microsecond=0)
        with mydb_session() as s:
            last_time = sensenrm_db.get_sys_lasttime(s)
            model_change = sensenrm_db.get_sys_lastchange(s)
        if (nrm_config["debug"]>2): 
            print "MODEL: current time: ", t21
            print "MODEL: Since last time: ", last_time
        tdiff = t21 - last_time
        if (nrm_config["debug"]>2): 
            print "MODEL: Avail in: ", (nrm_service["poll_duration"]*60) - tdiff.total_seconds()

        #if tdiff.total_seconds() < (nrm_service["poll_duration"]*60):
        if (model_change == 1) or (tdiff.total_seconds() > (nrm_service["poll_duration"]*60)):
            return True
        else:
            return False

    def time_rfc1123():
        now = datetime.now()
        stamp = mktime(now.timetuple())
        rfc1123_time = format_date_time(stamp)
        return rfc1123_time

    def setLastTime(self):
        with mydb_session() as s:
            #last_time = self.get_delayed_time(0)
            last_time = datetime.now()
            if (nrm_config["debug"]>2):
                print "MODEL: Set last time: ", last_time
            sensenrm_db.update_sys_value(s, "last_model_time", last_time)

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

    def get_delayed_time(self, delay_days):
        tZERO = timedelta(0)
        class UTC(tzinfo):
          def utcoffset(self, dt):
            return tZERO
          def tzname(self, dt):
            return "UTC"
          def dst(self, dt):
            return tZERO
        utc = UTC()
        mytime1=datetime.now(utc)
        if delay_days != 0:
            newday = mytime1.day+delay_days
            newmonth = mytime1.month
            daycomp = 30
            if (mytime1.month == 2):
                daycomp = 28
            if (mytime1.day+delay_days > daycomp):
                newday = mytime1.day+delay_days - daycomp
                newmonth = mytime1.month + 1
            mytime1=datetime(mytime1.year, newmonth, newday, mytime1.hour, mytime1.minute, mytime1.second, tzinfo=utc)
        return mytime1
    
    def writeModel(self, nrm_uuid, modelcontent):
        timed_file = datetime.fromtimestamp(time.mktime(datetime.now().timetuple())).strftime('%Y%m%d-%H%M%S')
        output_file = self.basePath+"/model_" + str(timed_file) + "_" + str(nrm_uuid) + ".txt"
        if (nrm_config["debug"]>3):
            print "MODEL: OUTPUT_PATH=", output_file
        fo = open(output_file, 'w')
        fo.write(modelcontent)
        fo.close()

        return True
    
    def getModel(self):
        if not self.getAvailOK() :
            #if (nrm_config["debug"]>3): print "MODEL: LAST_TIME=", self.last_time
            with mydb_session() as s:
                old_id, old_href, old_creationtime, old_model = sensenrm_db.get_sys_lastmodel(s)
            return [{"id":old_id,"href":old_href,"creationTime":old_creationtime,"model":old_model}], False
            #return [{"id":str(""),"href":str(self.getURL()),"creationTime":str(self.getTime()),"model":str("")}], self.last_time, False

        urnpr = nrm_config["urnprefix"]

        self.setLastTime()
        modelcontent="@prefix sd:    <http://schemas.ogf.org/nsi/2013/12/services/definition#> .\n@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix owl:   <http://www.w3.org/2002/07/owl#> .\n@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .\n@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix nml:   <http://schemas.ogf.org/nml/2013/03/base#> .\n@prefix mrs:   <http://schemas.ogf.org/mrs/2013/12/topology#> .\n\n"
        modelcontent = modelcontent + '<' + urnpr + '::ServiceDefinition:EVTS.A-GOLE>\n        a                       sd:ServiceDefinition ; \n        nml:belongsTo   <' + urnpr + '::ServiceDomain:EVTS.A-GOLE> ; \n        nml:name    "OSCARS based Network RM Service" ; \n        sd:serviceType  "http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE" . \n '
        modelcontent = modelcontent + '<' + urnpr + '::ServiceDefinition:L2-MP-ES>\n        a                       sd:ServiceDefinition ; \n        nml:belongsTo   <' + urnpr + '::ServiceDomain:EVTS.A-GOLE> ; \n        nml:name    "OSCARS based Network RM Layer-2 Multi-Point Service" ; \n        sd:serviceType  "http://services.ogf.org/nsi/2018/06/descriptions/l2-mp-es" . \n\n '
        
        try:
            resp = oscars_conn.get_avail_topo()
        except Exception as e:
            if (nrm_config["debug"]>0): print "MODEL EXCEPT: ", e
            raise

        with mydb_session() as s:
            sensenrm_db.remove_expired_deltas(s) # Checking expired deltas
            allJunctions = s.query(sensenrm_db.oJunction).all();
            if (nrm_config["debug"]>3):
                print "\nMODEL: num of junctions = ", len(allJunctions)
            myjlist = ""
            jDetails = [{"id": f.id, "name": f.name, "port_urn": f.port_urn, "vlan_expression": f.vlan_expression, "ingress_bandwidth": f.ingress_bandwidth, "egress_bandwidth": f.egress_bandwidth} for f in allJunctions]
            for f in allJunctions:
                fid = f.id.replace('/', '_')
                bidplist=""
                if len(f.bidports) > 0 :
                    bports = f.bidports.split(",")
                    bidcount=0
                    for bp in bports:   # delta_id:netlab-7750sr12-rt2:10/1/5:2210
                        if (len(bp) > 0) :
                            bpsws = bp.split(":")
                            bpsw = bpsws[1]+":"+bpsws[2].replace('/', '_')
                            bpvl = bpsws[3]
                            if (fid == bpsw) :
                                bidcount=bidcount+1
                                if bidcount > 1:
                                    bidplist = bidplist + ','
                                bidplist=bidplist + '<' + urnpr + '::' + bpsw + ':+:vlanport+' + bpvl + '>'
                
                # BandwidthService
                modelcontent = modelcontent + '<' + urnpr + '::' + fid + ":+:BandwidthService>\n        a                       mrs:BandwidthService ; \n        mrs:availableCapacity   " + '"' + str(f.ingress_bandwidth) + '"^^xsd:long ;\n        mrs:reservableCapacity   "' + str(f.ingress_bandwidth) + '"^^xsd:long ;\n        mrs:maximumCapacity   ' + '"' + str(f.ingress_bandwidth) + '"^^xsd:long ;\n        mrs:minimumCapacity   "100"^^xsd:long ;\n       mrs:type                "guaranteedCapped" ;\n        mrs:unit                "mbps" ;\n       nml:belongsTo           <' + urnpr + '::' + fid + ':+> .\n\n' 
                # vlan
                modelcontent = modelcontent + '<' + urnpr + '::' + fid + ':+:vlan>\n        a              nml:LabelGroup ;\n        nml:belongsTo  <' + urnpr + '::' + fid + ':+> ;\n        nml:labeltype  <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> ;\n        nml:values     "' + f.vlan_expression.replace(':', '-') + '" .\n\n' 
                
                # vlan detail
                modelcontent = modelcontent + '<' + urnpr + '::' + fid + ':+>\n        a                  nml:BidirectionalPort ;\n        nml:belongsTo      <' + urnpr + ':> ;\n'
                if len(bidplist) > 0:
                    modelcontent = modelcontent + '        nml:hasBidirectionalPort       ' + bidplist + ' ;\n'
                modelcontent = modelcontent + '        nml:encoding       <http://schemas.ogf.org/nml/2012/10/ethernet> ;\n        nml:hasLabelGroup  <' + urnpr + '::' + fid + ':+:vlan> ;\n        nml:hasService     <' + urnpr + '::' + fid + ':+:BandwidthService> .\n\n' 
                
                myjlist = myjlist + '<' + urnpr + '::' + fid + ':+>'
                if allJunctions.index(f) != len(allJunctions)-1:
                    myjlist = myjlist + ', '

            ## existing active vlans
            mObjs = s.query(sensenrm_db.oSwitch).filter(sensenrm_db.oSwitch.active == 1).all()
            adlist=[] # activeDeltaList
            subninsert=""
            for mObj in mObjs:
                # GET oDelta.switch_list and split with , for "netlab-7750sr12-rt2:10/1/5:2210,netlab-mx960-rt1:xe-11/2/0:2210"
                if (nrm_config["debug"]>6): 
                    print "MODEL: SWITCHID=", mObj.id
                    print "MODEL: DELTAID=", mObj.deltaid
                mDelta = s.query(sensenrm_db.oDelta).filter(sensenrm_db.oDelta.id == mObj.deltaid).first()
                mydeltaid = ""
                mydeltavlan = ""
                mydeltavlanEmpty = True
                if len(mDelta.altid) > 0:
                    mydeltaid = mDelta.altid
                else:
                    mydeltaid = mObj.deltaid
                if len(mDelta.altvlan) > 0:
                    mydeltavlan = mDelta.altvlan # there is always one
                    mydeltavlanEmpty = False
                mydeltaurs = mDelta.urs # there is always one
                    
                dswitch=[]
                scontent=""
                if (mDelta is not None) and (mDelta.status == "COMMITTED") and (len(mDelta.switch_list) > 0) :
                    addToModel = False
                    if (mDelta.id not in adlist):
                        adlist.append(mDelta.id)
                        addToModel = True
                    if mydeltavlanEmpty :
                        mydeltavlan = str(mObj.vlanport) # there is always one
                    if (nrm_config["debug"]>6): 
                        print "MODEL_DELTA_ID=", mDelta.id
                        print "MODEL_DELTA_ID_MY=", mydeltaid
                        print "MODEL_DELTA_VLAN_MY=", mydeltavlan

                    if addToModel:
                        dswitch = mDelta.switch_list.split(",") 
                        if (nrm_config["debug"]>6): 
                            print "MODEL_DELTA_SWITCH=", mDelta.switch_list
                            print "MODEL_DELTA_IDs=", adlist
                        for ds in dswitch:
                            if (len(ds) > 0) :
                                ds1 = ds.split(":")  # ds1[0]="netlab-7750sr12-rt2"
                                ds2 = ds1[1].replace('/', '_')  # ds2 = "10_1_5"
                                scontent = scontent + '<' + urnpr + '::' + ds1[0] + ':' + ds2 + ':+:vlanport+' + ds1[2] + '>'
                                if dswitch.index(ds) != len(dswitch)-1:
                                    scontent = scontent + ', '
                        if (nrm_config["debug"]>6): print "MODEL_DELTA_SCONTENT=", scontent

                        dvlan = mydeltavlan.split(",")
                        durs = mydeltaurs.split(",")
                        for dv in dvlan:
                            if (len(dv) > 0) :
                                dvi = dvlan.index(dv)
                                modelcontent = modelcontent + '<' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+'+ mydeltaid +':' + durs[dvi] + ':vlan+' + str(dv)+'>\n        a                       mrs:SwitchingSubnet ; \n        nml:belongsTo   <' + urnpr + '::ServiceDomain:EVTS.A-GOLE> ; \n        nml:encoding    <http://schemas.ogf.org/nml/2012/10/ethernet> ; \n        nml:existsDuring    <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+'+ mydeltaid + ':' + durs[dvi] + ':vlan+' +str(dv)+':existsDuring> ; \n        nml:hasBidirectionalPort  ' + scontent + ' ; \n        nml:labelSwapping   true ; \n        nml:labelType   <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> . \n\n '

                if len(mDelta.altvlan) > 0:
                    mydeltavlan = mDelta.altvlan # there is always one
                # mObj.name = "netlab-7750sr12-rt2:10/1/5:2210"
                sname=mObj.name.split(":")
                sname1=sname[1].replace('/', '_')
                sport=sname[2]

                #dvlan = mydeltavlan.split(",")
                #durs = mydeltaurs.split(",")
                dvlan = mydeltavlan
                durs = mydeltaurs
                if (nrm_config["debug"]>7): 
                    print "MODEL: mydeltavlan:", mydeltavlan
                    print "MODEL: mydvlan:", dvlan
                #dvi = dvlan.index(sport)

                #modelcontent = modelcontent + '<' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + '>\n        a                 nml:BidirectionalPort ;\n        nml:belongsTo     <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs[dvi] + ':vlan+' + sport + '>,<' + urnpr + '::' + sname[0] + ':' + sname1 + ':+> ;\n        nml:encoding      <http://schemas.ogf.org/nml/2012/10/ethernet> ;\n        nml:existsDuring  <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs[dvi] + ':vlan+' + sport + ':existsDuring> ;\n        nml:hasLabel      <' + urnpr + '::' + sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':label+' + sport + '> ;\n        nml:hasService    <' + urnpr + '::' + sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':service+bw> ;\n        nml:name          "' + mObj.heldid+":"+mObj.deltaid +':'+mydeltaid+'" .\n\n'
                modelcontent = modelcontent + '<' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + '>\n        a                 nml:BidirectionalPort ;\n        nml:belongsTo     <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs + ':vlan+' + dvlan + '>,<' + urnpr + '::' + sname[0] + ':' + sname1 + ':+> ;\n        nml:encoding      <http://schemas.ogf.org/nml/2012/10/ethernet> ;\n        nml:existsDuring  <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs + ':vlan+' + dvlan + ':existsDuring> ;\n        nml:hasLabel      <' + urnpr + '::' + sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':label+' + sport + '> ;\n        nml:hasService    <' + urnpr + '::' + sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':service+bw> ;\n        nml:name          "' + mObj.heldid+":"+mObj.deltaid +':'+mydeltaid+'" .\n\n'
                # service+bw
                #modelcontent = modelcontent + '<' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':service+bw>\n        a                       mrs:BandwidthService ;\n        mrs:reservableCapacity  "' + str(mObj.reservedbw) + '"^^xsd:long ;\n        mrs:availableCapacity                "' + str(mObj.reservedbw) + '"^^xsd:long ;\n        mrs:type                "guaranteedCapped" ;\n        mrs:unit                "bps" ;\n        nml:belongsTo           <' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + '> ;\n        nml:existsDuring        <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs[dvi] + ':vlan+' + sport + ':existsDuring> .\n\n '
                modelcontent = modelcontent + '<' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':service+bw>\n        a                       mrs:BandwidthService ;\n        mrs:reservableCapacity  "' + str(mObj.reservedbw) + '"^^xsd:long ;\n        mrs:availableCapacity                "' + str(mObj.reservedbw) + '"^^xsd:long ;\n        mrs:type                "guaranteedCapped" ;\n        mrs:unit                "bps" ;\n        nml:belongsTo           <' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + '> ;\n        nml:existsDuring        <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs + ':vlan+' + dvlan + ':existsDuring> .\n\n '
                # existingDuring
                #modelcontent = modelcontent + '<' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs[dvi] + ':vlan+' + sport + ':existsDuring>\n        a          nml:Lifetime ;\n        nml:end    "' + mObj.time_end + '" ;\n        nml:start  "' + mObj.time_begin + '" .\n\n '
                modelcontent = modelcontent + '<' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs + ':vlan+' + dvlan + ':existsDuring>\n        a          nml:Lifetime ;\n        nml:end    "' + mObj.time_end + '" ;\n        nml:start  "' + mObj.time_begin + '" .\n\n '
                # label+vlanport
                #modelcontent = modelcontent + '<' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':label+' + sport + '>\n        a                 nml:Label ;\n        nml:belongsTo     <' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + '> ;\n        nml:existsDuring  <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs[dvi] + ':vlan+' + sport + ':existsDuring> ;\n        nml:labeltype     <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> ;\n        nml:value         "' + sport + '" .\n\n '
                modelcontent = modelcontent + '<' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + ':label+' + sport + '>\n        a                 nml:Label ;\n        nml:belongsTo     <' + urnpr + '::'+sname[0] + ':' + sname1 + ':+:vlanport+' + sport + '> ;\n        nml:existsDuring  <' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs + ':vlan+' + dvlan + ':existsDuring> ;\n        nml:labeltype     <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> ;\n        nml:value         "' + sport + '" .\n\n '
                # final insert
                #subninsert = subninsert + '<' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs[dvi] + ':vlan+' + sport + '>'
                subninsert = subninsert + '<' + urnpr + '::ServiceDomain:EVTS.A-GOLE:conn+' + mydeltaid + ':' + durs + ':vlan+' + dvlan + '>'

                if mObjs.index(mObj) != len(mObjs)-1:
                    subninsert = subninsert + ', '

            ## L3VPN static info 190816
            if ((len(self.l3vpnPath) > 0) and os.path.exists(self.l3vpnPath)):
                with open(self.l3vpnPath, 'r') as l3vpn_info:
                    l3vpnInfo = l3vpn_info.read()
                    modelcontent = modelcontent + l3vpnInfo

            ## nml:Toplogy
            modelcontent = modelcontent + '<' + urnpr + ':>\n        a                         nml:Topology ;\n        nml:existsDuring             [ a        nml:Lifetime ;\n                                      nml:end    "' + str(self.get_delayed_time(2)) + '" ; \n                                      nml:start    "' + str(self.getTime()) + '" \n                                     ] ;\n        nml:hasBidirectionalPort  ' + myjlist + ';\n        nml:hasService         <' + urnpr + '::ServiceDomain:EVTS.A-GOLE> ;\n         nml:name         "es.net" ;\n        nml:version         "' + str(self.getTime()) + '" .\n\n'
            
            ## ServiceDomain nml:SwitchingService
            modelcontent = modelcontent + '<' + urnpr + '::ServiceDomain:EVTS.A-GOLE>\n        a                         nml:SwitchingService ;\n'
            if len(subninsert) > 0:
                modelcontent = modelcontent + '        mrs:providesSubnet              ' + subninsert + ';\n'
            modelcontent = modelcontent + '        nml:encoding              <http://schemas.ogf.org/nml/2012/10/ethernet> ;\n        nml:hasBidirectionalPort  ' + myjlist + ';\n        nml:labelSwapping         true ;\n        nml:labeltype             <http://schemas.ogf.org/nml/2012/10/ethernet#vlan> ;\n        sd:hasServiceDefinition   <' + urnpr + '::ServiceDefinition:EVTS.A-GOLE> ;\n        sd:hasServiceDefinition   <' + urnpr + '::ServiceDefinition:L2-MP-ES> .\n\n'
            modelc = json.dumps(jDetails, indent = 4)

        if (nrm_config["debug"]>4):
            print '[{"id":', str(self.getUUID()),',"href":', str(self.getURL()),',"creationTime":', str(self.getTime()), '}]', str(self.getTime())
        #if (nrm_config["debug"]>7):
        #    print '[{"id":', str(self.getUUID()),',"href":', str(self.getURL()),',"creationTime":', str(self.getTime()),',"model":', str(modelc), '}]', str(self.getTime())
        
        if (nrm_config["debug"]>9):
            print "modelcontent=", modelcontent
        if (nrm_config["debug"]>8):
            self.writeModel(str(self.getUUID()), modelcontent)

        new_id = str(self.getUUID())
        new_href = str(self.getURL())
        new_creationtime = str(self.getTime())
        new_model = str(modelcontent)
        with mydb_session() as s:
            sensenrm_db.update_sys_value(s, "last_id", new_id)
            sensenrm_db.update_sys_value(s, "last_href", new_href)
            sensenrm_db.update_sys_value(s, "last_creationtime", new_creationtime)
            sensenrm_db.update_sys_value(s, "last_model", new_model)
            sensenrm_db.update_sys_value(s, "model_changed", 0)
        
        return [{"id":new_id,"href":new_href,"creationTime":new_creationtime,"model":new_model}], True
        #return [{"id":str(self.getUUID()),"href":str(self.getURL()),"creationTime":str(self.getTime()),"model":str(modelcontent)}], self.last_time, True
