import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import officers as of

def t(ts, lng=-87.65, lat=41.88, amt=6000, loc="1 W MADISON ST", desc="EXPIRED METER OR OVERSTAY", oid=5):
    return {"ticketDate": ts, "ticketAmount": amt, "ticketLocation": loc, "ticketDescription": desc,
            "ticketType": desc, "latitude": lat, "longitude": lng, "officerId": oid, "ticketId": "X" + ts}

def test_split_shifts_breaks_on_gaps_over_four_hours():
    runs = of.split_shifts([t("2026-11-12T08:00:00"), t("2026-11-12T11:59:00"), t("2026-11-12T16:00:00")])
    assert [len(r) for r in runs] == [2, 1]

def test_split_shifts_keeps_a_night_shift_whole_across_midnight():
    runs = of.split_shifts([t("2026-11-12T22:00:00"), t("2026-11-13T00:30:00"), t("2026-11-13T01:10:00")])
    assert len(runs) == 1 and runs[0][0]["ticketDate"].startswith("2026-11-12")

def test_area_center_is_the_spot_nearest_the_average():
    c = of.area_center([t("2026-11-12T08:00:00", -87.60, 41.80), t("2026-11-12T08:10:00", -87.70, 41.90), t("2026-11-12T08:20:00", -87.66, 41.86)])
    assert c == [-87.66, 41.86]

def test_area_center_none_without_map_points():
    assert of.area_center([t("2026-11-12T08:00:00", None, None)]) is None

def test_fake_ids_known_published_and_new_are_stable():
    f1 = of.FakeIds({"2213": 731}, b"k", {})
    assert f1.get("2213") == 731
    new = f1.get("9999")
    assert 100 <= new <= 999 and new != 731
    f2 = of.FakeIds({"2213": 731}, b"k", {f1.k("9999"): new})   # next night reads the published keyed hash
    assert f2.get("9999") == new

def test_fake_ids_step_past_a_clash():
    f = of.FakeIds({}, b"k", {})
    a = f.get("1"); f2 = of.FakeIds({"7": a}, b"k", {})
    assert f2.get("1") != a

def test_build_publishes_fake_numbers_only_and_counts_unreadable_in_totals():
    fake = of.FakeIds({"2213": 731}, b"k", {})
    out = of.build({"2213": [t("2026-11-12T08:00:00"), t("2026-11-12T09:00:00", amt=7500)],
                    "0": [t("2026-11-12T10:00:00", oid=0)]}, fake, "2026-11-01", "2026-11-12", [])
    assert set(out["daily"]) == {"731"}
    assert out["daily"]["731"][0][:5] == ["2026-11-12", 2, 135.0, "08:00", "09:00"]
    assert out["days"]["2026-11-12"][0] == [731, "08:00", -87.65, 41.88, "1 W MADISON ST", 0, 60.0]
    assert out["totals"]["2026-11-12"] == [3, 195.0, 1]
    assert out["by_officer"]["731"] == [["2026-11-12", -87.65, 41.88], ["2026-11-12", -87.65, 41.88]]
    assert "2213" not in repr(out)

def test_build_drops_shifts_outside_the_dates():
    fake = of.FakeIds({"2213": 731}, b"k", {})
    out = of.build({"2213": [t("2026-10-31T22:00:00"), t("2026-11-01T00:30:00"), t("2026-11-13T08:00:00")]}, fake, "2026-11-01", "2026-11-12", [])
    assert out["daily"] == {} and out["days"] == {}

def test_violation_indexes_are_append_only():
    fake = of.FakeIds({"2213": 731}, b"k", {})
    out = of.build({"2213": [t("2026-11-12T08:00:00", desc="NEW ONE")]}, fake, "2026-11-01", "2026-11-12", ["OLD"])
    assert out["violations"] == ["OLD", "NEW ONE"] and out["days"]["2026-11-12"][0][5] == 1

