#
# SENSE Resource Manager (SENSE-RM) Copyright (c) 2018, The Regents
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
#####################################
# oscars_config and ssl_config sections must be updated
#

# Current server host information
nrm_config = {
    "url": "https://dev-sense-nrm.es.net:8443",
    "urnprefix": "urn:ogf:network:es.net:2013",
    "debug": 4  # debug level [0-9]
}

nrm_service = {
    "poll_duration": 60,  # minutes
    "default_delta_lifetime": 240 # hours
}

# Configurations for sqlalchemy
nrmdb_config = {
    "type": "sqlite",
    "url": "./nrmdb.db"
}

# OSCARS access information
oscars_config = {
    "url": "oscars-dev2.es.net:443",     # Required for requests
    "default_user": None,     # Required for requests
    "default_passwd": None,   # Optional, but Only required for token retrieval
    "default_token": None,    # Required for requests
    "default_dn": None        # Optional 
}
# For example, 
#oscars_config = {
#    "url": "oscars-dev2.es.net:443",
#    "default_user": "this_user",
#    "default_passwd": "this_passwd",
#    "default_token": "this_token_random_looking ",
#    "default_dn": "DC=org/DC=SENSE/O=LBNL/OU=People/CN=This User 1234"
#}

# Configurations for WSGI, should be the same in httpd-ssl.conf
ssl_config = {
    "capath":    "/etc/grid-security/certificates",
    "hostcertpath": "/etc/grid-security/openssl/sensenrm-cert.pem",
    "hostkeypath": "/etc/grid-security/openssl/sensenrm-key.pem", 
    "httpsverify": False
}

log_config = {
    "basepath": "./logs"
}

