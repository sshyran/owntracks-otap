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

version = '0.12'

class RPC(object):
    def __init__(self, otc_url, otc_secret):
        self.server = pyjsonrpc.HttpClient(
            url = "%s/rpc" % otc_url,
            username = None,
            password = None,
            )

        self.otc_hash = hashlib.sha256(otc_secret).hexdigest()

    def _request(self, cmd, *args):
        try:
            return self.server.call(cmd, self.otc_hash, *args)
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


if __name__ == '__main__':
    usage = '''OTAP Control

    Usage:
      otc ping
      otc show [<imei>]
      otc jars
      otc add <imei> <custid> <tid>
      otc deliver <imei> <version>
      otc block [--all] [<imei>]
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




