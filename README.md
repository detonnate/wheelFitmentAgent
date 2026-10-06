# Wheel Fitment Agent

A GitHub Copilot agent for VS Code that tells you whether a set of wheels and tyres will fit a car.

It runs as an [MCP server](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) that Copilot Chat calls in agent mode. That means:

- AI usage comes from **your own GitHub Copilot account and credits**. No OpenAI key is needed.
- You supply **your own [Wheel-Size API key](https://developer.wheel-size.com/)**, entered securely when the server starts. It is never stored in the repo.

The server looks up OEM wheel/tyre data from Wheel-Size and runs deterministic checks: bolt pattern, centre bore, overall tyre diameter, rim/tyre width match, and how far the wheel sits in or out compared with factory sizes. Results are calculated estimates; always verify on the vehicle, especially for lowered or cambered cars, big brakes or aftermarket suspension.

## Requirements

- VS Code with the GitHub Copilot and Copilot Chat extensions, signed in to a Copilot plan
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (provides `uvx`, which downloads and runs the server for you)
- A Wheel-Size API key

## Install

1. Install `uv`, e.g. on Windows: `winget install astral-sh.uv`
2. Add the server to VS Code. Either:
   - **Per project:** copy [.vscode/mcp.json](.vscode/mcp.json) into your workspace's `.vscode/` folder, or
   - **For all projects:** run **MCP: Open User Configuration** from the Command Palette and paste the contents of that file in.
3. Start the server: open `mcp.json` and click **Start** above the `wheel-fitment` entry. VS Code prompts for your Wheel-Size key (hidden input). Leave the Gemini prompt blank unless you want rendering (see below).
4. *(Optional)* Add the custom agent: copy [.github/agents/wheel-fitment.agent.md](.github/agents/wheel-fitment.agent.md) into your workspace's `.github/agents/` folder, or run **Chat: New Custom Agent** and paste it in.

The server runs straight from this repo with `uvx --from git+https://github.com/detonnate/wheelFitmentAgent wheel-fitment-mcp`, so it needs read access to the repo.

## Use

Open Copilot Chat, choose **Wheel Fitment** from the agent picker (or use **Agent** mode and make sure the `wheel-fitment` tools are enabled), then ask, for example:

> 2003 BMW E46 325Ci, UK. Will 18x8 ET47 wheels with 225/40R18 tyres fit? Bolt pattern is 5x120 and centre bore 72.6.

The agent finds your exact car, pulls its OEM specs and answers with one of:

- `SHOULD FIT`
- `FITS WITH CAVEATS` (e.g. check arch or brake clearance, speedo error, hub rings needed)
- `WILL NOT FIT` (e.g. wrong bolt pattern, bore too small, poke or push beyond tolerance)

along with the numbers behind it. For staggered setups give front and rear sizes.

### Tools

| Tool | Purpose |
|---|---|
| `search_makes`, `search_models`, `list_modifications` | Identify the exact vehicle |
| `get_oem_specs` | Factory wheel/tyre sizes, bolt pattern, centre bore |
| `check_wheel_fitment` | Fitment verdict for proposed wheels/tyres |
| `wheelsize_api_usage` | Calls used this month vs the limit |
| `render_car_with_wheels_tool` | Optional, see below |

### API quota

Every real Wheel-Size request is counted in `~/.wheel-fitment-agent/wheelsize_usage.json` (resets monthly). When the limit is reached, calls stop with a clear error. The default limit is 300; change it by setting `WHEELSIZE_MONTHLY_LIMIT` in the server's `env` block. Repeated identical requests in one session are cached and cost nothing. A fitment check typically uses 4-5 calls.

## Optional: render a car with new wheels

GitHub Copilot has no image generation, so this tool only appears if you provide a Google Gemini API key ([get one in AI Studio](https://aistudio.google.com/apikey)) at the second prompt. Gemini's image models ("Nano Banana") need a **billing-enabled** Google project; on the free tier the image models return a quota error.

It lets you ask Copilot to render a car with new wheels, using file paths to photos or text descriptions: a car photo plus a wheel photo/description edits the photo, and a car description generates one. Images must be JPEG, PNG or WebP up to 10 MB. Renders are saved to `~/.wheel-fitment-agent/renders/`. The model defaults to `gemini-3.1-flash-image`; override it with `GEMINI_IMAGE_MODEL` in the server's `env` block.

## Develop

```powershell
git clone https://github.com/detonnate/wheelFitmentAgent.git
cd wheelFitmentAgent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

To run your local copy in VS Code, change the server entry in `mcp.json` to:

```json
"command": "uv",
"args": ["run", "--directory", "${workspaceFolder}", "wheel-fitment-mcp"]
```

Layout:

```
wheel_fitment/
  server.py      MCP server and tools
  fitment.py     Deterministic fitment checks
  wheelsize.py   Wheel-Size API client (quota counter + cache)
  rendering.py   Optional image editing/generation (Gemini)
.github/agents/  Custom Copilot agent definition
.vscode/mcp.json Server configuration with secure key prompts
tests/           Fitment unit tests
```

Thresholds for poke/push (`OUT_OK`, `OUT_WARN`, `IN_OK`, `IN_WARN`) and the tyre-width rule are rules of thumb in `wheel_fitment/fitment.py`. Adjust them to your tolerance.
