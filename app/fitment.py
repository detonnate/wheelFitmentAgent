"""Deterministic wheel/tyre fitment checks against OEM data from Wheel-Size."""
import re

IN_TO_MM = 25.4
_TIRE_RE = re.compile(r"(\d{3})\s*/\s*(\d{2})\s*(?:[A-Z]*R|-)?\s*(\d{2}(?:\.5)?)", re.I)
_BOLT_RE = re.compile(r"(\d+)\s*[x×*]\s*(\d+(?:[.,]\d+)?)", re.I)

# Poke/push thresholds (mm) for tyre edge movement vs the OEM reference.
OUT_OK, OUT_WARN = 3, 12
IN_OK, IN_WARN = 3, 8


def parse_tire(size: str) -> tuple[int, int, float]:
    m = _TIRE_RE.search(size or "")
    if not m:
        raise ValueError(f"Unrecognised tyre size: {size!r} (expected e.g. 225/40R18)")
    return int(m[1]), int(m[2]), float(m[3])


def tire_od_mm(section_width: float, aspect: float, rim_in: float) -> float:
    return 2 * section_width * aspect / 100 + rim_in * IN_TO_MM


def measuring_rim_in(section_width: float, aspect: float) -> float:
    if aspect >= 70:
        k = 0.70
    elif aspect >= 60:
        k = 0.75
    elif aspect >= 50:
        k = 0.80
    elif aspect >= 45:
        k = 0.85
    else:
        k = 0.90
    return round(section_width / IN_TO_MM * k * 2) / 2


def parse_bolt_pattern(value) -> tuple[int, float] | None:
    m = _BOLT_RE.search(str(value or ""))
    return (int(m[1]), float(m[2].replace(",", "."))) if m else None


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _usable(axle: dict | None) -> bool:
    return bool(axle) and all(_num(axle.get(k)) is not None for k in ("rim_diameter", "rim_width", "rim_offset"))


def _oem_tire_dims(oem: dict) -> tuple[float, float]:
    width, od = _num(oem.get("tire_width_mm")), _num(oem.get("tire_diameter_mm"))
    if width and od:
        return width, od
    sw, ar, rd = parse_tire(oem.get("tire") or oem.get("tire_full") or "")
    return sw, tire_od_mm(sw, ar, rd)


def _edge_deltas(oem: dict, new: dict, new_tire_w: float, oem_tire_w: float) -> tuple[float, float]:
    """Outward (poke) and inward (push) movement of the tyre edges in mm; positive = closer to fender/suspension."""
    half_w = (new["rim_width"] - oem["rim_width"]) * IN_TO_MM / 2
    et_shift = oem["rim_offset"] - new["rim_offset"]
    tire_half = (new_tire_w - oem_tire_w) / 2
    return half_w + et_shift + tire_half, half_w - et_shift + tire_half


