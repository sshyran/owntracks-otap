#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__    = 'Jan-Piet Mens <jpmens()gmail.com>'
__copyright__ = 'Copyright 2014 Jan-Piet Mens'

import os
import sys
import logging
import bottle
import bottle_jsonrpc   # https://github.com/olemb/bottle_jsonrpc/
from bottle import response, template, static_file, request
import zipfile
import owntracks
from owntracks import cf
from owntracks.dbschema import db, Otap, Versioncheck, createalltables, dbconn
import time
import hashlib
from distutils.version import StrictVersion

log = logging.getLogger(__name__)

def _keycheck(secret):
    ''' secret is a SHA256 hex hash. Compute our own hash and compare '''
    h = hashlib.sha256()
    h.update(cf.otckey)
    my_hash = h.hexdigest()

    if secret != my_hash:
        return False
    return True

def list_jars():
    ''' Obtain a list of JAR files, and return a sorted list of versions '''

    versions = []
    for f in os.listdir(cf.jardir):
        path = os.path.join(cf.jardir, f)
        if os.path.isfile(path):
            versions.append(f.replace('.jar', ''))

    versions.sort(key=StrictVersion)
    return versions

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

# FIXME: we need the following commands:
# blockall (true/false)      block all from otap
# show versions
# add IMEI TID version
# del IMEI
# set IMEI deliverversion
# set all deliverversion
# add IMEI cust TID



    def ping(self, otckey):
        auth = _keycheck(otckey)
        if auth is True:
            return "PONG"
        return "pong"

    def jars(self, otckey):
        ''' Return list of all JAR versions in jardir '''

        if _keycheck(otckey) == False:
            return "NOP"

        return list_jars()


    def add_imei(self, otckey, imei, custid, tid):
        ''' Add to database. If IMEI exists, other fields are updated. '''

        if _keycheck(otckey) == False:
            return "NOP"

        imei = imei.replace(' ', '')
        custid = custid.replace(' ', '')
        tid  = tid.replace(' ', '')

        try:
            o = Otap.get(Otap.imei == imei)

            o.custid  = custid
            o.tid     = tid
            o.block   = 0
            o.save()
        except Otap.DoesNotExist:
            item = {
                'imei'   : imei,
                'custid' : custid,
                'tid'    : tid,
                'block'  : 0,
            }
            try:
                o = Otap(**item)
                o.save()

                log.info("Stored OTAP IMEI {0} in database".format(imei))
            except Exception, e:
                log.error("Cannot store OTAP record for {0} in DB: {1}".format(imei, str(e)))
        except Exception, e:
            log.error("Cannot get OTAP record for {0} from DB: {1}".format(imei, str(e)))

        return "IMEI {0} added".format(imei)

    def deliver(self, otckey, imei, version):
        ''' Update IMEI in database and set version to be delivered '''

        if _keycheck(otckey) == False:
            return "NOP"

        imei = imei.replace(' ', '')
        version = version.replace(' ', '')

        if version == 'latest':
            # Get sorted versions and take highest
            version = list_jars()[-1]

        if version != '*':
            jarfile = "{0}/{1}.jar".format(cf.jardir, version)
            if not os.path.isfile(jarfile):
                return "No such version here"

        try:
            o = Otap.get(Otap.imei == imei)
            o.deliver = version
            o.save()
        except:
            return "Can't find IMEI {0} in DB".format(imei)

        return "{0} will get {1} at next OTAP".format(imei, version)

    def show(self, otckey, imei):

        if _keycheck(otckey) == False:
            return "NOP"

        results = []

        query = (Otap.select())
        if imei is not None:
            query = query.where(Otap.imei == imei)
        query = query.order_by(Otap.imei.asc())
        for q in query.naive():
            results.append({
                'imei'      : q.imei,
                'custid'    : q.custid,
                'tid'       : q.tid,
                'block'     : q.block,
                'reported'  : q.reported,
                'deliver'   : q.deliver,
                })

        return results


