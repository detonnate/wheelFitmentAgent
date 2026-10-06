"""MCP server exposing wheel fitment tools to GitHub Copilot (VS Code agent mode)."""
import time
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP, Image
from pydantic import BaseModel, Field

from . import config
from .fitment import check_fitment
from .rendering import render_car_with_wheels
from .wheelsize import WheelSizeClient

INSTRUCTIONS = """You are a wheel fitment advisor. Users want to know whether aftermarket wheels/tyres will fit their car.

Workflow:
1. Identify the exact vehicle: make, model, year, region (usdm, eudm, jdm, etc.) and trim/engine, using the lookup tools. Never guess slugs.
2. Ask for the proposed wheel specs if missing: rim diameter (in), width (in), offset/ET (mm), tyre size (e.g. 225/40R18), bolt pattern and centre bore if known. Ask for rear specs only if the setup is staggered.
3. Call check_wheel_fitment, then explain the verdict in plain language with the key numbers (poke/push in mm, diameter change). Mention hub rings, spacers or alternative sizes when relevant.
4. State that results are calculated estimates from OEM data; recommend verifying for lowered/cambered cars, big brakes or aftermarket suspension.
The Wheel-Size API key has a limited monthly call quota. Avoid redundant lookups and reuse data already retrieved."""

mcp = FastMCP("wheel-fitment", instructions=INSTRUCTIONS)
_client: WheelSizeClient | None = None
_IMAGE_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _ws() -> WheelSizeClient:
    global _client
    if _client is None:
        _client = WheelSizeClient()
    return _client


class Axle(BaseModel):
    rim_diameter: float = Field(description="Rim diameter in inches")
    rim_width: float = Field(description="Rim width in inches")
    rim_offset: float = Field(description="Offset (ET) in mm")
    tire: str = Field(description="Tyre size, e.g. 225/40R18")
    bolt_pattern: str | None = Field(None, description="e.g. 5x112")
    centre_bore: float | None = Field(None, description="Wheel centre bore in mm")


def _compact_axle(a: dict | None) -> dict | None:
    if not a:
        return None
    keys = ("rim", "tire", "rim_diameter", "rim_width", "rim_offset", "load_index", "speed_index")
    return {k: a.get(k) for k in keys if a.get(k) not in (None, "")}


async def _oem(make: str, model: str, modification: str, region: str | None) -> dict:
    item = await _ws().oem_specs(make, model, modification, region)
    if not item:
        raise ValueError("No OEM data found for that vehicle/modification.")
    return item


@mcp.tool()
async def search_makes(query: str | None = None, region: str | None = None) -> list[dict]:
    """List car makes (slug + name), optionally filtered by a name substring and region slug (usdm, eudm, jdm...)."""
    q = (query or "").lower()
    return [{"slug": m["slug"], "name": m["name"]} for m in await _ws().makes(region)
            if q in m["name"].lower() or q in m["slug"]][:50]


@mcp.tool()
async def search_models(make: str, year: int | None = None, query: str | None = None) -> list[dict]:
    """List models for a make slug, optionally filtered by year and a name substring."""
    q = (query or "").lower()
    return [{"slug": m["slug"], "name": m["name"], "years": m.get("year_ranges")}
            for m in await _ws().models(make, year)
            if q in m["name"].lower() or q in m["slug"]][:50]


@mcp.tool()
async def list_modifications(make: str, model: str, year: int, region: str | None = None) -> list[dict]:
    """List trims/engines (modification slugs) for a make, model and year."""
    mods = await _ws().modifications(make, model, year, region)
    return [{"slug": m["slug"], "trim": m.get("trim"), "engine": m.get("engine", {}).get("capacity"),
             "fuel": m.get("engine", {}).get("fuel"), "regions": m.get("regions")} for m in mods][:60]


@mcp.tool()
async def get_oem_specs(make: str, model: str, modification: str, region: str | None = None) -> dict:
    """Get OEM wheel/tyre sizes, bolt pattern, centre bore and thread for a vehicle modification."""
    item = await _oem(make, model, modification, region)
    return {
        "vehicle": f"{item['make']['name']} {item['model']['name']} {item.get('trim') or ''} "
                   f"({item['start_year']}-{item['end_year']})",
        "technical": item.get("technical"),
        "wheels": [{"is_stock": w["is_stock"], "front": _compact_axle(w["front"]),
                    "rear": _compact_axle(w["rear"])} for w in item.get("wheels", [])],
    }


@mcp.tool()
async def check_wheel_fitment(
    make: str,
    model: str,
    modification: str,
    front: Axle,
    rear: Annotated[Axle | None, Field(description="Only for staggered setups")] = None,
    region: str | None = None,
) -> dict:
    """Check whether proposed wheels/tyres fit a vehicle. Returns a verdict plus per-axle deltas and issues."""
    item = await _oem(make, model, modification, region)
    return check_fitment(item, front.model_dump(), rear.model_dump() if rear else None)


@mcp.tool()
def wheelsize_api_usage() -> dict:
    """Show how many Wheel-Size API calls have been used this month and the monthly limit."""
    return _ws().usage()


def _read_image(path: str | None) -> tuple[bytes, str] | None:
    if not path:
        return None
    p = Path(path).expanduser()
    mime = _IMAGE_SUFFIXES.get(p.suffix.lower())
    if mime is None:
        raise ValueError("Images must be .jpg, .jpeg, .png or .webp files.")
    if not p.is_file() or p.stat().st_size > config.MAX_UPLOAD_BYTES:
        raise ValueError(f"{p.name} not found or larger than 10 MB.")
    return p.read_bytes(), mime


if config.GEMINI_API_KEY:

    @mcp.tool()
    async def render_car_with_wheels_tool(
        car_image_path: str | None = None,
        wheel_image_path: str | None = None,
        car_description: str = "",
        wheel_description: str = "",
        stance_notes: str = "",
    ) -> list:
        """Render a car with new wheels. Give a car photo path (edits the photo) or a car description (generates one),
        plus a wheel photo path or wheel description. Saves a PNG and returns it."""
        png = await render_car_with_wheels(
            car_image=_read_image(car_image_path),
            wheel_image=_read_image(wheel_image_path),
            car_description=car_description,
            wheel_description=wheel_description,
            stance_notes=stance_notes,
        )
        out_dir = config.DATA_DIR / "renders"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"render-{int(time.time())}.png"
        out.write_bytes(png)
        return [Image(data=png, format="png"), f"Saved to {out}"]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
