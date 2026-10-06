import json
import threading
from datetime import date
from pathlib import Path

import httpx

from . import config

USAGE_FILE = config.DATA_DIR / "wheelsize_usage.json"


class QuotaExceeded(RuntimeError):
    pass


class WheelSizeError(RuntimeError):
    pass


class _UsageCounter:
    """Persists the number of upstream API calls made this month."""

    def __init__(self, path: Path, limit: int):
        self._path, self._limit, self._lock = path, limit, threading.Lock()

    def _load(self) -> dict:
        month = date.today().strftime("%Y-%m")
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            data = {}
        return data if data.get("month") == month else {"month": month, "calls": 0}

    def consume(self) -> int:
        with self._lock:
            data = self._load()
            if data["calls"] >= self._limit:
                raise QuotaExceeded(f"Wheel-Size monthly quota of {self._limit} calls reached.")
            data["calls"] += 1
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data))
            return data["calls"]

    def status(self) -> dict:
        data = self._load()
        return {"month": data["month"], "calls_used": data["calls"], "monthly_limit": self._limit}


class WheelSizeClient:
    def __init__(self, api_key: str = config.WHEELSIZE_API_KEY, base_url: str = config.WHEELSIZE_BASE_URL):
        self._key = api_key
        self._http = httpx.AsyncClient(base_url=base_url, timeout=20)
        self._usage = _UsageCounter(USAGE_FILE, config.WHEELSIZE_MONTHLY_LIMIT)
        self._cache: dict[tuple, list[dict]] = {}

    async def aclose(self) -> None:
        await self._http.aclose()

    def usage(self) -> dict:
        return self._usage.status()

    async def _get(self, path: str, **params) -> list[dict]:
        if not self._key:
            raise WheelSizeError("No Wheel-Size API key configured (set WHEELSIZE_API_KEY).")
        query = {k: v for k, v in params.items() if v not in (None, "")}
        cache_key = (path, tuple(sorted(query.items())))
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._usage.consume()
        resp = await self._http.get(path, params={**query, "user_key": self._key})
        if resp.status_code >= 400:
            # Raised without the URL so the API key never reaches logs or the model.
            raise WheelSizeError(f"Wheel-Size API returned HTTP {resp.status_code} for {path}")
        data = resp.json().get("data", [])
        self._cache[cache_key] = data
        return data

    async def makes(self, region: str | None = None) -> list[dict]:
        return await self._get("/makes/", region=region)

    async def models(self, make: str, year: int | None = None, region: str | None = None) -> list[dict]:
        return await self._get("/models/", make=make, year=year, region=region)

    async def years(self, make: str, model: str) -> list[dict]:
        return await self._get("/years/", make=make, model=model)

    async def modifications(self, make: str, model: str, year: int, region: str | None = None) -> list[dict]:
        return await self._get("/modifications/", make=make, model=model, year=year, region=region)

    async def oem_specs(self, make: str, model: str, modification: str, region: str | None = None) -> dict | None:
        data = await self._get(
            "/search/by_model/", make=make, model=model, modification=modification, region=region
        )
        return data[0] if data else None
