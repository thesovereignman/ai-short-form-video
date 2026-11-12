# AI Short-Form Video — Agent Skill

A step-by-step playbook that guides an AI agent through producing a complete short-form video (Instagram Reels, YouTube Shorts, TikTok) from scratch: script, AI voiceover, animated scenes, background music, synced captions, final assembly, and publishing.

## What's in this repo

| File | What it is |
| --- | --- |
| `SKILL.md` | The skill itself — readable markdown, works with any AI agent that supports skills or custom instructions |
| `ai-short-form-video.skill` | One-click install package for the Claude desktop app |
| `references/original-playbook.md` | Environment-specific playbook for Hermes + Zapier + Replicate setups — also bundled inside both downloads |
| `references/sume.md` | Sume MCP and REST workflow, likeness/voice references, setup and rollout checks |
| `references/sume-migration-audit.md` | Existing integration inventory and exact model mapping |
| `scripts/sume_client.py` | Server-side Python helper: catalog, estimates, owned jobs, polling, results and cancellation |
| `examples/`, `tests/` | Explicit request examples and offline lifecycle/security tests |

## Install

**Claude desktop app:** download `ai-short-form-video.skill`, drag it into a Claude chat, and click **Save skill**. Then just ask for a short-form video. (The `.skill` file is for Claude only.)

**Other AI tools (Hermes, OpenAI Codex, Gemini CLI, Kimi, OpenClaw, and anything else that supports the open SKILL.md standard):** copy this repository's skill folder, including `references/`, `scripts/` and `examples/`, into your tool's skills folder. A lone `SKILL.md` omits the Sume helper and workflow. If your tool doesn't support skills, use the playbook as custom instructions and run the helper separately on your server.

## What you'll need

The skill orchestrates a few external services (bring your own accounts):

- **Sume** MCP or server API — optional generation provider; exact dollar estimates and server-side job ownership. See [setup](references/sume.md).
- **Replicate** — retained legacy video generation (Seedance 2.0) and character art (GPT Image 2)
- **ElevenLabs** — AI voiceover
- **MusicGPT** or similar — background music (optional)
- **Buffer** or similar — social publishing (optional)
- **FFmpeg** — video assembly (free)

## How it works

The skill walks the agent through 9 phases: brand intake → script → voiceover → character art → scene generation → music → editing → captions → delivery and publishing. It includes battle-tested prompts, FFmpeg commands, and a long list of pitfalls learned the hard way (model quirks, caption timing, audio mixing).

Sume is opt-in. No production app or traffic is deployed by this repository.
Copy `.env.example` to `.env`, configure `SUME_API_KEY` locally, and follow the
[Sume guide](references/sume.md). Keep the default provider unchanged until each
mapped model completes a real Sume job. No credential migration or social posting
happens automatically.

Offline validation: `python3 -m unittest discover -s tests -v`.
Rebuild the install package: `python3 scripts/package_skill.py`.
