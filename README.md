empty

### versioncheck

```
curl -s -X POST -d 0.0.0 --user-agent "X1/000000000000001" http://localhost:8810/otap/JJOLIE/version
```


### OTC

_otc_ is the OTAP Control program which speaks JSON RPC to the OTAP daemon. The
following commands are supported:

* `show` [_imei_]

* `deliver` _imei_ _version_ where _version_ may be any installed JAR version number, the word "`*`" which means any most recent version, or "`latest`" which is the current latest version.
