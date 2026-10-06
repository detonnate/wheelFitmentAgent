# Wheel Fitment Agent

An AI agent that tells you whether a set of wheels and tyres will fit a car, and can render a car with new wheels on it.

- **Fitment advice:** looks up OEM wheel/tyre data from the [Wheel-Size API](https://developer.wheel-size.com/), then checks bolt pattern, centre bore, tyre diameter, rim/tyre width match and how far the wheel sits in or out compared with factory sizes.
- **Rendering:** upload a car photo and/or a wheel photo (or describe either) and get an image of the car with those wheels, using OpenAI image models.

Fitment results are calculated estimates. Always verify on the vehicle, especially for lowered or cambered cars, big brake kits or aftermarket suspension.

## Requirements

- Python 3.11+
- A Wheel-Size API key
- An OpenAI API key

## Install

```powershell
git clone https://github.com/detonnate/wheelFitmentAgent.git
cd wheelFitmentAgent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## Configure

Copy `.env.example` to `.env` and fill in your keys:

```
WHEELSIZE_API_KEY=your-wheel-size-key
OPENAI_API_KEY=your-openai-key
```

Optional settings:

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4.1` | Chat/agent model |
| `OPENAI_VISION_MODEL` | `gpt-4.1-mini` | Describes uploaded wheel photos |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1` | Rendering model |
| `WHEELSIZE_MONTHLY_LIMIT` | `300` | Max Wheel-Size API calls per month |

`.env` is git-ignored. Never commit it.

### API quota

The app counts every real Wheel-Size request in `.wheelsize_usage.json` (resets each month) and stops at `WHEELSIZE_MONTHLY_LIMIT`. Identical requests in one session are cached and cost nothing. A single fitment check typically uses 4-5 calls.

## Run

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Use

### Check fitment

In the chat panel, give the agent:

1. Your car: make, model, year, region (e.g. `eudm` for Europe, `usdm` for USA) and trim/engine.
2. The wheels: diameter (in), width (in), offset/ET (mm), tyre size (e.g. `225/40R18`), and ideally bolt pattern and centre bore.
3. Rear sizes too, if the setup is staggered.

Example: *"2003 BMW E46 325Ci, UK. I have 19x8.5 ET30 on the front with 225/35R19 and 19x10 ET40 on the rear with 265/30R19."*

The agent returns one of:

- `SHOULD FIT`
- `FITS WITH CAVEATS` (e.g. check arch or brake clearance, speedo error, hub rings needed)
- `WILL NOT FIT` (e.g. wrong bolt pattern, bore too small, poke or push beyond tolerance)

along with the numbers behind it (mm further out/in than OEM, overall diameter change).

### Render a car with new wheels

Use the "Preview wheels on a car" panel:

| You provide | Result |
|---|---|
| Car photo + wheel photo | Wheels in your photo are replaced with the ones shown |
| Car photo + wheel description | Wheels replaced based on the description |
| Car description + wheel photo/description | A generated image of that car with the wheels |

Add optional stance notes (e.g. "lowered 30mm, flush fitment"). Images must be JPEG, PNG or WebP, up to 10 MB.

## API

| Endpoint | Description |
|---|---|
| `POST /api/chat` | JSON `{ "message": "...", "session_id": "..." }` returns `{ "session_id", "reply" }` |
| `POST /api/render` | Multipart form: `car_image`, `wheel_image`, `car_description`, `wheel_description`, `stance_notes` returns `{ "image_b64" }` |

Chat history is held in memory and is lost on restart.

## Tests

```powershell
pytest
```

## Project layout

```
app/
  agent.py       OpenAI tool-calling agent
  fitment.py     Deterministic fitment checks
  wheelsize.py   Wheel-Size API client (quota counter + cache)
  rendering.py   Image editing/generation
  main.py        FastAPI app
  static/        Web UI
tests/           Fitment unit tests
```

## Tuning the checks

Thresholds for poke/push (`OUT_OK`, `OUT_WARN`, `IN_OK`, `IN_WARN`) and the tyre-width rule are rules of thumb in `app/fitment.py`. Adjust them to your tolerance.
