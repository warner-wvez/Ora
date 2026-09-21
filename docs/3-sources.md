---
type: page
---
# Sources

Every camera on the map comes from a state or city transportation agency's own public
feed, read by one builder script per feed. This page holds the rules every builder
follows, then the table of states with a link to the page that explains each feed.

## The rules

**Location first.** A pin means a camera exists here. A builder keeps every camera the
agency lists, feed or no feed, and drops a row only for validity: no coordinate, a
coordinate outside the state, a test feed, a camera that belongs to another state's layer,
or an airport webcam. A camera with no working feed becomes a location-only pin and the
popup says "No live image at this camera". [Decision 0001](6-decisions/0001-location-first.md).

**Video is flagged only when a stream really plays from a static page.** A builder samples
up to eight streams with a browser-like request and sets `video: true` if any plays. One
camera never speaks for a state: New York's first camera is dead and once cost 1,553
working feeds. A stream is refused, and its URL stored as `null`, when:

- the URL carries a `token=` parameter, because a credential with a lifetime cannot live
  in a static file (Kansas and Massachusetts, [decision 0002](6-decisions/0002-no-expiring-tokens.md));
- the chunklist names an `#EXT-X-KEY`, which is DRM the browser cannot decrypt however
  green the CORS header is (Alabama);
- the host demands a `Referer`, a header a static page cannot send (Rhode Island, New
  Jersey). [Decision 0003](6-decisions/0003-cors-alone-proves-nothing.md).

**URLs are stored as the agency serves them.** No rewriting to https, no proxy baked in.
The health sweep must fingerprint the real bytes, and the health file must key on the same
string the page uses. An http-only host gets an `imgproxy` flag in the index and the page
proxies at render time.

**Never filter with `states-outline.json` as the primary test.** It is too coarse for a
coastal or river-border state and silently deletes real ferry and bridge cameras.
[Decision 0011](6-decisions/0011-outline-is-not-a-filter.md).

**A rebuild is compared against the committed file before it ships.** A relaxed filter can
only add cameras. A drop means the agency's feed changed, and the page for that state says
what a drop has meant before.

**No guessed cadence.** A refresh rate is stated only where it was measured over two
observed refreshes. One age sample is not a rate.

## How to read a drop

| The count went | Likely cause | Check |
|---|---|---|
| Up a lot | A filter was relaxed, or the agency added cameras | Spot-check five new pins on satellite |
| Down a few percent | Feed drift: cameras retired or relisted | The agency's map, then ship |
| Down by half at a stable number | A filter is eating valid rows and impersonating a rate limit | The Mississippi trap on its page |
| To zero | The endpoint moved | The state's page names where the URL was found |

## The states

The table is written by `scripts/refresh_numbers.py` from `states/index.json`; edit that,
not this.

<!-- states:start -->
| State | Cameras | Live video | How it is read |
|---|---|---|---|
| Alabama | 629 | snapshot | [Alabama](3.3-alabama.md) |
| Alaska | 123 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Arizona | 644 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Arkansas | 525 | snapshot | [Arkansas](3.4-arkansas.md) |
| California | 3,197 | snapshot | [California](3.5-california.md) |
| Colorado | 1,026 | yes | [511 GraphQL](3.2-511-graphql.md) |
| Connecticut | 347 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Delaware | 358 | yes | [Delaware](3.6-delaware.md) |
| Florida | 4,904 | yes | [511 DataTables](3.1-511-datatables.md) |
| Georgia | 4,043 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Hawaii | 361 | yes | [Hawaii](3.7-hawaii.md) |
| Idaho | 457 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Illinois | 1,328 | snapshot | [Illinois](3.8-illinois.md) |
| Indiana | 740 | snapshot | [511 GraphQL](3.2-511-graphql.md) |
| Iowa | 844 | yes | [511 GraphQL](3.2-511-graphql.md) |
| Kansas | 613 | snapshot | [511 GraphQL](3.2-511-graphql.md) |
| Kentucky | 241 | snapshot | [Kentucky](3.9-kentucky.md) |
| Louisiana | 336 | yes | [511 DataTables](3.1-511-datatables.md) |
| Maine | 151 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Maryland | 553 | yes | [Maryland](3.11-maryland.md) |
| Massachusetts | 304 | snapshot | [511 GraphQL](3.2-511-graphql.md) |
| Michigan | 783 | snapshot | [Michigan](3.12-michigan.md) |
| Minnesota | 1,527 | yes | [511 GraphQL](3.2-511-graphql.md) |
| Mississippi | 411 | yes | [Mississippi](3.13-mississippi.md) |
| Missouri | 737 | yes | [Missouri](3.14-missouri.md) |
| Montana | 118 | snapshot | [Montana](3.15-montana.md) |
| Nebraska | 353 | snapshot | [511 GraphQL](3.2-511-graphql.md) |
| Nevada | 648 | yes | [511 DataTables](3.1-511-datatables.md) |
| New Hampshire | 181 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| New Mexico | 183 | snapshot | [New Mexico](3.16-new-mexico.md) |
| New York | 1,864 | yes | [511 DataTables](3.1-511-datatables.md) |
| New York City | 957 | snapshot | [New York City](3.17-new-york-city.md) |
| North Carolina | 1,114 | yes | [511 DataTables](3.1-511-datatables.md) |
| North Dakota | 186 | snapshot | [North Dakota](3.18-north-dakota.md) |
| Ohio | 1,121 | snapshot | [Ohio](3.19-ohio.md) |
| Oklahoma | 193 | yes | [Oklahoma](3.20-oklahoma.md) |
| Oregon | 1,127 | snapshot | [Oregon](3.21-oregon.md) |
| Pennsylvania | 1,522 | yes | [511 DataTables](3.1-511-datatables.md) |
| Rhode Island | 135 | snapshot | [Rhode Island](3.22-rhode-island.md) |
| South Carolina | 763 | yes | [South Carolina](3.23-south-carolina.md) |
| South Dakota | 170 | snapshot | [South Dakota](3.24-south-dakota.md) |
| Tennessee | 667 | yes | [Tennessee](3.25-tennessee.md) |
| Texas | 3,426 | yes | [Texas](3.26-texas.md) |
| Utah | 2,063 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Vermont | 89 | snapshot | [511 DataTables](3.1-511-datatables.md) |
| Virginia | 1,684 | snapshot | [Virginia](3.27-virginia.md) |
| Washington | 1,524 | snapshot | [Washington](3.28-washington.md) |
| West Virginia | 127 | yes | [West Virginia](3.29-west-virginia.md) |
| Wisconsin | 482 | yes | [511 DataTables](3.1-511-datatables.md) |
| Wyoming | 228 | snapshot | [Wyoming](3.30-wyoming.md) |
<!-- states:end -->

Not on the map: [New Jersey](3.31-new-jersey.md).
