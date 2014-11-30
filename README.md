empty

### versioncheck

```
curl -s -X POST -d 0.0.0 --user-agent "X1/000000000000001" http://localhost:8810/otap/JJOLIE/version
```

Run ./generate-key.py
copy output into otap.conf
make variable available to OTC's environment


### OTC

_otc_ is the OTAP Control program which speaks JSON RPC to the OTAP daemon. The
following commands are supported:

* `show` [_imei_]

* `deliver` _imei_ _version_ where _version_ may be any installed JAR version number, the word "`*`" which means any most recent version, or "`latest`" which is the current latest version.

* ping
	if PONG then ok
	if pong then not ok


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
