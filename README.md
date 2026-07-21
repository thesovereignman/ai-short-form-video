# AI Short-Form Video — Agent Skill

A step-by-step playbook that guides an AI agent through producing a complete short-form video (Instagram Reels, YouTube Shorts, TikTok) from scratch: script, AI voiceover, animated scenes, background music, synced captions, final assembly, and publishing.

## What's in this repo

| File | What it is |
| --- | --- |
| `SKILL.md` | The skill itself — readable markdown, works with any AI agent that supports skills or custom instructions |
| `ai-short-form-video.skill` | One-click install package for the Claude desktop app |
| `references/original-playbook.md` | Environment-specific playbook for Hermes + Zapier + Replicate setups — also bundled inside both downloads |

## Install

**Claude desktop app:** download `ai-short-form-video.skill`, drag it into a Claude chat, and click **Save skill**. Then just ask for a short-form video. (The `.skill` file is for Claude only.)

**Other AI tools (Hermes, OpenAI Codex, Gemini CLI, Kimi, OpenClaw, and anything else that supports the open SKILL.md standard):** download `SKILL.md` and drop it into your tool's skills folder — e.g. `~/.hermes/skills/` for Hermes. If your tool doesn't support skills, paste the contents into its custom instructions.

## What you'll need

The skill orchestrates a few external services (bring your own accounts):

- **Replicate** — video generation (Seedance 2.0) and character art (GPT Image 2)
- **ElevenLabs** — AI voiceover
- **MusicGPT** or similar — background music (optional)
- **Buffer** or similar — social publishing (optional)
- **FFmpeg** — video assembly (free)

## How it works

The skill walks the agent through 9 phases: brand intake → script → voiceover → character art → scene generation → music → editing → captions → delivery and publishing. It includes battle-tested prompts, FFmpeg commands, and a long list of pitfalls learned the hard way (model quirks, caption timing, audio mixing).
