import base64

import httpx

from . import config


class RenderError(ValueError):
    pass


_MAX_ATTEMPTS = 3

# Appended to every prompt so renders never carry personal identifiers.
_PRIVACY_RULE = (
    " Privacy: remove or blank out all licence/number plates (replace with a plain blank plate), and remove "
    "or blur any other personal identifying details such as faces, people, VIN numbers, street or house "
    "numbers, addresses, phone numbers, names and dealer or personal stickers or text."
)


def _part_image(data: bytes, mime: str) -> dict:
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}


async def render_car_with_wheels(
    *,
    car_image: tuple[bytes, str] | None,
    wheel_image: tuple[bytes, str] | None,
    car_description: str = "",
    wheel_description: str = "",
    stance_notes: str = "",
) -> bytes:
    """Return image bytes of the car fitted with the new wheels, using Gemini image models.

    Edits the car photo when one is supplied, otherwise generates the car from a description.
    """
    if not config.GEMINI_API_KEY:
        raise RenderError("No Gemini API key configured (set GEMINI_API_KEY).")
    if not car_image and not car_description.strip():
        raise RenderError("Provide a car photo or a car description.")
    if not wheel_image and not wheel_description.strip():
        raise RenderError("Provide a wheel photo or a wheel description.")

    stance = f" Stance/fitment: {stance_notes.strip()}." if stance_notes.strip() else ""
    parts: list[dict] = []

    if car_image:
        wheel_ref = "the wheel shown in the reference wheel image" if wheel_image else \
            f"wheels described as: {wheel_description.strip()}"
        parts.append({"text": (
            f"Edit the first image (the car photo): replace all visible wheels on the car with {wheel_ref}. "
            "Keep the car body, colour, background, lighting, camera angle and tyre realism unchanged. "
            f"Match wheel perspective and reflections to the scene.{stance}{_PRIVACY_RULE}")})
        parts.append(_part_image(*car_image))
    else:
        wheel_ref = "the wheel shown in the reference wheel image" if wheel_image else \
            f"wheels described as: {wheel_description.strip()}"
        parts.append({"text": (
            f"Photorealistic side three-quarter view of a {car_description.strip()} fitted with {wheel_ref}."
            f"{stance} Studio lighting, neutral background.{_PRIVACY_RULE}")})
    if wheel_image:
        parts.append(_part_image(*wheel_image))

    url = f"{config.GEMINI_BASE_URL}/models/{config.GEMINI_IMAGE_MODEL}:generateContent"
    payload = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"]}}
    reason = ""
    # Gemini's image filters (e.g. IMAGE_RECITATION) are intermittent, so a retry often succeeds.
    for _ in range(_MAX_ATTEMPTS):
        async with httpx.AsyncClient(timeout=120) as http:
            resp = await http.post(url, headers={"x-goog-api-key": config.GEMINI_API_KEY}, json=payload)
        if resp.status_code >= 400:
            try:
                detail = resp.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                detail = ""
            raise RenderError(f"Gemini API returned HTTP {resp.status_code}: {detail}".strip())

        body = resp.json()
        for candidate in body.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                blob = part.get("inlineData") or part.get("inline_data")
                if blob and blob.get("data"):
                    return base64.b64decode(blob["data"])

        reason = (body.get("promptFeedback") or {}).get("blockReason") or \
            next((c.get("finishReason") for c in body.get("candidates", []) if c.get("finishReason")), "")
    raise RenderError(f"Gemini returned no image after {_MAX_ATTEMPTS} attempts{f' ({reason})' if reason else ''}.")
