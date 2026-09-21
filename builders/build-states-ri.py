#!/usr/bin/env python3
"""
Build Rhode Island cameras from RIDOT's regional camera pages (dot.ri.gov/travel).

Rhode Island publishes no camera API, no coordinates, and no 511 site: the only
public surface is six PHP pages (cameras_{metro,westbay,scounty,ncounty,eastbay,
bstonenorth}.php) that inline ~150 cameras as thumbnails + a Video.js popup, with
some cameras repeated across pages. Two findings decided this build:

  * The video is real (Wowza Cloud HLS on cdn3.wowza.com) but the CDN answers
    403 to any request that does not carry `Referer: dot.ri.gov`. A browser
    cannot spoof Referer from a static page (forbidden header), and Ora ships
    <meta name="referrer" content="no-referrer"> besides. CORS is open -- which
    is exactly why the CORS probe alone can never be the whole test. Video is
    therefore unusable here, and video URLs are deliberately not stored.
  * The page "thumbnails" (dot.ri.gov/img/travel/camimages/<name>.jpg) are NOT
    static preview stills: Last-Modified tracks within seconds of now on every
    sample. They are the live snapshots, https, referrer-tolerant. So Rhode
    Island ships as an honest snapshot state.

Coordinates: RIDOT encodes location only in the thumbnail filename ("95_17.0_M_CAM
- Weaver Hill Rd") and in prose. The GAZETTEER below was derived offline
(2026-07-12), one entry per camera, and each entry's comment says how:
  mm:*      RI renumbered its freeway exits to milepost-based numbers (2021), so
            OSM motorway_junction refs are mile anchors; a camera's filename
            milemarker interpolates between the two bracketing exits, snapped to
            the route polyline. State-line anchors come from intersecting the
            route with the RI admin boundary. Verified monotonic per route.
  x:A~B     closest approach of two OSM way sets (route refs or street names).
  hand:*    hand-anchored from OSM bridge geometry / Nominatim, snapped to the
            carrying route.
Every entry was validated inside the RI boundary polygon, and each named/hand
entry was reverse-geocoded to confirm the street it claims to sit on.

If RIDOT adds a camera this script does not know, it prints a loud warning and
skips it: a pin with a guessed location is worse than a missing pin.
"""
import json, os, re, urllib.parse, urllib.request

PAGES = ['metro', 'westbay', 'scounty', 'ncounty', 'eastbay', 'bstonenorth']
BASE = 'https://www.dot.ri.gov/travel/cameras_{}.php'
IMGBASE = 'https://www.dot.ri.gov/img/travel/camimages/'
HDRS = {'User-Agent': 'Mozilla/5.0'}
BBOX = (-71.95, 41.1, -71.1, 42.05)

LI = re.compile(r'<li><a id="(cam\d+)"[^>]*>\s*<img src="([^"]+)"[^>]*alt="([^"]*)"\s*>\s*</a>([^<]*)', re.S)
VID = re.compile(r'getElementById\("(cam\d+)"\).*?openVideoPopup2?\(\'([^\']+)\'\)', re.S)
MM_FACING = re.compile(r'_\d+\.?\d*_([NSEW])_CAM')
FACING = {'N': 'Northbound', 'S': 'Southbound', 'E': 'Eastbound', 'W': 'Westbound'}

