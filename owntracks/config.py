#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from ConfigParser import RawConfigParser, NoOptionError
import codecs
import ast
import sys
import logging

class Config(RawConfigParser):
    def __init__(self, configuration_file):
        self.configfile = configuration_file
        self.scriptname = os.path.splitext(os.path.basename(sys.argv[0]))[0]

        # [defaults]
        self.logfile    = os.getenv(self.scriptname.upper() + 'LOG', self.scriptname + '.log')
        self.loglevel   = 'INFO'
        self.logformat  = '%(asctime)-15s %(levelname)-5s [%(module)s] %(message)s'
        self.logconfig  = 'logging.conf'

        self.dbengine   = 'mysql'
        self.dbname     = 'otap'
        self.dbuser     = None
        self.dbpasswd   = None
        self.dbhost     = 'localhost'
        self.dbport     = 3306
        self.dbpath     = '/tmp/otap.db'

        self.jarurl     = 'http://localhost:8810/jars'
        self.jardir     = '/tmp/jars'
        self.otckey     = None

        RawConfigParser.__init__(self)
        try:
            f = codecs.open(configuration_file, 'r', encoding='utf-8')
            self.readfp(f)
            f.close()
        except:
            print "Cannot open configuration file ", configuration_file
            sys.exit(2)

        self.__dict__.update(self.config('defaults'))

        self.loglevelnumber = getattr(logging, self.loglevel.upper())


    def g(self, section, key, default=None):
        try:
            val = self.get(section, key)
            return ast.literal_eval(val)
        except NoOptionError:
            return default
        except ValueError:   # e.g. %(xxx)s in string
            return val
        except:
            raise
            return val

    def config(self, section):
        d = {}
        if self.has_section(section):
            for key in self.options(section):
                d[key] = self.g(section, key)

        return d

