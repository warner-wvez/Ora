#!/usr/bin/env python3
"""
Build California cameras. Caltrans publishes every CCTV in one JS file
(cwwp2.dot.ca.gov/vm/js/cctv09.js) -- it literally says "developers looking
for data please go here". Each entry is byte-0xFF-delimited:
  pageUrl <0xFF> lng <0xFF> lat <0xFF> description <0xFF> status(1=active)
The snapshot image URL is derivable from the page URL:
  /vm/loc/{district}/{name}.htm  ->  /data/{district}/cctv/image/{name}/{name}.jpg
(images are CORS-open). Only active cameras (status=1) are kept.

Usage: python3 build-states-ca.py
"""
import urllib.request, re, json, os

def img_from_page(page):
    m=re.match(r'https://cwwp2\.dot\.ca\.gov/vm/loc/(d\d+)/(.+)\.htm', page)
    if not m: return None
    d,name=m.groups()
    return f'https://cwwp2.dot.ca.gov/data/{d}/cctv/image/{name}/{name}.jpg'

def main():
    req=urllib.request.Request('https://cwwp2.dot.ca.gov/vm/js/cctv09.js', headers={'User-Agent':'Mozilla/5.0'})
    js=urllib.request.urlopen(req, timeout=60).read().decode('latin-1')  # 0xFF delimiter must survive
    rows=re.findall(r"cctv\[\d+\]\s*=\s*'([^']*)'", js)
    feats=[]; skipped=0
    for r in rows:
        parts=r.split('\xff')
        if len(parts)<4: continue
        page,lng,lat,desc=parts[0],parts[1],parts[2],parts[3]
        if (parts[4] if len(parts)>4 else '1')!='1': skipped+=1; continue
        try: lngf,latf=float(lng),float(lat)
        except ValueError: continue
        iu=img_from_page(page)
        if not iu: continue
        feats.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lngf,latf]},
            'properties':{'name':re.sub(r'\s*\([A-Z]\d+\)\s*$','',desc).strip() or 'Camera','kind':'live',
                          'directions':[{'snapshot':iu,'video':None,'label':''}],'roadway':'','county':''}})
    os.makedirs('states', exist_ok=True)
    json.dump({'type':'FeatureCollection','features':feats}, open('states/CA.json','w'))
    idx=json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['CA']={'name':'California','file':'states/CA.json','count':len(feats),'center':[-119.6,37.3],'zoom':5.2,'video':False}
    json.dump(idx, open('states/index.json','w'), indent=1)
    print(f'California: {len(feats)} active cameras (skipped {skipped} inactive)')

if __name__=='__main__': main()
