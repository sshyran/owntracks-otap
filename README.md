## OTAP

This is the OTAP server for OwnTracks Greenwich.

### Installation notes

1. Clone the repository
2. Run `./generate-key.py` to create a secret key.
3. Create `otap.conf` from `.sample` and adapt. In particular, copy the secret key you generated into this, and make it available to `otc` in your environment.

### OTC

_otc_ is the OTAP Control program which speaks JSON RPC to the OTAP daemon. The
following commands are supported:

* `ping`. If "PONG" is returned, all is good. If you see "pong", then the secret key isn't correctly configured between `otap.py` and `otc.py`.

* `show` [_imei_]

* `deliver` _imei_ _version_ where _version_ may be any installed JAR version number, the word "`*`" which means any most recent version, or "`latest`" which is the current latest version.

* `find`. Search for a TID in the database.
* `jars`. Show installed JAR versions
* `add`. Add a device with _custid_ and _tid_ to the database.
* `deliver`. Set up _imei_ to be provided with Jar _version_ at next OTAP
* `block`. Prohibit _imei_ to do OTAP.
* `unblock`. Enable _imei_ to do OTAP.
* `upload`. Upload a Jar file to the OTAP server. The specified filename must be a JAR file.
* `purge`. Remove a jar from the server. If a particular version is queued for `deliver`y to a device, the jar will not be removed
* `versioncheck`. Simulate a versionCheck
* `otap`: Simulate an OTAP request (the `.jad` is returned)
* `showconfig`. Show the OTAP configuration required for OwnTracks Greenwich

### uWSGI

##### /etc/uwsgi/apps-enabled/otap.ini
```ini
[uwsgi]
base = /home/owntracks/otap
socket = /var/run/uwsgi/app/%n.sock
chdir = %(base)
file  = otap.py
env = OTAPCONFIG=/home/owntracks/otap/otap.conf
plugins = python
uid = www-data
gid = www-data
logto = /var/log/uwsgi/app/%n.log

py-autoreload = 1
```

##### /etc/nginx/sites-enabled/otap.example.com

```
server {
        listen 80;
        server_name otap.example.com;

        access_log /var/log/nginx/otap.log;

        root /var/www/otap.example.com;
        index index.php index.html index.htm;

        location / {
                include uwsgi_params;
                uwsgi_pass unix:///var/run/uwsgi/app/otap.sock;
        }
        location /rpc {
                include uwsgi_params;
                uwsgi_pass unix:///var/run/uwsgi/app/otap.sock;
        }
}
```
