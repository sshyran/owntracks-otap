#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__    = 'Jan-Piet Mens <jpmens()gmail.com>'
__copyright__ = 'Copyright 2014 Jan-Piet Mens'
__license__   = """Eclipse Public License - v 1.0 (http://www.eclipse.org/legal/epl-v10.html)"""

import os
import sys
import logging
import bottle
import bottle_jsonrpc   # https://github.com/olemb/bottle_jsonrpc/
from bottle import response, template, static_file, request
import zipfile
import owntracks
from owntracks import cf
from owntracks.dbschema import db, Otap, Versioncheck, createalltables, dbconn, fn
import time
import hashlib
from distutils.version import StrictVersion
import warnings
import base64
import textwrap
import paho.mqtt.publish as mqtt

log = logging.getLogger(__name__)

with warnings.catch_warnings():
    ''' Suppress cffi/vengine_cpy.py:166: UserWarning: reimporting '_cffi__x332a1fa9xefb54d7c' might overwrite older definitions '''
    warnings.simplefilter('ignore')

    import nacl.secret
    import nacl.utils
    from nacl.encoding import Base64Encoder

def _keycheck(secret):
    ''' <secret> is a base64-encoded, encrypted payload. Decrypt and
        verify content '''

    authorized = False

    key = base64.b64decode(cf.otckey)
    box = nacl.secret.SecretBox(key)

    try:
        encrypted = base64.b64decode(secret)
        nonce = encrypted[0:24]
        print base64.b64encode(nonce)
        # FIXME: invalidate nonce

        plaintext = box.decrypt(encrypted)
        if plaintext == b'OvEr.THe.aIR*':
            authorized = True
    except Exception, e:
        log.error("Decryption says {0}".format(str(e)))


    return authorized

def list_jars():
    ''' Obtain a list of JAR files, and return a sorted list of versions '''

    versions = []
    for f in os.listdir(cf.jardir):
        if f.startswith('.'):
            continue
        path = os.path.join(cf.jardir, f)
        if os.path.isfile(path):
            versions.append(f.replace('.jar', ''))

    versions.sort(key=StrictVersion)
    return versions

def notify(top, message):
    ''' Publish an MQTT notification to cf.notify + top '''

    if cf.notify is None:
        return

    topic = cf.notify + "/" + top
    payload = message

    try:
        mqtt.single(topic, payload, qos=1, retain=False, hostname='localhost',
            port=1883)
    except Exception, e:
        log.error("Cannot MQTT publish: {0}".format(str(e)))
        pass


@bottle.route('/')
def index():
    return "(OTAP)"


#   ____  ____   ____ 
#  |  _ \|  _ \ / ___|
#  | |_) | |_) | |    
#  |  _ <|  __/| |___ 
#  |_| \_\_|    \____|
#                     

class Methods(object):

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

        message = "IMEI {0} ({1}/{2}) added".format(imei, custid, tid)
        notify('add_imei', message)
        return message

    def deliver(self, otckey, imei, version):
        ''' Update IMEI in database and set version to be delivered.
            n.nn.nn means that version, "latest" means current highest version,
            and "*" means highest version existing even if that is introduced
            at a later point in time. '''

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

        message = "{0} will get {1} at next OTAP".format(imei, version)
        notify('deliver', message)
        return message

    def purge(self, otckey, version):
        ''' purge JAR version from filesystem, ensuring that version is
            not configured as 'deliver' for devices. '''

        if _keycheck(otckey) == False:
            return "NOP"

        version = version.replace(' ', '')

        n = None
        try:
            query = (Otap.select(fn.COUNT(Otap.imei).alias('numdeliver')).where(Otap.deliver == version).get())
            n = query.numdeliver or 0
        except Exception, e:
            raise

        if n != 0:
            return "Cannot purge this version: {0} clients are expecting it".format(n)

        jarfile = "{0}/{1}.jar".format(cf.jardir, version)
        if not os.path.isfile(jarfile):
            return "No such version here"

        try:
            os.remove(jarfile)
        except Exception, e:
            s = "Error removing {0}: {1}".format(jarfile, str(e))
            log.error(s)
            return s

        message = "{0} removed".format(jarfile)
        notify('purge', message)
        return message


    def block(self, otckey, imei, bl):
        ''' Set block in db for IMEI. If IMEI == 'ALL', then for all '''

        if _keycheck(otckey) == False:
            return "NOP"

        imei = imei.replace(' ', '')
        nrecs = None
        try:
            query = Otap.update(block = bl)
            if imei != 'ALL':
                query = query.where(Otap.imei == imei)
            nrecs = query.execute()
        except Exception, e:
            s = "Cannot update db: {0}".format(str(e))
            log.error(s)
            return s

        message = "%s updates set to block=%s" % (nrecs, bl)
        notify('blocker', message)
        return message

    def show(self, otckey, imei):
        ''' Show content of database. If IMEI specified, then just that one. '''

        if _keycheck(otckey) == False:
            return "NOP"

        results = []

        query = (Otap.select())
        if imei is not None:
            query = query.where(Otap.imei == imei)
        query = query.order_by(Otap.tid.asc())
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

    def find(self, otckey, tid):
        ''' Find a TID in the database and show info. '''

        results = []
        if _keycheck(otckey) == True:

            query = (Otap.select())
            query = query.where(Otap.tid == tid)
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

    def showconfig(self, otckey, custid):
        ''' Print configuration for the Greenwich OwnTracks Edition '''

        url = request.url   # http://localhost/rpc

        params = {
            'url'  :  url.replace('/rpc', ''),
            'custid' : custid,
        }

        res = ''
        if _keycheck(otckey) == True:
            res = res + "set otapURI={url}/{custid}/otap.jad\n".format(**params)
            res = res + "set notifyURI={url}/{custid}/notify=@\n".format(**params)
            res = res + "set versionURI={url}/{custid}/version\n".format(**params)

        return res


