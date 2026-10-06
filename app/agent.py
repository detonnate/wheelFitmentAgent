import json
from typing import Any

from openai import AsyncOpenAI

from . import config
from .fitment import check_fitment
from .wheelsize import WheelSizeClient

MAX_STEPS = 10

SYSTEM_PROMPT = """You are a wheel fitment advisor. Users want to know whether aftermarket wheels/tyres will fit their car.

Workflow:
1. Identify the exact vehicle: make, model, year, region (usdm, eudm, jdm, etc.) and trim/engine. Use the lookup tools; never guess slugs.
2. Ask the user for the proposed wheel specs if missing: rim diameter (in), width (in), offset/ET (mm), tyre size (e.g. 225/40R18), bolt pattern and centre bore if known. Ask for rear specs only if the setup is staggered.
3. Call check_fitment, then explain the verdict in plain language with the key numbers (offset delta, poke/push in mm, diameter change). Mention hub rings, spacers, or alternative sizes when relevant.
4. State that results are calculated estimates from OEM data; recommend verifying for lowered/cambered cars, big brakes, or aftermarket suspension.
If a tool returns an error or no data, say so and ask the user for clarification. Be concise."""

_VEHICLE = {
    "make": {"type": "string", "description": "Make slug, e.g. 'volkswagen'"},
    "model": {"type": "string", "description": "Model slug, e.g. 'golf'"},
    "modification": {"type": "string", "description": "Modification slug from list_modifications"},
    "region": {"type": "string", "description": "Region slug, e.g. usdm, eudm, jdm"},
}
_AXLE = {
    "type": "object",
    "properties": {
        "rim_diameter": {"type": "number", "description": "inches"},
        "rim_width": {"type": "number", "description": "inches"},
        "rim_offset": {"type": "number", "description": "ET in mm"},
        "tire": {"type": "string", "description": "e.g. 225/40R18"},
        "bolt_pattern": {"type": "string", "description": "e.g. 5x112"},
        "centre_bore": {"type": "number", "description": "mm"},
    },
    "required": ["rim_diameter", "rim_width", "rim_offset", "tire"],
}


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOLS = [
    _tool("search_makes", "List car makes, optionally filtered by name substring.",
          {"query": {"type": "string"}, "region": _VEHICLE["region"]}, []),
    _tool("search_models", "List models for a make, optionally filtered by year and name substring.",
          {"make": _VEHICLE["make"], "year": {"type": "integer"}, "query": {"type": "string"}}, ["make"]),
    _tool("list_modifications", "List trims/engines for a make, model and year.",
          {**{k: _VEHICLE[k] for k in ("make", "model", "region")}, "year": {"type": "integer"}},
          ["make", "model", "year"]),
    _tool("get_oem_specs", "Get OEM wheel/tyre sizes, bolt pattern and centre bore for a modification.",
          _VEHICLE, ["make", "model", "modification"]),
    _tool("check_fitment", "Check whether proposed wheels/tyres fit a vehicle modification.",
          {**_VEHICLE, "front": _AXLE, "rear": {**_AXLE, "description": "Only for staggered setups"}},
          ["make", "model", "modification", "front"]),
]


def _compact_axle(a: dict | None) -> dict | None:
    if not a:
        return None
    keys = ("rim", "tire", "rim_diameter", "rim_width", "rim_offset", "load_index", "speed_index")
    return {k: a.get(k) for k in keys if a.get(k) not in (None, "")}


async def _dispatch(ws: WheelSizeClient, name: str, args: dict[str, Any]) -> Any:
    if name == "search_makes":
        q = (args.get("query") or "").lower()
        return [{"slug": m["slug"], "name": m["name"]} for m in await ws.makes(args.get("region"))
                if q in m["name"].lower() or q in m["slug"]][:50]
    if name == "search_models":
        q = (args.get("query") or "").lower()
        return [{"slug": m["slug"], "name": m["name"], "years": m.get("year_ranges")}
                for m in await ws.models(args["make"], args.get("year"))
                if q in m["name"].lower() or q in m["slug"]][:50]
    if name == "list_modifications":
        mods = await ws.modifications(args["make"], args["model"], args["year"], args.get("region"))
        return [{"slug": m["slug"], "trim": m.get("trim"), "engine": m.get("engine", {}).get("capacity"),
                 "fuel": m.get("engine", {}).get("fuel"), "regions": m.get("regions")} for m in mods][:60]

    item = await ws.oem_specs(args["make"], args["model"], args["modification"], args.get("region"))
    if not item:
        return {"error": "No OEM data found for that vehicle/modification."}
    if name == "get_oem_specs":
        return {
            "vehicle": f"{item['make']['name']} {item['model']['name']} {item.get('trim') or ''} "
                       f"({item['start_year']}-{item['end_year']})",
            "technical": item.get("technical"),
            "wheels": [{"is_stock": w["is_stock"], "front": _compact_axle(w["front"]),
                        "rear": _compact_axle(w["rear"])} for w in item.get("wheels", [])],
        }
    if name == "check_fitment":
        return check_fitment(item, args["front"], args.get("rear"))
    return {"error": f"Unknown tool {name}"}


class FitmentAgent:
    def __init__(self, ws: WheelSizeClient):
        self._ws = ws
        self._llm = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    async def chat(self, history: list[dict], user_message: str) -> str:
        history.append({"role": "user", "content": user_message})
        for _ in range(MAX_STEPS):
            resp = await self._llm.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history],
                tools=TOOLS,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                history.append({"role": "assistant", "content": msg.content or ""})
                return msg.content or ""

            history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name, "arguments": c.function.arguments}}
                               for c in msg.tool_calls],
            })
            for call in msg.tool_calls:
                try:
                    result = await _dispatch(self._ws, call.function.name, json.loads(call.function.arguments))
                except Exception as exc:  # surfaced to the model so it can recover
                    result = {"error": f"{type(exc).__name__}: {exc}"}
                history.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        return "Sorry, I couldn't complete that lookup. Please try rephrasing or give more vehicle details."