GAZETTEER = {
 '1-01 Rt 1 S @ Fourth Ave East Greenwich': (41.653443, -71.455307),  # hand:US 1 at 4th Ave, East Greenwich (Nominatim+snap)
 '1-02 Rt 1 @ Rt 402 Frenchtown Rd': (41.632912, -71.467733),  # x:US 1~RI 402
 '1-03 Rt 1 N @ Rt 403 Devils Foot Road': (41.60474, -71.454843),  # x:US 1~RI 403
 '1-04 Rt 1 N @ Rt 138 North Kingstown': (41.521858, -71.462966),  # x:US 1~RI 138
 '1-06 Rt 1 N @ Saugatucket Rd': (41.466431, -71.463516),  # x:US 1~Saugatucket Road
 '1-07 Rt 1 S @ Government Center': (41.44376, -71.478203),  # hand:US1 S. County Gov Ctr, snap to US 1
 '1-08 Rt 1 S @ Wakefield': (41.427171, -71.509439),  # hand:US1 at Wakefield, snap to US 1
 '1-09 Rt 1 S @ Camp Fuller Rd': (41.414278, -71.529091),  # x:US 1~Camp Fuller Road
 '1-10 Rt 1 N @ Rt 78 Westerly': (41.357299, -71.807524),  # x:US 1~RI 78
 '10_00.4_N_CAM Exit 1A - Elmwood Ave': (41.776286, -71.418648),  # mm:extrap-snap
 '10_01.4_S_CAM Exit 2A - Reservoir Ave': (41.785479, -71.43265),  # mm:interp-snap
 '10_02.2_N_CAM 2B - Kenwood St': (41.796877, -71.441233),  # mm:interp-snap
 '10_03.0_S_CAM 3A - Union Ave': (41.808858, -71.44056),  # mm:exact-snap
 '138_25.6_W_CAM Rt 138 @ Rt 1A': (41.527813, -71.427876),  # x:RI 138~RI 1A
 '138_26.0_W_CAM Rt 138 @ Jamestown Br (NK)': (41.5303, -71.416),  # hand:Verrazzano Br west end (OSM)
 '138_27.8_E_CAM Rt 138 @ Jamestown Br (Island)': (41.5261, -71.3897),  # hand:Verrazzano Br east end (OSM)
 '138_32.4_E_CAM JT Connell Hwy at Rt 138 Overpass': (41.507332, -71.317484),  # x:JT Connell Highway~RI 138
 '138_32.6_E_CAM Rt 138 At Connector Rd - Waste Mgmt': (41.507251, -71.3164),  # mm-neighbor
 '138_32.9_W_CAM Admiral Kalbfus at Halsey St': (41.507388, -71.314815),  # x:Admiral Kalbfus Road~Halsey Boulevard
 '138_34.0_W_CAM Rt 114 @ Evergreen-Middletown': (41.510924, -71.302071),  # x:RI 114~Evergreen Avenue
 '138_34.4_W_CAM Rt 114 @ Rt 138': (41.516985, -71.300595),  # x:West Main Road~East Main Road
 '138_34.8_E_CAM Rt 138 @ Rt 214': (41.519209, -71.291988),  # x:East Main Road~Valley Road
 '138_35.3_E_CAM Rt 138 @ Rt 138A': (41.521821, -71.283169),  # x:East Main Road~Aquidneck Avenue
 '146_00.4_N_CAM Exit 1 - Admiral St': (41.840685, -71.417973),  # mm:extrap-snap
 '146_01.2_S_CAM Exit 1 - Branch Ave': (41.853279, -71.426565),  # mm:interp-snap
 '146_01.6_S_CAM Exit 1 - DMS': (41.860661, -71.42968),  # mm:interp-snap
 '146_02.8_N_CAM Exit 2 - Charles St': (41.878239, -71.434265),  # mm:interp-snap
 '146_04.0_N_CAM Exit 4 - State Police': (41.893266, -71.442113),  # mm:exact-snap
 '146_05.6_N_CAM Exit 6 - Sherman Ave': (41.912763, -71.452312),  # mm:interp-snap
 '146_07.0_N_CAM Exit 7 - Rt 116': (41.9355, -71.467254),  # mm:exact-snap
 '146_10.4_N_CAM Exit 10 - Rt 146A Split': (41.972066, -71.51685),  # mm:interp-snap
 '146_10.4_S_CAM Exit 10 - Rt 146A Split': (41.972066, -71.51685),  # mm:interp-snap
 '146_12.4_N_CAM Exit 13 - Woonsocket Hill Rd': (41.984337, -71.546113),  # mm:interp-snap
 '146_14.2_N_CAM Exit 14 - Great Rd': (42.003238, -71.562042),  # mm:extrap-snap
 '195-0 I-195 E @ Point St': (41.814414, -71.40324),  # hand:Iway EB over Point St, snap
 '195-1 I-195 W Split @ I-95': (41.814395, -71.409564),  # hand:I-95/I-195 split, snap to I 95
 '195-2 I-195 E @ India St': (41.818662, -71.393604),  # hand:Iway at India Point, snap
 '195-3 I-195 W @ Gano DMS and Camera': (41.819043, -71.389751),  # x:I 195~Gano Street
 '195-5 I-195 W @ Washington Bridge': (41.818985, -71.385965),  # hand:I-195 Seekonk R. crossing, snap
 '195-7 I-195 E @ Rt 114': (41.812318, -71.358341),  # x:I 195~RI 114
 '195-8 I-195 W @ Mass State Line': (41.806802, -71.339401),  # boundary-crossing:I 195
 '24_03.6_N_CAM - Sakonnet River Bridge (Tiverton)': (41.63817, -71.212187),  # mm:interp-snap
 '24_04.1_N_CAM - Sakonnet River Bridge (Portsmouth)': (41.641635, -71.202496),  # mm:interp-snap
 '24_04.4_S_CAM Exit 4 - Main Rd': (41.642527, -71.197138),  # mm:interp-snap
 '24_06.8_N_CAM Exit 1A - Eagleville Rd': (41.649661, -71.174596),  # mm:extrap-snap
 '295_01.2_M_CAM Exit 1B - Rt 2': (41.72377, -71.480242),  # mm:interp-snap
 '295_06.4_M_CAM Exit 6 - Rt 14': (41.794798, -71.50857),  # mm:interp-snap
 '295_08.2_N_CAM Exit 9 - Rt 6': (41.818594, -71.511938),  # mm:interp-snap
 '295_09.2_S_CAM Exit 9C - Rt 6': (41.83179, -71.516246),  # mm:interp-snap
 '295_10.8_M_CAM Exit 10': (41.857187, -71.513237),  # mm:interp-snap
 '295_12.0_S_CAM Exit 12A - Rt 44': (41.869231, -71.515221),  # mm:exact-snap
 '295_16.2_S_CAM Rt 116': (41.923677, -71.505345),  # mm:interp-snap
 '295_18.4_SM_CAM Exit 18A - Rt 146': (41.942582, -71.467671),  # mm:interp-snap
 '295_20.0_N_CAM Exit 20 - Rt 122': (41.946026, -71.434193),  # mm:exact-snap
 '37_00.3_W_CAM Exit 1A - I-295': (41.755801, -71.479811),  # mm:extrap-snap
 '37_00.7_W_CAM Exit 1C - between I-295 and Rt 2': (41.756034, -71.470625),  # mm:extrap-snap
 '37_01.4_E_CAM Exit 1C - Rt 2': (41.750922, -71.455705),  # mm:interp-snap
 '37_02.0_E_CAM Exit 1E - Pontiac Ave': (41.748061, -71.442391),  # mm:exact-snap
 '37_03.2_W_CAM Exit 3B - Post Rd': (41.739659, -71.430819),  # mm:extrap-snap
 '4_00.0_M_CAM - Rt 1': (41.53345, -71.515459),  # mm:extrap
 '4_00.6_S_CAM - West Allenton Rd': (41.542994, -71.512755),  # mm:extrap
 '4_02.0_S_CAM Exit 3A - Oak Hill Rd': (41.568302, -71.491486),  # mm:extrap-snap
 '4_04.6_S_CAM Exit 5 - Rt 102 DMS': (41.607258, -71.496454),  # mm:interp-snap
 '4_07.0_S_CAM Exit 7A - Frenchtown Rd': (41.630958, -71.487205),  # mm:exact-snap
 '4_08.2_N_CAM Exit 7 - Middle Rd': (41.649564, -71.488569),  # mm:interp-snap
 '4_09.4_M_CAM Exit 9 - Division St': (41.667274, -71.489773),  # mm:extrap-snap
 '6_16.6_W_CAM - Atwood Ave': (41.816947, -71.496497),  # x:US 6~Atwood Avenue
 '6_18.4_W_CAM - Glenbridge Ave': (41.822868, -71.460915),  # x:US 6~Glenbridge Avenue
 '6_18.9_W_CAM - DMS': (41.821469, -71.453693),  # mm-neighbor
 '6_19.2_W_CAM - Hartford Ave': (41.81948, -71.450531),  # mm-neighbor
 '6_19.6_W_CAM - Flyover': (41.816175, -71.447062),  # mm-neighbor
 '6_20.0_E_CAM - Westminster St': (41.816934, -71.438703),  # x:US 6~Westminster Street
 '6_20.4_E_CAM - Tobey St': (41.820631, -71.437129),  # x:US 6~Tobey Street
 '6_20.6_E_CAM - Atwells Ave': (41.824471, -71.430705),  # x:US 6~Atwells Avenue
 '6_21.1_E_CAM - Dean St': (41.822231, -71.4216),  # x:US 6~Dean Street
 '95_00.2_N_CAM - CT_RI State Line': (41.443638, -71.794534),  # mm:interp-snap
 '95_00.6_S_CAM - Exit 1': (41.446387, -71.790519),  # mm:interp-snap
 '95_04.4_S_CAM - Exit 4': (41.488623, -71.727158),  # mm:interp-snap
 '95_07.2_N_CAM - Exit 7': (41.514849, -71.690838),  # mm:interp-snap
 '95_09.2_N_CAM - Exit 9': (41.538376, -71.678624),  # mm:interp-snap
 '95_10.8_S_CAM - Tefft Hill': (41.558543, -71.668205),  # mm:interp-snap
 '95_14.0_S_CAM - Exit 14': (41.6031, -71.657148),  # mm:exact-snap
 '95_15.4_S_CAM - Exit 14B DMS': (41.621609, -71.642761),  # mm:interp-snap
 '95_17.0_M_CAM - Weaver Hill Rd': (41.640203, -71.624649),  # mm:interp-snap
 '95_18.2_N_CAM - Nooseneck Hill Rd': (41.650517, -71.601598),  # mm:interp-snap
 '95_20.0_N_CAM - Hopkins Hill Rd': (41.657392, -71.562642),  # mm:interp-snap
 '95_21.4_S_CAM - New London Tpke': (41.659423, -71.541561),  # mm:interp-snap
 '95_22.4_N_CAM - Shippeetown Rd': (41.661788, -71.525377),  # mm:interp-snap
 '95_24.0_N_CAM - Quaker Ln': (41.666492, -71.500739),  # mm:exact-snap
 '95_25.4_N_CAM - Rt 4 Cell Tower': (41.681114, -71.477509),  # mm:interp-snap
 '95_26.0_S_CAM - Cowesett Rd': (41.687302, -71.477549),  # mm:interp-snap
 '95_27.4_N_CAM - Toll Gate Rd': (41.704923, -71.473648),  # mm:interp-snap
 '95_28.8_S_CAM - Greenwich Ave': (41.727348, -71.459976),  # mm:interp-snap
 '95_30.2_N_CAM - Service Ave': (41.741292, -71.445796),  # mm:interp-snap
 '95_31.4_N_CAM - Jefferson Blvd': (41.755295, -71.436516),  # mm:interp-snap
 '95_32.4_N_CAM - Wellington Ave': (41.772074, -71.428156),  # mm:interp-snap
 '95_32.6_S_CAM - Laurens St': (41.775571, -71.426879),  # mm:interp-snap
 '95_33.6_S_CAM - Rt 10': (41.787027, -71.420831),  # mm:interp-snap
 '95_33.6_S_CAM - Rt 10': (41.787027, -71.420831),  # mm:interp-snap
 '95_34.0_S_CAM - Elmwood Ave': (41.790031, -71.417947),  # mm:exact-snap
 '95_34.4_S_CAM - Detriot Ave': (41.793094, -71.412075),  # mm:interp-snap
 '95_35.2_N_CAM - Thurbers Ave': (41.802682, -71.403826),  # mm:interp-snap
 '95_35.8_N_CAM - Public St': (41.81158, -71.406252),  # mm:interp-snap
 '95_36.2_S_CAM - Eddy St': (41.815392, -71.412496),  # mm:interp-snap
 '95_36.8_S_CAM - Broad St': (41.824015, -71.419687),  # mm:interp-snap
 '95_37.0_S_CAM - Broadway (Prov)': (41.826023, -71.419063),  # mm:exact-snap
 '95_37.4_S_CAM - 6_10 Interchange': (41.828504, -71.418156),  # mm:interp-snap
 '95_37.6_N_CAM - Kinsley Ave': (41.829695, -71.4178),  # mm:interp-snap
 '95_38.0_S_CAM - Orms St': (41.832409, -71.417079),  # mm:exact-snap
 '95_38.8_N_CAM - Branch Ave': (41.847753, -71.411018),  # mm:interp-snap
 '95_39.4_N_CAM - Exit 39B & 39C': (41.857028, -71.405343),  # mm:interp-snap
 '95_40.0_N_CAM - Smithfield Ave': (41.865711, -71.402893),  # mm:exact-snap
 '95_40.6_N_CAM - Lonsdale Ave': (41.872354, -71.394578),  # mm:interp-snap
 '95_41.0_S_CAM - Garden St': (41.873028, -71.388427),  # mm:exact-snap
 '95_41.8_N_CAM - Vernon St': (41.87936, -71.378343),  # mm:interp-snap
 '95_42.0_S_CAM - Central Ave': (41.882049, -71.3775),  # mm:exact-snap
 '95_42.4_N_CAM - Broadway (Pawt)': (41.885, -71.378518),  # mm:interp-snap
 '95_43.0_S_CAM - East St': (41.889565, -71.378873),  # mm:exact-snap
 'Admiral Kalbfus @ JT Connell Roundabout': (41.506875, -71.317777),  # x:Admiral Kalbfus Road~JT Connell Highway
 'Airport Connector': (41.727284, -71.438575),  # hand:Airport Connector, snap to named way
 "Farewell Street @ America's Cup Ave": (41.494926, -71.316765),  # x:Farewell Street~Americas Cup Avenue
 'Henderson Bridge EP 1': (41.8263, -71.367),  # hand:Henderson Pkwy east end
 'Henderson Bridge EP 2': (41.8261, -71.366),  # hand:Henderson Pkwy east end
 'Henderson Bridge Prov 1': (41.8293, -71.3795),  # hand:Henderson Pkwy west end
 'Henderson Bridge Prov 2': (41.8294, -71.3785),  # hand:Henderson Pkwy west end
 'Memorial Blvd @ Francis St': (41.825765, -71.41529),  # x:Memorial Boulevard~Francis Street
 'Memorial Blvd @ Steeple St': (41.826959, -71.410206),  # x:Memorial Boulevard~Steeple Street
 'Promenade St @ Dean St': (41.829282, -71.426635),  # x:Promenade Street~Dean Street
 "Rt 108 @ S. Pier Rd (Dillon's Corner)": (41.430821, -71.481068),  # x:RI 108~South Pier Road
 'Rt 114 @ Mink St DMS and Camera': (41.789521, -71.332554),  # x:RI 114~Mink Street
 'Rt 136 Market St @ Kickemuit Rd': (41.732971, -71.273811),  # x:Market Street~Kickemuit Road
 'Rt 2 @ I-295': (41.723693, -71.480634),  # x:RI 2~I 295
 'Rt 44 @ Rt 5': (41.870208, -71.530727),  # x:US 44~RI 5
 'Rt 5 @ I-95 Metro Center Blvd': (41.72193, -71.466503),  # x:RI 5~Metro Center Boulevard
 'Rt 5 @ Phenix Ave': (41.780956, -71.472336),  # x:RI 5~Phenix Avenue
 'Rt 5 @ Rt 113': (41.7168, -71.463517),  # x:RI 5~RI 113
}