bottle_jsonrpc.register('/rpc', Methods())


def agentinfo():

    device = 'unknown'
    imei = '000000000000000'

    user_agent = request.environ.get('HTTP_USER_AGENT')
    try:
        # "TC65i/123456789012345 Profile/IMP-NG Configuration/CLDC-1.1"
        user_agent = user_agent.split(' ')[0]
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

@bottle.route('/<custid>/<word:re:(version|version.php)>', method='POST')
def versioncheck(custid, word):

    device, imei = agentinfo()

    current_version = bottle.request.body.read()

    upgrade = 0
    settings = []
    new_version = ""
    tid = ""

    try:
        o = Otap.get(Otap.imei == imei)

        tid = o.tid or '??'
        new_version = o.deliver

        o.reported = current_version
        o.save()

        if o.block == 0 and o.deliver is not None and current_version != o.deliver:
            upgrade = 1

            if o.settings is not None:
                try:
                    for kv in o.settings.split(';'):
                        print "KV===", kv
                        k, v = kv.split('=')
                        settings.append(dict(key=k, val=v))
                except:
                    pass


    except Otap.DoesNotExist:
        log.info("Requested OTAP IMEI {0} doesn't exist in database".format(imei))
    except Exception, e:
        log.error("Cannot get OTAP record for {0} from DB: {1}".format(imei, str(e)))

    item = {
        'imei'    : imei,
        'version' : current_version,
        'tstamp'  : time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(time.time()))),
        'upgrade' : upgrade,
        'tid'     : tid,
        'new_version' : new_version,
        'custid'      : custid,
    }
    try:
        vlog = Versioncheck(**item)
        vlog.save()
    except Exception, e:
        log.error("Cannot INSERT versioncheck log for {0} into DB: {1}".format(imei, str(e)))

    resp = {
        'upgrade'     : upgrade,
        'new_version' : new_version,
        'settings'    : settings,
        }

    message = "{imei} ({custid}/{tid}) has {version}; IHAVE {new_version}. upgrade={upgrade} {tstamp}".format(**item)
    notify('version', message)

    return resp

def get_midlet_version(f):
    ''' Read the .JAR (.zip) file at the open file `f' and extract its MANIFEST
        from which we obtain the MIDlet-Version and return that. '''

    version = None
    try:
        manifest = 'META-INF/MANIFEST.MF'

        f.seek(0)
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

# "POST /dev/notify=123456789012345 HTTP/1.1" 200 0 "-" "TC65i/356612028111492 Profile/IMP-NG Configuration/CLDC-1.1"
@bottle.route('/<custid>/notify=<clientid>', method="POST")
def otap_notify(custid, clientid):
    device, imei = agentinfo()
    otap_result = bottle.request.body.read()
    otap_result = otap_result.rstrip()

    log.info('OTAP notifyURI for cust={0} / {1} IMEI={2}'.format(custid, device, imei))

    item = {
        'tid'       : "",
        'device'    : device,
        'imei'      : imei,
        'result'    : otap_result,
        'tstamp'    : time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(time.time()))),
        'custid'    : custid,
    }
    try:
        o = Otap.get(Otap.imei == imei, Otap.custid == custid)

        item['tid'] = o.tid or "??"
    except:
        pass

    message = "Upgrade result for {custid}/{tid} ({device}) {imei}: {result}  {tstamp}".format(**item)
    notify(item.get('tid', 'xxx'), message)

    return ""

