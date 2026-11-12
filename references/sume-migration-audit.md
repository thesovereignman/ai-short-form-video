# Sume integration audit — 2026-11-11

## Inventory before editing

This repository is a distributable agent skill, not an application with a backend,
database, or live generation traffic. No executable provider SDK integration or
tracked environment file exists. The integration points are instructional examples:

| Operation | Existing location | Provider / behavior |
| --- | --- | --- |
| Narration submission / result | `SKILL.md`, Phase 2; `references/original-playbook.md`, voiceover | User-configured ElevenLabs / Zapier voice, returned audio URL |
| Reference upload | `SKILL.md`, Phase 3; original playbook character art | Replicate multipart Files API |
| Image submission / result | `SKILL.md`, Phase 3; original playbook character art | `openai/gpt-image-2`, Replicate predictions; prose says poll and download |
| Video submission / polling / result | `SKILL.md`, Phase 4; original playbook scene generation | `bytedance/seedance-2.0`, Replicate prediction ID, `succeeded`, `output` URL |
| Cancellation | Nowhere | Missing |
| Music submission / polling | Phase 5 and original playbook | MusicGPT; task and conversion IDs |
| Assembly / captions | Phases 6–7 | Local FFmpeg / transcription, no provider migration needed |
| Publishing upload / post | Phase 8 and original playbook | Drive / Buffer; separate from generation |

No fal.ai, Higgsfield, or Kie submission implementation exists in this checkout.
The ongoing Service Ghost campaign uses Higgsfield MCP externally; it is not a
server integration in this repository.

## Mapping verified against the live Sume catalog

Source: <https://api.sume.com/v1/open/catalog>, fetched 2026-11-11 Pacific.

| Existing model / service | Sume match | Status |
| --- | --- | --- |
| Replicate `bytedance/seedance-2.0` | `seedance-2`, text/image/reference-to-video, including 720p | Exact family/version match; live paid validation pending |
| Replicate `openai/gpt-image-2` | `gpt-image-2`, text-to-image / image-edit | Exact family/version match; live paid validation pending |
| Legacy `bytedance/seedance-1-lite` | None in current catalog | Unmapped; no automatic substitution |
| Legacy `minimax/video-01` | None in current catalog | Unmapped; Hailuo/H3 are different models |
| User-configured ElevenLabs voice / Higgsfield voice element | No portable identity mapping | Preserve original narration or establish a Sume-compatible voice separately |
| MusicGPT | No exact model mapping | Preserve existing service; Sume music would be an explicit new choice |
| Drive / Buffer / FFmpeg | Not generation models | Preserve |

Sume REST fields differ from MCP fields. REST video uses `image_url` and
`reference_*_urls`; MCP `generate_video` currently accepts `input_references`.
Never copy one payload blindly into the other.

## Rollout and evidence

Public REST estimates verified through the new helper on 2026-11-11 (no spend):

| Exact request file | Sume estimate | Previous provider price |
| --- | --- | --- |
| `examples/sume-roof-scene.json` — Seedance 2.0, 8s, 720p | $1.2096 | Unknown; no prior quote supplied |
| `examples/sume-portrait.json` — GPT Image 2, one high-quality 1K portrait | $0.1138 | Unknown; no prior quote supplied |

These are request-specific estimates, not lasting rate guarantees. Re-estimate
the actual reference inputs before each generation. Offline lifecycle tests pass;
no paid REST job has completed through this helper yet.

- Keep the default provider `legacy`; opt into the new helper with
  `VIDEO_GENERATION_PROVIDER=sume`. No production traffic exists here to switch.
- Run an exact estimate for each request and record the previous provider's
  actual dollar price beside it. No previous price is recorded in this repo;
  leave it unknown instead of inventing savings.
- Complete a real Sume job for every mapped model before changing the default.
  Offline tests and MCP estimates are not proof of REST generation success.
- Keep old integrations and credentials while they are still in use. This change
  does not delete keys or silently reroute narration, music, or publishing.
- The API helper uses polling, not an unverified webhook receiver. Public HTTPS
  references avoid reliance on hidden upload routes. Local photos need an
  authorized upload through Sume MCP or the user's own media storage first.
