#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__    = 'Jan-Piet Mens <jpmens()gmail.com>'
__copyright__ = 'Copyright 2014 Jan-Piet Mens'

import sys
import pyjsonrpc
import os
import hashlib
import base64
from docopt import docopt
import warnings
from requests_toolbelt import MultipartEncoder
import requests
import json

with warnings.catch_warnings():
    ''' Suppress cffi/vengine_cpy.py:166: UserWarning: reimporting '_cffi__x332a1fa9xefb54d7c' might overwrite older definitions '''
    warnings.simplefilter('ignore')

    import nacl.secret
    import nacl.utils
    from nacl.encoding import Base64Encoder

version = '0.12'
secret_text = b"OvEr.THe.aIR*"

def make_secret(message):
    key = base64.b64decode(os.getenv("OTC_KEY"))
    box = nacl.secret.SecretBox(key)
    nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
    encrypted = box.encrypt(message, nonce)

    b64 = base64.b64encode(encrypted)
    return b64

class RPC(object):
    def __init__(self, otc_url, otc_secret):
        self.server = pyjsonrpc.HttpClient(
            url = "%s/rpc" % otc_url,
            username = None,
            password = None,
            )

    def _request(self, cmd, *args):

        b64 = make_secret(secret_text)

        try:
            return self.server.call(cmd, b64, *args)
        except Exception, e:
            print("Error talking to server: {0}".format(str(e)))
            return None

    def ping(self):
        return self._request('ping')

    def show(self, imei=None):
        return self._request('show', imei)

    def find(self, tid=None):
        return self._request('find', tid)

    def jars(self):
        return self._request('jars')

    def add(self, imei, custid, tid):
        return self._request('add_imei', imei, custid, tid)

    def deliver(self, imei, version):
        return self._request('deliver', imei, version)

    def purge(self, version):
        return self._request('purge', version)

    def block(self, imei, bl=0):
        return self._request('block', imei, bl)

    def unblock(self, imei, bl=0):
        return self._request('block', imei, bl)

    def showconfig(self):
        return self._request('showconfig')

def print_devices(data):
    print "BLOCK IMEI             CUSTID    TID  Reported   Deliver"
    for item in data:
        print "%(block)5d %(imei)-16s %(custid)-10s %(tid)-3s %(reported)-10s %(deliver)-10s" % item

if __name__ == '__main__':
    usage = '''OTAP Control

    Usage:
      otc ping
      otc show [<imei>]
      otc find <tid>
      otc jars
      otc add <imei> <custid> <tid>
      otc deliver <imei> <version>
      otc block [--all] [<imei>]
      otc unblock [--all] [<imei>]
      otc upload <filename>
      otc purge <version>
      otc versioncheck <imei> <custid> <version>
      otc otap <imei> <custid>
      otc config

      otc (-h | --help)
      otc --version

    Options:
      -h --help     Show this screen.
      --version     Show version.
    '''

    otc_url = os.getenv("OTC_URL")
    if otc_url is None:
        print "Requires OTC_URL in environment"
        sys.exit(2)
    if otc_url.endswith('/'):
        otc_url = otc_url[0:-1]

    otc_key = os.getenv("OTC_KEY")
    if otc_key is None:
        print "Requires OTC_KEY in environment"
        sys.exit(2)

    rpc = RPC(otc_url, otc_key)

    args = docopt(usage, version=version)

    if args['ping']:
        print rpc.ping()

    if args['show']:
        data = rpc.show(args['<imei>'])
        if data is not None:
            print_devices(data)
    if args['find']:
        data = rpc.find(args['<tid>'])
        if data is not None:
            print_devices(data)

    if args['jars']:
        jarlist = rpc.jars()
        print "\n".join(jarlist)

    if args['add']:
        print rpc.add(args['<imei>'], args['<custid>'], args['<tid>'])

    if args['deliver']:
        print rpc.deliver(args['<imei>'], args['<version>'])

    if args['purge']:
        print rpc.purge(args['<version>'])

    if args['showconfig']:
        print rpc.showconfig()

    if args['block'] or args['unblock']:
        imei = args['<imei>']
        if args['--all']:
            imei = 'ALL'

        if imei is None:
            print "Nothing to block"
            sys.exit(0)

        bl = 0
        if args['block']:
            bl = 1
        print rpc.block(imei, bl)

    if args['upload']:
        # No uploads with RPC (content too large), so we have to do this
        # "traditionally".

        filepath = args['<filename>']

        try:
            f = open(filepath, 'rb')
        except Exception, e:
            print "Can't open file {0}: {1}".format(filepath, str(e))
            sys.exit(2)

        url = '%s/jarupload' % otc_url

        b64 = make_secret(secret_text)
        m = MultipartEncoder(
            fields = {
                'otckey' : b64,
                'jar'   : ('file', f, 'application/binary')
            }
        )

        r = requests.post(url, data=m, headers={'Content-Type' : m.content_type})
        print r.text
        f.close()

    if args['versioncheck']:
        imei = args['<imei>']
        custid = args['<custid>']
        current_version = args['<version>']

        print "Testing Versioncheck for IMEI {0} ({1})...".format(imei, current_version)

        headers = {
            'User-Agent'    : 'SIMU/{0}'.format(imei),
        }

        url = '%s/%s/version' % (otc_url, custid)

        payload = current_version
        resp = requests.post(url, headers=headers, data=payload)

        print json.dumps(resp.json(), indent=4)


    if args['otap']:
        imei = args['<imei>']
        custid = args['<custid>']

        print "Testing OTAP for cust={0}/IMEI={1} ...".format(custid, imei)

        headers = {
            'User-Agent'    : 'SIMU/{0}'.format(imei),
        }

        url = '%s/%s/otap.jad' % (otc_url, custid)

        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print "Response: {0} {1}".format(resp.status_code, resp.text)
        else:
            print(resp.headers)
            print resp.content


