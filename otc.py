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

with warnings.catch_warnings():
    ''' Suppress cffi/vengine_cpy.py:166: UserWarning: reimporting '_cffi__x332a1fa9xefb54d7c' might overwrite older definitions '''
    warnings.simplefilter('ignore')

    import nacl.secret
    import nacl.utils
    from nacl.encoding import Base64Encoder

version = '0.12'

class RPC(object):
    def __init__(self, otc_url, otc_secret):
        self.server = pyjsonrpc.HttpClient(
            url = "%s/rpc" % otc_url,
            username = None,
            password = None,
            )

        self.key = base64.b64decode(otc_secret)
        self.box = nacl.secret.SecretBox(self.key)

    def _request(self, cmd, *args):
        message = b"OvEr.THe.aIR*"
        nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
        encrypted = self.box.encrypt(message, nonce)

        b64 = base64.b64encode(encrypted)

        try:
            return self.server.call(cmd, b64, *args)
        except Exception, e:
            print("Error talking to server: {0}".format(str(e)))

    def ping(self):
        return self._request('ping')

    def show(self, imei=None):
        return self._request('show', imei)

    def jars(self):
        return self._request('jars')

    def add(self, imei, custid, tid):
        return self._request('add_imei', imei, custid, tid)

    def deliver(self, imei, version):
        return self._request('deliver', imei, version)

    def block(self, imei, bl=0):
        return self._request('block', imei, bl)

    def unblock(self, imei, bl=0):
        return self._request('block', imei, bl)

if __name__ == '__main__':
    usage = '''OTAP Control

    Usage:
      otc ping
      otc show [<imei>]
      otc jars
      otc add <imei> <custid> <tid>
      otc deliver <imei> <version>
      otc block [--all] [<imei>]
      otc unblock [--all] [<imei>]
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
        print "BLOCK IMEI             CUSTID    TID  Reported   Deliver"
        for item in data:
            print "%(block)5d %(imei)-16s %(custid)-10s %(tid)-3s %(reported)-10s %(deliver)-10s" % item

    if args['jars']:
        jarlist = rpc.jars()
        print "\n".join(jarlist)

    if args['add']:
        print rpc.add(args['<imei>'], args['<custid>'], args['<tid>'])

    if args['deliver']:
        print rpc.deliver(args['<imei>'], args['<version>'])

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



