---
type: page
---
# The map

What a visitor can do on the map, in the order they usually do it.

## Find cameras

The map opens on the whole country with a counted bubble on every covered state. Zoom to a
city or a region (zoom 6 or closer) and the cameras there load on their own, with no
clicks: up to four states per move, nearest the middle of the screen first, so panning
from Washington into Oregon brings Oregon in. A state's bubble steps aside once its
cameras load, so a zoomed-out map shows clusters where states are loaded and one bubble
everywhere else. Tap a bubble to load that state and fly in.

The Sources section of the panel lists every state. Untick one to switch it off; the map
then leaves it off until you tick it again, tap its bubble, or pick it in search. "All
states" is a three-way box (none, some, all), and "Clear" switches every state off without
moving the map. New York City is folded into New York's row.

The Chicago ticket map is a different kind of data, so it never loads on its own. Turn it
on in its own section of the panel.

## Find yourself

The locate button under the zoom buttons shows your position as a blue dot with a ring for
how sure the browser is, and flies there at about city zoom, so the cameras around you load.
The browser asks for permission only when you tap it, never on load. If location is off for
the site, one line says so and the map stays where it was. Opening the bare address, with no
link, returns to wherever you last looked; the very first visit opens on the whole country.

## Read a pin

Pins cluster as you zoom out and split as you zoom in. A tap on + or -, or a double-click,
plays a short morph so a cluster visibly becomes its members; a wheel or pinch swaps levels
at once so the gesture stays smooth. A grey pin is a camera the health sweep found
offline, frozen, or serving a placeholder; the popup says which and when that was last
checked. Hovering shows a ring and the camera's name.

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
in the browser. Results list inside the panel, two lines a row: the name, then where it is.
Pick a result and the map flies to it and opens it. Only the states loaded right now are
searched; when nothing loaded matches, a search offers to turn on the state it finds. Run on
your own machine with the [route preview](2.3-route-preview.md) proxy, it also finds places
and addresses.

## Tap the map

Tap a landmark, a shop or a restaurant drawn on the map and its card opens: its name and
kind, and how many cameras sit within a mile. Tap empty map to close it. Camera pins and
state bubbles answer a tap first. On your own machine the card also fills in the address,
phone and website from Overture Maps Places (see the [route preview](2.3-route-preview.md)).

## Basemap

Switch between the street style and satellite imagery. Satellite shows the actual road
and intersection each camera watches; pin outlines thicken on it so they stay visible.

## Share a view

The URL always reflects what you are looking at: position, zoom, basemap, and the Chicago
ticket map with its filters. States are not in it, because they follow the view: opening
the link at the same position loads the same states. "Copy link" copies it. Older links
that name states (`#l=st-WA`) still open on the same view.

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
