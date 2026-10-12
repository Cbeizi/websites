"""Run the same journey assertions, using a cuttable TCP proxy for WebKit HTTPS.
The proxy forwards only to the current public app host and never decrypts TLS.
"""
from pathlib import Path
import os,socket,socketserver,select,threading
from urllib.parse import urlparse
from playwright.sync_api import Page
_original_screenshot=Page.screenshot
def stable_screenshot(self,*args,**kwargs):
    self.wait_for_timeout(250)
    return _original_screenshot(self,*args,**kwargs)
Page.screenshot=stable_screenshot
class OutageProxy:
    def __init__(self):
        owner=self;self.off=False;self.connections=set();self.lock=threading.Lock()
        allowed=urlparse(os.environ['MACAU_PUBLIC_URL']).hostname
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                client=self.request;up=None
                try:
                    client.settimeout(15);raw=b''
                    while b'\r\n\r\n' not in raw:
                        chunk=client.recv(8192)
                        if not chunk or len(raw)>65536:return
                        raw+=chunk
                    line=raw.split(b'\r\n',1)[0].decode('ascii','ignore').split()
                    if len(line)<3 or line[0]!='CONNECT' or owner.off:return
                    host,port=line[1].rsplit(':',1)
                    if host!=allowed or port!='443':
                        client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');return
                    up=socket.create_connection((host,443),timeout=15)
                    with owner.lock:owner.connections.update([client,up])
                    client.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                    client.settimeout(3);up.settimeout(3)
                    while not owner.off:
                        ready,_,_=select.select([client,up],[],[],1)
                        for src in ready:
                            data=src.recv(65536)
                            if not data:return
                            (up if src is client else client).sendall(data)
                except (OSError,ValueError):pass
                finally:
                    with owner.lock:
                        owner.connections.discard(client)
                        if up:owner.connections.discard(up)
                    if up:
                        try:up.close()
                        except OSError:pass
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=True;daemon_threads=True
        self.server=Server(('127.0.0.1',0),Handler)
        self.address='http://127.0.0.1:'+str(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def cut(self):
        self.off=True
        with self.lock:sockets=list(self.connections)
        for sock in sockets:
            try:sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:sock.close()
            except OSError:pass
    def close(self):
        self.cut();self.server.shutdown();self.server.server_close()
path=Path(__file__).with_name('qa.py');s=path.read_text()
a="b=bt.launch();ctx=b.new_context"
b="tunnel=OutageProxy() if PUBLIC and name=='webkit' else None\n    b=bt.launch(proxy={'server':tunnel.address} if tunnel else None);ctx=b.new_context"
assert a in s;s=s.replace(a,b)
a="checks['title']='2.0' in page.title()"
b="page.wait_for_function(\"document.querySelectorAll('#markers .marker').length>=2\",timeout=20000)\n        "+a
assert a in s;s=s.replace(a,b)
a="ctx.route('**/*',lambda route:route.abort());offline_method='origin requests blocked; service-worker cache response asserted'"
b="tunnel.cut();offline_method='HTTPS TCP proxy severed; new navigation served by service worker'\n            import requests\n            try:\n                requests.get(url,proxies={'https':tunnel.address},timeout=5)\n                raise AssertionError('The outage proxy did not block a fresh network connection')\n            except requests.RequestException:pass"
assert a in s;s=s.replace(a,b)
a='b.close()\n        if server:'
b='b.close()\n        if tunnel:tunnel.close()\n        if server:'
assert a in s;s=s.replace(a,b)
exec(compile(s,str(path),'exec'),{'__name__':'__main__','__file__':str(path),'OutageProxy':OutageProxy})
