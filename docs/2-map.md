---
type: page
---
# The map

What a visitor can do on the map, in the order they usually do it.

## Pick a state

The map opens on the whole country with a counted pin on every covered state. Click a pin
or tick the state in the sidebar to load it and fly in. States stack: tick several and all
of their cameras share one map. "All states" is a three-way box (none, some, all), "Show
all states" returns to the overview, and "Clear" turns everything off without moving the
map. New York City is folded into New York's row; the Chicago ticket layer sits under
Illinois.

## Read a pin

Pins cluster as you zoom out and split as you zoom in, with a short morph between levels
so a cluster visibly becomes its members. A grey pin is a camera the health sweep found
offline, frozen, or serving a placeholder; the popup says which and when that was last
checked. Hovering shows a ring and the camera's name; the selected pin stays ringed as you
pan, with a "Back to selection" button to return to it.

## Open a camera

Click a pin. The popup shows the snapshot at once, then, where the state supports it, the
live stream fades in over it with a red LIVE badge. If the stream stops moving the badge
turns grey and reads NOT LIVE while the snapshot stays; if it never starts, the popup falls
back to the snapshot after 12 seconds. A camera with several views has a tab per view, and
a compass chip says which direction of travel the view covers where the agency publishes
that. Click the picture or the enlarge button for a full-screen view; the left and right
arrow keys cycle to the next camera in spatial order, and F toggles fit and fill.

## Search

The search box matches every loaded camera by name, road, and intersection, instantly and
in the browser. Pick a result and the map flies to it and opens it. Only the layers you
have switched on are searched; with none on, a search offers to turn on the state it
finds.

## Basemap

Switch between the street style and satellite imagery. Satellite shows the actual road
and intersection each camera watches; pin outlines thicken on it so they stay visible.

## Share a view

The URL always reflects what you are looking at: layers, position, zoom, basemap, Chicago
filters, and the selected camera. "Copy link" copies it, and opening it restores that exact
view, popup included.

## On a phone

The sidebar becomes a bottom sheet with two heights, swipe or tap to change, and the top
panel collapses out of the map's way. Every pin has an invisible 44 px touch target.

## Keyboard

| Key | What |
|---|---|
| Left, Right | Previous or next camera, spatial order |
| Enter in the jump box | Go to camera number N in that order |
| Esc | Close the enlarged view or the search results |
| F | Fit or fill in the enlarged view |
