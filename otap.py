#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__    = 'Jan-Piet Mens <jpmens()gmail.com>'
__copyright__ = 'Copyright 2014 Jan-Piet Mens'

import os
import sys
import bottle
import bottle_jsonrpc   # https://github.com/olemb/bottle_jsonrpc/
from bottle import response, template, static_file, request
import zipfile

@bottle.route('/')
def index():
    return "(click)"


#   ____  ____   ____ 
#  |  _ \|  _ \ / ___|
#  | |_) | |_) | |    
#  |  _ <|  __/| |___ 
#  |_| \_\_|    \____|
#                     

class Methods(object):
    #def add(self, a, b):
    #    return a + b

# FIXME: we need the following commands:
# blockall (true/false)      block all from otap
# show versions
# add IMEI TID version
# del IMEI
# set IMEI deliverversion
# set all deliverversion


    def versions(self, data):
        print data
        return { 'status' : 'fine' }

bottle_jsonrpc.register('/rpc', Methods())


#    ___ _____  _    ____  
#   / _ \_   _|/ \  |  _ \ 
#  | | | || | / _ \ | |_) |
#  | |_| || |/ ___ \|  __/ 
#   \___/ |_/_/   \_\_|    
#                          


# --- VERSIONCHECK
# If the Greenwich is configured with a `versionURI`, it will periodically
# (first at startup and then every `versionInterval` seconds -- default: 3
# hours) perform a HTTP POST to that URI in order to be informed on whether the
# device should or should not attempt an OTAP upgrade
#
# curl -X POST --user-agent "XAK/123456789085147" -d 0.8.37 http://localhost:8810/version.php
#
# set versionURI=http://localhost/otap/CUST/version
#
# For legacy reasons, I support /custid/version and /custid/version.php (the `word'
# parameter is ignored)

@bottle.route('/otap/<custid>/<word:re:(version|version.php)>', method='POST')
def versioncheck(custid, word):

    user_agent = request.environ.get('HTTP_USER_AGENT')

    print "CUSTID = ", custid

    print "USER_AGENT=", user_agent

    return "HI"

def get_midlet_version(f):
    ''' Read the .JAR (.zip) file at the open file `f' and extract its MANIFEST
        from which we obtain the MIDlet-Version and return that. '''

    version = None

    try:
        manifest = 'META-INF/MANIFEST.MF'

        zf = zipfile.ZipFile(f, 'r')
        # info = zf.getinfo(manifest)
        # print info.filename, info.file_size

        mdata = zf.read(manifest)
        for line in mdata.splitlines():
            line = line.rstrip()
            if line.startswith("MIDlet-Version: "):
                version = line.split(': ')[1]
                break

        zf.close()
    except:
        raise

    return version

# --- OTAP (submit NOTIFICATION)
# This is invoked by the device when it has completed OTAP, depending
# on the setting of notifyURI
#
# notifyURI=http://localhost/otap/id=@

# POST /otap/id=PM
@bottle.route('/otap/id=<tid>', method="POST")
def otap(tid):
    print "POST for ", tid
    return "thanks for post"

# --- OTAP (download JAD)
# This is invoked by the device when it wants to initiate OTAP. The
# URI *must* end in ".jad" or the device will not handle OTAP
#
# set otapURI=http://localhost/otap/otap.jad
#
# GET /otap.jad
@bottle.route('/otap/otap.jad', method="GET")
def otap_get():
    print "GET"
    return "thanks for GET"


# curl -F jar=@filename http://localhost:8810/up

@bottle.route('/up', method='POST')
def upload():

    upload  = request.files.get('jar')
    name, ext = os.path.splitext(upload.filename)

    print "filename = ", upload.filename
    print "c-type   = ", upload.content_type
    print "c-len    = ", upload.content_length
    print "name     = ", name
    print "ext      = ", ext

    midlet_version = get_midlet_version(upload.file)
    if midlet_version is None:
        return "ERROR"

    jar_dir = "/tmp/ot"
    
    store_dir = "{0}/{1}".format(jar_dir, midlet_version)

    if not os.path.exists(store_dir):
        os.makedirs(store_dir)

    path = "{0}/OwnTracks.jar".format(store_dir)
    upload.save(path, overwrite=True)


    return "Thanks for the JAR: I got {0}".format(midlet_version)
    # return json.dumps(resp, sort_keys=True, indent=2)

@bottle.route('/dn')
def FIXME():
    f = open('/tmp/ot/0.8.9/OwnTracks.jar')

    return f

#  ---------------------------------------------------------------


bottle.debug(True)

if __name__ == '__main__':
    # Standalone web server
    bottle.run(reloader=True,
        host="localhost",
        port=8810)
else:
    # Running under WSGI
    application = bottle.default_app()