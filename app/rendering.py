import base64

from openai import AsyncOpenAI

from . import config


class RenderError(ValueError):
    pass


def _data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


async def _describe_wheel(llm: AsyncOpenAI, data: bytes, mime: str) -> str:
    resp = await llm.chat.completions.create(
        model=config.OPENAI_VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this wheel for a 3D artist in one paragraph: spoke design and count, "
                                         "finish/colour, lip style, centre cap, approximate depth/dish."},
                {"type": "image_url", "image_url": {"url": _data_url(data, mime)}},
            ],
        }],
    )
    return resp.choices[0].message.content or ""


async def render_car_with_wheels(
    *,
    car_image: tuple[bytes, str] | None,
    wheel_image: tuple[bytes, str] | None,
    car_description: str = "",
    wheel_description: str = "",
    stance_notes: str = "",
) -> bytes:
    """Return PNG bytes of the car fitted with the new wheels.

    Uses image editing when a car photo is supplied, otherwise generates the car from a description.
    """
    if not car_image and not car_description.strip():
        raise RenderError("Provide a car photo or a car description.")
    if not wheel_image and not wheel_description.strip():
        raise RenderError("Provide a wheel photo or a wheel description.")

    llm = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    stance = f" Stance/fitment: {stance_notes.strip()}." if stance_notes.strip() else ""

    if car_image:
        files = [("car.png", car_image[0], car_image[1])]
        if wheel_image:
            files.append(("wheel.png", wheel_image[0], wheel_image[1]))
            wheel_ref = "the wheels shown in the second image"
        else:
            wheel_ref = f"wheels described as: {wheel_description.strip()}"
        prompt = (
            f"Edit the first image: replace all visible wheels on the car with {wheel_ref}. "
            "Keep the car body, colour, background, lighting, camera angle and tyres' realism unchanged. "
            f"Match wheel perspective and reflections to the scene.{stance}"
        )
        result = await llm.images.edit(model=config.OPENAI_IMAGE_MODEL, image=files, prompt=prompt)
    else:
        wheel_text = wheel_description.strip()
        if wheel_image:
            wheel_text = (wheel_text + " " + await _describe_wheel(llm, *wheel_image)).strip()
        prompt = (
            f"Photorealistic side three-quarter view of a {car_description.strip()} fitted with these wheels: "
            f"{wheel_text}.{stance} Studio lighting, neutral background."
        )
        result = await llm.images.generate(model=config.OPENAI_IMAGE_MODEL, prompt=prompt, size="1536x1024")

    b64 = result.data[0].b64_json
    if not b64:
        raise RenderError("Image model returned no image.")
    return base64.b64decode(b64)
