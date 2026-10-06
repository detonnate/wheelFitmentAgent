# Setup guide

This guide gets the Wheel Fitment agent running in VS Code. It takes about 10 minutes and needs no coding.

The agent uses **your own GitHub Copilot account** for the AI, and **your own free API keys** for the data.

## What you need

| | Required | Cost |
|---|---|---|
| [VS Code](https://code.visualstudio.com/) | Yes | Free |
| GitHub Copilot (signed in to VS Code) | Yes | Free plan works, or any paid plan |
| `uv` (a small tool that runs the agent) | Yes | Free |
| Wheel-Size API key | Yes | Free plan |
| Google Gemini API key | Only for the image preview | Needs a billing-enabled Google account |

## Step 1: Install VS Code and sign in to Copilot

1. Install [VS Code](https://code.visualstudio.com/).
2. Open the Extensions view (`Ctrl+Shift+X`) and install **GitHub Copilot** and **GitHub Copilot Chat** if they are not already there.
3. Click the account icon (bottom left) and **sign in with GitHub**. Check the Copilot icon in the status bar shows no warning.

## Step 2: Install `uv`

`uv` downloads and runs the agent for you. You do not need to install Python.

**Windows** (open PowerShell):

```powershell
winget install --id astral-sh.uv
```

**macOS / Linux**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then **close and reopen VS Code** so it can find `uv`. To check, open a terminal and run `uvx --version`; it should print a version number.

## Step 3: Get your Wheel-Size API key (required)

1. Go to https://developer.wheel-size.com/ and create an account.
2. Choose a plan (the free plan is enough to start) and copy your **API key** from your dashboard.

The free plan only allows a limited number of calls per month. The agent counts them for you (default limit 300) and stops before going over. Each car check uses about 4 to 5 calls.

## Step 4: Get your Gemini API key (optional, for image previews)

Skip this if you only want fitment checks.

1. Go to https://aistudio.google.com/apikey and sign in with your Google account.
2. Click **Create API key** and copy it.
3. Image generation is not on Google's free tier. Turn on billing for the project in Google AI Studio, otherwise renders fail with a quota error.

Without a Gemini key the agent works as normal, it just has no render tool.

## Step 5: Add the agent to VS Code

1. Press `Ctrl+Shift+P` (macOS: `Cmd+Shift+P`) to open the Command Palette.
2. Run **MCP: Open User Configuration**. A file called `mcp.json` opens.
3. Replace its contents with this and save:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "wheelsize-api-key",
      "description": "Wheel-Size API key",
      "password": true
    },
    {
      "type": "promptString",
      "id": "gemini-api-key",
      "description": "Gemini API key (optional, leave blank to skip image previews)",
      "password": true
    }
  ],
  "servers": {
    "wheel-fitment": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/detonnate/wheelFitmentAgent", "wheel-fitment-mcp"],
      "env": {
        "WHEELSIZE_API_KEY": "${input:wheelsize-api-key}",
        "GEMINI_API_KEY": "${input:gemini-api-key}"
      }
    }
  }
}
```

If the file already has other servers, add only the `wheel-fitment` block and the two `inputs` to it.

Prefer one project only? Save the same content as `.vscode/mcp.json` inside that project instead.

## Step 6: Start it and enter your keys

1. In `mcp.json`, click **Start** just above `"wheel-fitment"`.
2. VS Code asks for the **Wheel-Size API key**. Paste it and press Enter. The input is hidden.
3. VS Code asks for the **Gemini API key**. Paste it, or just press Enter to skip.
4. The first start takes a minute while the agent downloads. After that it starts in seconds.

VS Code remembers your keys securely, so you will not be asked again.

## Step 7 (optional): Add the Wheel Fitment agent

This gives you a "Wheel Fitment" option in the chat agent picker, set up with the right instructions.

1. Download [wheel-fitment.agent.md](.github/agents/wheel-fitment.agent.md) from this repo.
2. Save it into a `.github/agents/` folder in your project (create the folder if needed).

You can skip this step. The tools also work in normal **Agent** mode, because the server includes its own instructions.

## Step 8: Use it

1. Open Copilot Chat (`Ctrl+Alt+I`).
2. Choose **Wheel Fitment** in the agent picker, or switch the chat to **Agent** mode.
3. Click the tools icon and check `wheel-fitment` is ticked.
4. Ask a question, for example:

> I have a 2003 BMW 330i saloon (EU). Will 18x8 ET47 wheels with 225/40R18 tyres fit? Bolt pattern 5x120, centre bore 72.6.

The agent finds your car, pulls the factory specs and gives a verdict: `SHOULD FIT`, `FITS WITH CAVEATS` or `WILL NOT FIT`, with the numbers behind it.

### Preview wheels on your car

If you added a Gemini key, ask for a render and give the file paths:

> Render my car `C:\Pictures\car.jpg` with the wheels in `C:\Pictures\wheel.jpg`.

The image is saved to `.wheel-fitment-agent/renders/` in your home folder. Number plates and other personal details are blanked automatically.

See [HOW-IT-WORKS.md](HOW-IT-WORKS.md) for a full example.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uvx` not found | Close and reopen VS Code after installing `uv`. Run `uvx --version` in a terminal to check. |
| Server won't start | Open the Output panel and choose `MCP: wheel-fitment` to see the error. Make sure you are online for the first start. |
| Can't download from GitHub | The repo must be public, or you need access to it. |
| No `wheel-fitment` tools in chat | Use **Agent** mode, click the tools icon and tick `wheel-fitment`. |
| Wheel-Size error such as `HTTP 401` | The key is wrong. Re-enter it: in `mcp.json` rename the input id (for example `wheelsize-api-key` to `wheelsize-api-key-2`, in both the `inputs` list and the `env` line), save, and restart the server. VS Code will prompt for the key again. |
| "monthly quota reached" | You have used your allowed Wheel-Size calls. Ask the agent for `wheelsize_api_usage`, wait for next month, or raise the limit with a `WHEELSIZE_MONTHLY_LIMIT` entry in the `env` block. |
| No render tool | You did not enter a Gemini key. Rename the `gemini-api-key` input id as above to be prompted again, and enter the key. |
| Render fails with a quota error | Turn on billing for your Gemini project. |
| Render says it returned no image | Google's filters sometimes refuse. The tool retries three times; try again or change the photo. |

## Updating

To pick up new versions, add `"--refresh"` to the start of the `args` list in `mcp.json` (before `"--from"`), then restart the server.

## Keeping your keys safe

- Keys are typed into hidden prompts and never written into your project.
- Never paste a key into a chat, a screenshot or a public file. If you do, create a new key and delete the old one.