def get(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def main():
    seen = {}   # img stem -> feature (dedupe across pages and across shared-image streams)
    unknown = []
    for page in PAGES:
        html = get(BASE.format(page))
        lis = {m.group(1): (m.group(2), m.group(3), m.group(4).strip()) for m in LI.finditer(html)}
        vids = {m.group(1): m.group(2) for m in VID.finditer(html)}
        for cid in set(lis) & set(vids):
            img, alt, trailing = lis[cid]
            stem = urllib.parse.unquote(img.split('/')[-1])
            stem = stem[:-4] if stem.lower().endswith('.jpg') else stem
            if stem in seen:
                continue
            if stem not in GAZETTEER:
                unknown.append(stem)
                continue
            lat, lon = GAZETTEER[stem]
            if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
                unknown.append(stem + ' (coords out of bbox)')
                continue
            name = alt.replace('Camera at ', '').strip() or trailing or 'Camera'
            d = {'snapshot': IMGBASE + urllib.parse.quote(stem) + '.jpg', 'video': None, 'label': ''}
            m = MM_FACING.search(stem)
            if m:
                d['facing'] = FACING[m.group(1)]
            seen[stem] = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                          'properties': {'name': name, 'kind': 'live', 'directions': [d],
                                         'roadway': '', 'county': ''}}
    feats = list(seen.values())
    if unknown:
        print(f'WARNING: {len(unknown)} cameras have no gazetteer entry and were SKIPPED;')
        print('re-derive their coordinates before shipping them:')
        for u in unknown:
            print('  -', u)

    os.makedirs('states', exist_ok=True)
    json.dump({'type': 'FeatureCollection', 'features': feats}, open('states/RI.json', 'w'))
    idx = json.load(open('states/index.json')) if os.path.exists('states/index.json') else {}
    idx['RI'] = {'name': 'Rhode Island', 'file': 'states/RI.json', 'count': len(feats),
                 'center': [-71.55, 41.65], 'zoom': 8.6, 'video': False}
    json.dump(idx, open('states/index.json', 'w'), indent=1)
    print(f'RI: {len(feats)} cameras, snapshot-only (video is Referer-locked to dot.ri.gov)')


if __name__ == '__main__':
    main()
