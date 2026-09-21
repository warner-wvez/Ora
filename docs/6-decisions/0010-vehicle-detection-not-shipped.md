---
type: adr
---
# 0010. Off-the-shelf vehicle detection is not shipped

Date: 2026-07-13. Status: Accepted.

## Context

A vehicle count per camera would turn the map into traffic data. The spike tested whether
a cold detector transfers to DOT cameras: 24 frames from 13 layers, counted by eye, against
YOLOv8n, YOLOv8m, and a purpose-built Roboflow vehicles model. The bar to ship was 80
percent bucket accuracy; under 50 meant harvest-and-label before any product feature.

## Decision

Nothing ships. YOLOv8m reached 46 percent overall. The binding constraint is camera
resolution, not the model: 71 percent on cameras delivering 640 px or wider, 11 percent
below, and roughly half the fleet is below (Texas about 90 percent). The specialist model
was five times worse than the generalist. Any future attempt starts by selecting cameras
at or above 640 px, not by retraining.

## Consequences

- The research lives under `research/vehicle-detection/` with its report as the README and
  the annotated frames as evidence.
- The map gained the tools the curation needed: a delivered-resolution chip, route export,
  uniform full-screen, arrow cycling.
- The `yolo-spike` branch holds a browser live-overlay demo, unmerged.
- Distilled from commits 1fa2ffe and b07359b; summary in [Research](../5-research.md).