def _check_axle(name: str, oem_wheels: list[dict], proposed: dict, tech: dict) -> dict:
    issues: list[tuple[str, str]] = []
    candidates = []
    for w in oem_wheels:
        axle = w.get(name) if _usable(w.get(name)) else w.get("front")
        if _usable(axle):
            candidates.append((w.get("is_stock", False), axle))
    if not candidates:
        return {"axle": name, "issues": [{"severity": "warn", "message": "No usable OEM wheel data to compare against."}]}

    new = {
        "rim_diameter": float(proposed["rim_diameter"]),
        "rim_width": float(proposed["rim_width"]),
        "rim_offset": float(proposed["rim_offset"]),
    }
    sw, ar, tire_rd = parse_tire(proposed["tire"])
    new_od = tire_od_mm(sw, ar, tire_rd)

    scored = []
    for is_stock, oem in candidates:
        oem_w, oem_od = _oem_tire_dims(oem)
        out, inn = _edge_deltas(oem, new, sw, oem_w)
        scored.append((max(out, 0) + max(inn, 0), not is_stock, oem, out, inn, oem_od))
    _, _, oem, out, inn, oem_od = min(scored, key=lambda s: (s[0], s[1]))

    if abs(tire_rd - new["rim_diameter"]) > 0.01:
        issues.append(("fail", f"Tyre is for {tire_rd:g}\" rims but wheel is {new['rim_diameter']:g}\"."))

    # Bolt pattern and centre bore
    suffix = "" if name == "front" else "rear_axis_"
    bp_oem = parse_bolt_pattern(tech.get(f"{suffix}bolt_pattern") or tech.get("bolt_pattern"))
    bp_new = parse_bolt_pattern(proposed.get("bolt_pattern"))
    if bp_new and bp_oem:
        if bp_new[0] != bp_oem[0] or abs(bp_new[1] - bp_oem[1]) > 0.05:
            issues.append(("fail", f"Bolt pattern {proposed['bolt_pattern']} does not match the car's {bp_oem[0]}x{bp_oem[1]:g}."))
    elif not bp_new:
        issues.append(("info", f"Bolt pattern not provided; car needs {bp_oem[0]}x{bp_oem[1]:g}." if bp_oem else "Bolt pattern not provided."))

    hub = _num(tech.get(f"{suffix}centre_bore") or tech.get("centre_bore"))
    cb_new = _num(proposed.get("centre_bore"))
    if cb_new is not None and hub is not None:
        if cb_new < hub - 0.05:
            issues.append(("fail", f"Wheel centre bore {cb_new:g}mm is smaller than the hub ({hub:g}mm); it cannot seat."))
        elif cb_new > hub + 0.05:
            issues.append(("info", f"Centre bore {cb_new:g}mm > hub {hub:g}mm: hub-centric rings are required."))
    elif cb_new is None and hub is not None:
        issues.append(("info", f"Centre bore not provided; hub is {hub:g}mm (wheel must be >= this)."))

    # Overall diameter (speedo/ABS)
    od_pct = (new_od - oem_od) / oem_od * 100
    if abs(od_pct) > 5:
        issues.append(("fail", f"Overall tyre diameter differs from OEM by {od_pct:+.1f}% (speedo/ABS/clearance out of range)."))
    elif abs(od_pct) > 2:
        issues.append(("warn", f"Overall tyre diameter differs from OEM by {od_pct:+.1f}%; speedometer will read off."))

    # Tyre width on rim
    ideal = measuring_rim_in(sw, ar)
    diff = new["rim_width"] - ideal
    if abs(diff) > 2:
        issues.append(("fail", f"{new['rim_width']:g}\" rim is far outside the safe range for a {sw}/{ar} tyre (measuring rim {ideal:g}\")."))
    elif abs(diff) > 1:
        issues.append(("warn", f"{new['rim_width']:g}\" rim is outside the usual range for a {sw}/{ar} tyre (measuring rim {ideal:g}\")."))

    # Clearance
    if out > OUT_WARN:
        issues.append(("fail", f"Tyre/wheel sits ~{out:.0f}mm further out than OEM; likely to poke past the arch or rub."))
    elif out > OUT_OK:
        issues.append(("warn", f"Sits ~{out:.0f}mm further out than OEM; check arch clearance (may need rolled lip or different offset)."))
    if inn > IN_WARN:
        issues.append(("fail", f"Sits ~{inn:.0f}mm further in than OEM; likely to hit suspension/brakes."))
    elif inn > IN_OK:
        issues.append(("warn", f"Sits ~{inn:.0f}mm further in than OEM; check brake caliper and suspension clearance."))

    if new["rim_diameter"] != oem["rim_diameter"]:
        issues.append(("info", f"Rim diameter changes from {oem['rim_diameter']:g}\" to {new['rim_diameter']:g}\"; confirm brake caliper clears the larger/smaller barrel."))

    return {
        "axle": name,
        "oem_reference": {k: oem.get(k) for k in ("rim", "tire", "rim_diameter", "rim_width", "rim_offset")},
        "proposed": {**new, "tire": proposed["tire"], "tire_od_mm": round(new_od, 1)},
        "deltas": {
            "outward_mm": round(out, 1),
            "inward_mm": round(inn, 1),
            "overall_diameter_pct": round(od_pct, 2),
        },
        "issues": [{"severity": s, "message": m} for s, m in issues],
    }


def check_fitment(oem_item: dict, front: dict, rear: dict | None = None) -> dict:
    """oem_item is one /search/by_model/ record; front/rear are proposed specs."""
    wheels = oem_item.get("wheels") or []
    tech = oem_item.get("technical") or {}
    axles = [_check_axle("front", wheels, front, tech)]
    if rear:
        axles.append(_check_axle("rear", wheels, rear, tech))

    severities = {i["severity"] for a in axles for i in a["issues"]}
    verdict = "WILL NOT FIT" if "fail" in severities else "FITS WITH CAVEATS" if "warn" in severities else "SHOULD FIT"
    return {"verdict": verdict, "axles": axles}
