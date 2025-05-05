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
#####################################
# oscars_config and ssl_config sections must be updated
#

# Current server host information
nrm_config = {
    "host": "hostname",
    "port": port,  # like 8443
    "urnprefix": "urn:ogf:network:es.net:2019",
    "debug": 8  # debug level [0-9]
}

nrm_service = {
    # "l3vpn_model_insert": "./nrm-l3vpn.txt", # Static L3VPN model insert path
    "poll_duration": 60,  # minutes
    "default_delta_lifetime": 24 # 72 hours
}

# Configurations for sqlalchemy
nrmdb_config = {
    "type": "sqlite",
    "url": "nrmtb.db" # path to the db
}

# OSCARS access information
#oscars_config = {
#    "url": "hostname:8443",
#    "default_user": None,
#    "default_passwd": None,
#    "default_token": None,
#    "default_dn": None
#}
# For example,
#oscars_config = {
#    "url": "hostname:8443",
#    "default_user": "this_user",
#    "default_passwd": "this_passwd",
#    "default_token": "this_token_random_looking ",
#    "default_dn": "DC=org/DC=SENSE/O=LBNL/OU=People/CN=This User 1234"
#}

users_config = {
    "admin" : "CN=Name,O=ESnet,ST=CA,C=US",
    "mapfile" : "path_to_nrm-mapfile" # DN mapfile
         # mapfile format: DN group
         # e.g. "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=People/CN=Name" default
}

# Configurations for WSGI, should be the same in httpd-ssl.conf
ssl_config = {
    "capath":    "path_to_certificates",
    "hostcertpath": "path_to_sensenrm-cert.pem",
    "hostkeypath": "path_to_sensenrm-key.pem", 
    "httpsverify": False
}

log_config = {
    "basepath": "path_to_logs"
}
