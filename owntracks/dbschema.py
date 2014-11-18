#!/usr/bin/env python

from peewee import *
from owntracks import cf
import datetime
import os
import sys
import logging

log = logging.getLogger(__name__)

db = None

engines = {
    'postgresql' : PostgresqlDatabase(cf.dbname,
                        user=cf.dbuser,
                        port=cf.dbport,
                        threadlocals=True),
    'mysql'      : MySQLDatabase(cf.dbname,
                        user=cf.dbuser,
                        passwd=cf.dbpasswd,
                        host=cf.dbhost,
                        port=cf.dbport,
                        threadlocals=True),
    'sqlite'     : SqliteDatabase(cf.dbpath,
                        threadlocals=True),
}

if cf.dbengine in engines:
    db = engines[cf.dbengine]
else:
    raise ValueError("Configuration error: there is no database engine called `{0}'".format(cf.dbengine))


class OTAPModel(Model):

    class Meta:
        database = db

class Versioncheck(OTAPModel):
    imei            = CharField(null=False, max_length=15)
    version         = CharField(null=True, max_length=10)
    tstamp          = DateTimeField(default=datetime.datetime.now, index=True)

class Otap(OTAPModel):
    imei            = CharField(null=False, max_length=15, unique=True)
    custid          = CharField(null=False, max_length=20)
    tid             = CharField(null=True, max_length=2)
    reported        = CharField(null=True, max_length=10)
    deliver         = CharField(null=True, max_length=10)
    block           = IntegerField(null=False)
    settings        = TextField(null=True)

    class Meta:
        indexes = (
            # # Create a unique index on tst
            # (('tst', ), True),
        )

def createalltables():

    silent = True

    db.connect()

    Otap.create_table(fail_silently=silent)
    Versioncheck.create_table(fail_silently=silent)

def dbconn():
    # Attempt to connect if not already connected. For MySQL, take care of MySQL 2006
    try:
        db.connect()
    except Exception, e:
        log.info("Cannot connect to database: %s" % (str(e)))