def test_merge_replaces_the_window_and_keeps_older_days():
    old = {"daily": {"731": [["2026-11-01", 5, 300.0, "08:00", "15:00", -87.6, 41.8], ["2026-11-10", 1, 60.0, "08:00", "08:00", -87.6, 41.8]]},
           "totals": {"2026-11-01": [5, 300.0, 0], "2026-11-10": [1, 60.0, 0]},
           "days": {"2026-11-01": [[731, "08:00", -87.6, 41.8, "A", 0, 60.0]], "2026-11-10": [[731, "08:00", -87.6, 41.8, "A", 0, 60.0]]},
           "by_officer": {"731": [["2026-11-01", -87.6, 41.8], ["2026-11-10", -87.6, 41.8]]}, "violations": ["A"]}
    new = {"daily": {"731": [["2026-11-10", 2, 120.0, "08:00", "09:00", -87.6, 41.8]]}, "totals": {"2026-11-10": [2, 120.0, 0]},
           "days": {"2026-11-10": [[731, "08:00", -87.6, 41.8, "A", 0, 60.0], [731, "09:00", -87.6, 41.8, "A", 0, 60.0]]},
           "by_officer": {"731": [["2026-11-10", -87.6, 41.8], ["2026-11-10", -87.6, 41.8]]}, "violations": ["A"]}
    m = of.merge(old, new, "2026-11-05")
    assert [s[0] for s in m["daily"]["731"]] == ["2026-11-01", "2026-11-10"] and m["daily"]["731"][1][1] == 2
    assert sorted(m["days"]) == ["2026-11-01", "2026-11-10"] and len(m["days"]["2026-11-10"]) == 2
    assert len(m["by_officer"]["731"]) == 3

def test_assign_characters_keeps_old_and_gives_new_officers_the_next_unused():
    chars = [{"character": "Mordecai", "s": 0}, {"character": "Rigby", "s": 1}, {"character": "Benson", "s": 2}]
    old = [{"id": 731, "c": "Mordecai", "s": 0, "k": "a"}]
    out = of.assign_characters(old, [731, 118], chars)
    assert out[0]["c"] == "Mordecai" and out[1] == {"id": 118, "c": "Rigby", "s": 1, "k": None}

def test_check_catches_real_numbers_extra_fields_and_bad_points():
    good = {"daily": {"731": [["2026-11-12", 1, 60.0, "08:00", "08:00", -87.6, 41.8]]}, "totals": {"2026-11-12": [1, 60.0, 0]},
            "days": {"2026-11-12": [[731, "08:00", -87.6, 41.8, "A", 0, 60.0]]}, "by_officer": {"731": [["2026-11-12", -87.6, 41.8]]}, "violations": ["A"]}
    assert of.check(good, {731}, "2026-11-01", "2026-11-12") == []
    bad = {**good, "days": {"2026-11-12": [[2213, "08:00", -80.0, 41.8, "A", 0, 60.0, "9206718473"]]}}
    probs = of.check(bad, {731}, "2026-11-01", "2026-11-12")
    assert any("not a fake" in p for p in probs) and any("fields" in p for p in probs) and any("outside Chicago" in p for p in probs)

def test_check_ties_day_files_to_daily():
    out = {"daily": {"731": [["2026-11-12", 2, 120.0, "08:00", "09:00", -87.6, 41.8]]}, "totals": {"2026-11-12": [2, 120.0, 0]},
           "days": {"2026-11-12": [[731, "08:00", -87.6, 41.8, "A", 0, 60.0]]}, "by_officer": {"731": [["2026-11-12", -87.6, 41.8]]}, "violations": ["A"]}
    assert any("tie out" in p for p in of.check(out, {731}, "2026-11-01", "2026-11-12"))


import importlib.util, json, tempfile

def load_cmd():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build-chicago-officers.py")
    spec = importlib.util.spec_from_file_location("bco", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_write_then_read_round_trips_and_carries_no_real_numbers():
    bco = load_cmd()
    fake = of.FakeIds({"2213": 731}, b"k", {})
    out = of.build({"2213": [t("2026-11-12T08:00:00")]}, fake, "2026-11-01", "2026-11-12", [])
    officers = [{"id": 731, "c": "Mordecai", "s": 0, "k": None}]
    with tempfile.TemporaryDirectory() as d:
        bco.write_all(d, out, officers, {"first": "2026-11-01", "last": "2026-11-12"})
        back, offs, meta = bco.read_existing(d)
        assert back["days"] == out["days"] and offs == officers and meta["last"] == "2026-11-12"
        blob = "".join(open(os.path.join(r, f)).read() for r, _, fs in os.walk(d) for f in fs)
        assert "2213" not in blob