# --- OTAP (download JAD)
# This is invoked by the device when it wants to initiate OTAP. The
# URI *must* end in ".jad" or the device will not handle OTAP
#
# set otapURI=http://localhost/cust/otap.jad
# "GET /dev/otap.jad HTTP/1.1" 200 8 "-" "TC65i/356612028111492 Profile/IMP-NG Configuration/CLDC-1.1"
#
@bottle.route('/<custid>/otap.jad', method="GET")
def otap_get(custid):
    device, imei = agentinfo()

    log.info('OTAP request for cust={0} / {1} IMEI={2}'.format(custid, device, imei))

    tid = ""
    deliver = None
    try:
        o = Otap.get(Otap.imei == imei, Otap.custid == custid)

        tid = o.tid or "??"

        if o.block == 0 and o.deliver is not None:
            deliver = o.deliver


    except Otap.DoesNotExist:
        log.info("Requested OTAP cust={0}/IMEI={1} doesn't exist in database".format(custid, imei))
        return bottle.HTTPResponse(status=404, body="NOTFOUND")
    except Exception, e:
        log.error("Cannot get OTAP record for {0} from DB: {1}".format(imei, str(e)))
        return bottle.HTTPResponse(status=404, body="NOTFOUND")

    if deliver is not None:
        if deliver == '*':
            deliver = list_jars()[-1]

        jarfile = "{0}/{1}.jar".format(cf.jardir, deliver)
        try:
            statinfo = os.stat(jarfile)
            octets = statinfo.st_size

            response.content_type = 'text/vnd.sun.j2me.app-descriptor'
            response.set_header('X-JARversion', deliver)
            response.headers['Content-Disposition'] = 'attachment; filename="OwnTracks.jad"'

            params = {
                'octets'    : octets,
                'jarURL'    : "%s/%s/OwnTracks.jar" % (cf.jarurl, deliver),
                'deliver'   : deliver,
            }

            JAD = """\
               MIDlet-1: AppMain,,general.AppMain
               MIDlet-Jar-Size: {octets}
               MIDlet-Jar-URL: {jarURL}
               MIDlet-Name: OwnTracks
               MIDlet-Permissions: javax.microedition.io.Connector.http, javax.microedition.io.Connector.https, javax.microedition.io.Connector.ssl, javax.microedition.io.Connector.socket
               MIDlet-Vendor: Choral
               MIDlet-Version: {deliver}
               MicroEdition-Configuration: CLDC-1.1
               MicroEdition-Profile: IMP-NG
            """

            log.debug("OTAP: returning JAD descriptor")

            message = "Upgrade starting on {custid}/{tid} ({device}) {imei} {deliver}".format(tid=tid, device=device, imei=imei, deliver=deliver, custid=custid)
            notify('OTAupgrades', message)
            return textwrap.dedent(JAD.format(**params))

        except Exception, e:
            log.error("OTAP: {0} wanted {1} but {2}".format(imei, deliver, str(e)))
            return bottle.HTTPResponse(status=404, body="ENOENT")

        log.debug('OTAP: about to deliver {0} to {1}'.format(deliver, imei))


    log.info('OTAP request for cust={0} / {1} IMEI={2} denied: NOTFORYOU'.format(custid, device, imei))
    return bottle.HTTPResponse(status=404, body="NOTFORYOU")

# --- OTAP (download JAR)
# This is invoked by the device when it wants to retrieve the JAR
# file. We just send out the static file. I could use Bottle's static_file
# but I want the filename to be 'OwnTracks.jar' so return a file object.
#
# "GET /jars/0.10.65.jar HTTP/1.1" 200 241748 "-" "TC65i/123456789012345 Profile/IMP-NG Configuration/CLDC-1.1"

@bottle.route('/jars/<version:re:.*>/OwnTracks.jar', method='GET')
def jarfile(version):

    jarfile = "{0}/{1}.jar".format(cf.jardir, version)

    try:
        statinfo = os.stat(jarfile)
        octets = statinfo.st_size

        response.content_type = 'application/java-archive'
        response.headers['Content-Length'] = str(octets)
        log.info("Delivering {0}".format(jarfile))
        f = open(jarfile, 'rb')
        return f
    except Exception, e:
        log.error("Can't serve JAR {0}: {1}".format(version, str(e)))
        return bottle.HTTPResponse(status=404, body="ENOENT")


@bottle.route('/jarupload', method='POST')
def jarupload():

    otckey  = request.forms.get('otckey')
    force   = request.forms.get('force')
    upload  = request.files.get('jar')
    name, ext = os.path.splitext(upload.filename)

    overwrite=False
    if force == '1':
        overwrite = True

    if otckey is None:
        return bottle.HTTPResponse(status=403, body="NO KEY")
    if _keycheck(otckey) is False:
        return bottle.HTTPResponse(status=403, body="BAD KEY")

    #print "filename = ", upload.filename
    #print "c-type   = ", upload.content_type
    #print "c-len    = ", upload.content_length
    #print "name     = ", name
    #print "ext      = ", ext

    midlet_version = None
    try:
        midlet_version = get_midlet_version(upload.file)
    except Exception, e:
        return bottle.HTTPResponse(status=415, body=str(e))

    if midlet_version is None:
        return bottle.HTTPResponse(status=415, body="NO MIDLET VERSION")

    upload.file.seek(0)

    if not os.path.exists(cf.jardir):
        os.makedirs(cf.jardir)

    path = "{0}/{1}.jar".format(cf.jardir, midlet_version)
    try:
        upload.save(path, overwrite=overwrite)
        log.info("Saved uploaded JAR as {0}".format(path))
    except Exception, e:
        s = "Cannot save {0}: {1}".format(path, str(e))
        log.error(s)
        return s


    message = "JAR version {0} stored as {1}".format(midlet_version, path)
    notify('jarupload', message)
    return message
    # return json.dumps(resp, sort_keys=True, indent=2)


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
