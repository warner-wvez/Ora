---
type: page
---
# Research: vehicle detection

One question was tested on 2026-07-13: does off-the-shelf vehicle detection work on Ora's
cameras well enough to ship a count? The answer was no, and the reason was not the one
being tested for. The full report with every number and frame is
[research/vehicle-detection/README.md](../research/vehicle-detection/README.md);
[decision 0010](6-decisions/0010-vehicle-detection-not-shipped.md) records the outcome.

## What was tried

24 frames harvested live from real Ora cameras, 12 from HLS video and 12 from snapshot
JPEGs, across Texas, South Carolina, Maryland, Mississippi, Florida, New York, Hawaii,
Washington, Illinois, Alabama, Kentucky, Rhode Island, and New York City. Vehicles counted
by eye as ground truth. Three candidates run cold, at defaults, no fine-tuning: YOLOv8n,
YOLOv8m, and Roboflow Universe's `vehicles-q0x2v` on hosted inference.

## What it found

- The best cold model, YOLOv8m, lands at 46 percent bucket accuracy (50 on video frames,
  42 on snapshots) against an 80 percent bar to ship.
- The failure is not that DOT pixels look alien to a COCO-trained model. Weather,
  compression, and camera angle were survivable. The failure is **vehicle pixel size**.
- On cameras delivering 640 px or wider, stock YOLOv8m with one free inference change
  reaches 71 percent and recovers all of the ground truth on the two cleanest frames.
  Below 640 px it scores 11 percent and no setting rescues it: the information is not in
  the file.
- A probe of 207 cameras across 50 layers puts roughly half the fleet in the workable tier
  and half in the blind tier (a three-camera sample per state is noisy; do not plan
  against the exact split). Texas, the largest state, is about 90 percent blind: TxDOT
  publishes one 320x240 or 352x240 rendition per camera.
- The purpose-built vehicle model was the worst of the three by a wide margin: 38 of 359
  vehicles found where stock YOLOv8m found 186. Buying a domain model off the shelf is not
  a shortcut.

## What it changed in the map

The camera-curation work that followed added a delivered-resolution chip to the popup and
full-screen view (the one hard filter is 640 px), a route export for handing off a camera
list, uniform full-screen sizing so scenes compare, and arrow-key cycling in spatial order.
Those shipped; the detector did not.

## Files

`research/vehicle-detection/`: `harvest.py` (pulls frames from live cameras),
`ground_truth.py`, `detect.py` and `roboflow_detect.py`, `score.py`, `report_tables.py`,
`resolution_census.py` (the fleet probe), `manifest.json`, `scores.json`,
`resolution_census.json`, the annotated frames under `annotated/`, and the report. Model
weights and captured frames are gitignored; the scripts that make them are what is
committed. The Roboflow call reads `ROBOFLOW_API_KEY`.
