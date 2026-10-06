from wheel_fitment.fitment import check_fitment, parse_tire, tire_od_mm

OEM = {
    "technical": {"bolt_pattern": "5x112", "centre_bore": "57.1"},
    "wheels": [{
        "is_stock": True,
        "front": {"rim": "7.5Jx17 ET51", "tire": "225/45R17", "rim_diameter": 17, "rim_width": 7.5,
                  "rim_offset": 51, "tire_width_mm": 225, "tire_diameter_mm": 632},
        "rear": {},
    }],
}


def test_parse_tire():
    assert parse_tire("225/40 ZR18") == (225, 40, 18.0)


def test_od():
    assert round(tire_od_mm(225, 45, 17)) == 634


def test_plus_one_fits():
    r = check_fitment(OEM, {"rim_diameter": 18, "rim_width": 7.5, "rim_offset": 50, "tire": "225/40R18",
                            "bolt_pattern": "5x112", "centre_bore": 66.5})
    assert r["verdict"] == "SHOULD FIT"


def test_poking_offset_fails():
    r = check_fitment(OEM, {"rim_diameter": 18, "rim_width": 8, "rim_offset": 45, "tire": "225/40R18",
                            "bolt_pattern": "5x112", "centre_bore": 66.5})
    assert r["verdict"] == "WILL NOT FIT"


def test_wrong_bolt_pattern():
    r = check_fitment(OEM, {"rim_diameter": 17, "rim_width": 7.5, "rim_offset": 51, "tire": "225/45R17",
                            "bolt_pattern": "5x114.3"})
    assert r["verdict"] == "WILL NOT FIT"


def test_small_centre_bore_fails():
    r = check_fitment(OEM, {"rim_diameter": 17, "rim_width": 7.5, "rim_offset": 51, "tire": "225/45R17",
                            "bolt_pattern": "5x112", "centre_bore": 54.1})
    assert r["verdict"] == "WILL NOT FIT"


def test_extreme_offset_fails():
    r = check_fitment(OEM, {"rim_diameter": 17, "rim_width": 9.5, "rim_offset": 20, "tire": "225/45R17",
                            "bolt_pattern": "5x112", "centre_bore": 66.5})
    assert r["verdict"] == "WILL NOT FIT"
