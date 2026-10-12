"""Run unchanged journey assertions plus a persistent WebKit cold-start test.
The dedicated CI runner temporarily maps only the public app host to loopback,
then restores its original hosts file in finally. GitHub and other hosts are
untouched. No browser inspector request-abort or HTTPS proxy is used.
"""
from pathlib import Path
import os,socket,tempfile,subprocess
from urllib.parse import urlparse
from playwright.sync_api import Page
_original_screenshot=Page.screenshot
def stable_screenshot(self,*args,**kwargs):
    self.wait_for_timeout(250)
    return _original_screenshot(self,*args,**kwargs)
Page.screenshot=stable_screenshot
class HostOutage:
    def __init__(self,url):
        self.host=urlparse(url).hostname
        assert self.host=='rawcdn.githack.com'
        self.original=Path('/etc/hosts').read_bytes();self.active=False
    def cut(self):
        data=self.original+b'\n127.0.0.1 '+self.host.encode()+b'\n::1 '+self.host.encode()+b'\n'
        subprocess.run(['sudo','tee','/etc/hosts'],input=data,stdout=subprocess.DEVNULL,check=True)
        self.active=True
        assert socket.gethostbyname(self.host)=='127.0.0.1'
    def close(self):
        if self.active:
            subprocess.run(['sudo','tee','/etc/hosts'],input=self.original,stdout=subprocess.DEVNULL,check=True)
            self.active=False
path=Path(__file__).with_name('qa.py');s=path.read_text()
a="b=bt.launch();ctx=b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)"
b="""profile=tempfile.mkdtemp(prefix='macau-webkit-') if PUBLIC and name=='webkit' else None
    outage=HostOutage(url) if profile else None
    if profile:
        ctx=bt.launch_persistent_context(profile,viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
        b=ctx
    else:
        b=bt.launch();ctx=b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)"""
assert a in s;s=s.replace(a,b)
a="checks['title']='2.0' in page.title()"
b="page.wait_for_function(\"document.querySelectorAll('#markers .marker').length>=2\",timeout=20000)\n        "+a
assert a in s;s=s.replace(a,b)
a="ctx.route('**/*',lambda route:route.abort());offline_method='origin requests blocked; service-worker cache response asserted'"
b="""ctx.close();outage.cut()
            import requests
            probe=requests.Session();probe.trust_env=False
            try:
                probe.get(url,timeout=4)
                raise AssertionError('App host remained reachable during cold-start test')
            except requests.RequestException:pass
            ctx=bt.launch_persistent_context(profile,viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
            b=ctx;page=ctx.new_page()
            offline_method='browser process restarted, app DNS mapped to unreachable loopback, service-worker response asserted'"""
assert a in s;s=s.replace(a,b)
a='b.close()\n        if server:'
b='b.close()\n        if outage:outage.close()\n        if server:'
assert a in s;s=s.replace(a,b)
# Preserve the precise failure context rather than an empty AssertionError.
s=s.replace("'error':str(e),'features':checks", "'error':str(e),'traceback':traceback.format_exc(),'offline_message':page.locator('#offlineMessage').inner_text() if page.locator('#offlineMessage').count() else '', 'features':checks")
exec(compile(s,str(path),'exec'),{'__name__':'__main__','__file__':str(path),'HostOutage':HostOutage,'tempfile':tempfile})