bottle_jsonrpc.register('/rpc', Methods())


def agentinfo():

    device = 'unknown'
    imei = '000000000000000'

    user_agent = request.environ.get('HTTP_USER_AGENT')
    try:
        parts = user_agent.split('/')
        if len(parts) == 2:
            device = parts[0]
            imei = parts[1]
    except:
        pass
    
    return device, imei


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
# The body of the POST is the current version number of its firmware
#
# set versionURI=http://localhost/otap/CUST/version
#
# For legacy reasons, I support /custid/version and /custid/version.php (the `word'
# parameter is ignored)

@bottle.route('/otap/<custid>/<word:re:(version|version.php)>', method='POST')
def versioncheck(custid, word):

    device, imei = agentinfo()

    print "CUSTID = ", custid

    print "device, imei: ", device, imei


    current_version = bottle.request.body.read()
    item = {
        'imei'    : imei,
        'version' : current_version,
        'tstamp'  : time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(time.time()))),
    }
    try:
        vlog = Versioncheck(**item)
        vlog.save()
    except Exception, e:
        log.error("Cannot INSERT versioncheck log for {0} into DB: {1}".format(imei, str(e)))

    upgrade = 0
    settings = []

    try:
        o = Otap.get(Otap.imei == imei)

        tid = o.tid or '??'

        o.reported = current_version
        o.save()

        if o.block == 0:
            upgrade = 1

            try:
                for kv in o.settings.split(';'):
                    print "KV===", kv
                    k, v = kv.split('=')
                    settings.append(dict(key=k, val=v))
            except:
                raise
                pass

        
    except Otap.DoesNotExist:
        log.info("Requested OTAP IMEI {0} doesn't exist in database".format(imei))
    except Exception, e:
        log.error("Cannot get OTAP record for {0} from DB: {1}".format(imei, str(e)))


    resp = {
        'upgrade'   : upgrade,
        'settings'  : settings,
        }

    return resp

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


# curl -F otckey=f0ac34ce3cbd715bafcae72f96bd914151c12e8d478bbb645d94d55cf54a1a14 -F jar=@filename http://localhost:8810/jarupload

@bottle.route('/jarupload', method='POST')
def jarupload():

    otckey  = request.forms.get('otckey')
    upload  = request.files.get('jar')
    name, ext = os.path.splitext(upload.filename)

    if otckey is None:
        return bottle.HTTPResponse(status=403, body="NO KEY")
    if _keycheck(otckey) is False:
        return bottle.HTTPResponse(status=403, body="BAD KEY")

    print "filename = ", upload.filename
    print "c-type   = ", upload.content_type
    print "c-len    = ", upload.content_length
    print "name     = ", name
    print "ext      = ", ext

    midlet_version = None
    try:
        midlet_version = get_midlet_version(upload.file)
    except Exception, e:
        return bottle.HTTPResponse(status=415, body=str(e))

    if midlet_version is None:
        return bottle.HTTPResponse(status=415, body="NO MIDLET VERSION")

    if not os.path.exists(cf.jardir):
        os.makedirs(cf.jardir)

    path = "{0}/{1}.jar".format(cf.jardir, midlet_version)
    try:
        upload.save(path, overwrite=True)
        log.info("Saved uploaded JAR as {0}".format(path))
    except Exception, e:
        log.error("Cannot save {0}: {1}".format(path, str(e)))


    return "Thanks for the JAR: I got {0}. Stored as {1}\n".format(midlet_version, path)
    # return json.dumps(resp, sort_keys=True, indent=2)

@bottle.route('/dn')
def FIXME():
    f = open('/tmp/ot/0.8.9/OwnTracks.jar')

    return f

#  ---------------------------------------------------------------


createalltables()
bottle.debug(True)

if __name__ == '__main__':
    # Standalone web server
    bottle.run(reloader=True,
        host="localhost",
        port=8810)
else:
    # Running under WSGI
    application = bottle.default_app()
