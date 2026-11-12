# Sume: provider setup, likeness, and job lifecycle

Use this route when the user selects Sume. Read `sume-migration-audit.md` first.
Keep the approved script, cast, voice, footage, CTA, edit, and publishing approval.
A provider change is not permission to regenerate accepted scenes or pick another
person's voice. Costs are US dollars.

## Connected MCP

1. Check `balance`. Load `get_workflow_instructions` for `ad-video` when producing
   an ad, then read the relevant workflow files. Follow the current tool schema.
2. Discover models with `models_explore`. Match the family, version, mode and
   resolution; a newer model is a deliberate choice, not an equivalent mapping.
3. Quote the exact request using `dry_run: true`. Use `max_spend_usd` on the paid
   call. Reuse the same idempotency key if a submission times out.
4. Wait for that job with `jobs_wait(include_results: true)` in bounded slices.
   A wait timeout is not a failed generation. Inspect the actual result.
5. Use existing clips where possible. Keep exact phone UI, captions, URL, and
   end-card text in the edit. Show the assembled video before publishing when
   the user requested review.

MCP OAuth is separate from a server API key. A read-only connection cannot spend;
an `insufficient_scope` response requires reconnecting with creation access.
Do not extract or repurpose the MCP OAuth token as a server API key.

## Recreating an authorized person's likeness

Face, voice and performance are separate inputs. A Higgsfield Soul/element ID or
voice ID is not a Sume identity. Reuse the user's actual photos and audio files.

- **For a new spoken performance:** Sume's current `seedance-2.5` supports image
  and audio references together. The voice sample conditions new speech; this is
  not proof that a durable cloned voice has been registered. State the new lines
  explicitly and compare a short test with the supplied voice before scaling up.
- **For exact approved narration:** lip-sync a camera-facing still to the actual
  narration with VEED Fabric. The MCP route requires Sume-hosted audio; import it
  with the supported media tools first. Preserve the recorded words and timing.
- **For a reusable avatar resource:** the REST API documents
  `POST /v1/avatar-1.0/generate` with
  `{"avatar_handle":"my_presenter","input":{"type":"photo","image_url":"https://..."}}`.
  This creates a new Sume resource after its job succeeds. Avatar creation alone
  does not establish the person's custom voice. No public voice-cloning endpoint
  was found in the live OpenAPI inspected on 2026-11-11.

Prefer clear, natural, unfiltered photos with the face unobstructed and enough
head/shoulder framing for the intended shot. Preserve identity and natural skin
texture; don't infer identity from demographic descriptions. Check the eyes,
glasses, teeth, hands, facial proportions, voice match and pronunciation.

REST `seedance-2.5` uses `reference_image_urls` and `reference_audio_urls`.
The current MCP uses `input_references`, for example:

```json
{
  "model": "seedance-2.5",
  "prompt": "The person from the image speaks these new words in the voice of @Audio1: ...",
  "input_references": [
    {"type":"image_url","image_url":{"url":"https://.../portrait.jpg"}},
    {"type":"audio_url","audio_url":{"url":"https://.../voice.wav"}}
  ],
  "duration": 10,
  "resolution": "720p",
  "aspect_ratio": "9:16",
  "generate_audio": true
}
```

For this model, reference audio must be MP3/WAV, 1.8–30.2 seconds per file, at most
15 MB per file and 30.2 seconds total. Do not combine first/last-frame inputs with
mixed references. Recheck these constraints against the live catalog/schema.

## Server / local CLI

Python 3.10+, standard library only. Copy `.env.example` to `.env` and set
`SUME_API_KEY` locally from **Sume → Sume API → API keys**. The CLI reads this file
without executing shell code. Never paste the key in chat, browser code or commits.

```bash
python3 scripts/sume_client.py catalog
python3 scripts/sume_client.py estimate --request examples/sume-roof-scene.json
python3 scripts/sume_client.py estimate --request examples/sume-portrait.json --old-usd 0.50
```

The `--old-usd 0.50` above is an example input, **not a verified previous price**.
Supply the old provider's actual quote for the same request, or omit it; the
comparison will show `null`, not invented savings. Catalog and estimate are public
read/quote endpoints and do not need a key. A paid submission does.

After reviewing the exact estimate, opt into Sume for that invocation:

```bash
VIDEO_GENERATION_PROVIDER=sume python3 scripts/sume_client.py submit \
  --owner trusted-local-operator --operation film1-roof-take1 \
  --request examples/sume-roof-scene.json --max-usd 1.30
python3 scripts/sume_client.py wait --owner trusted-local-operator --job job_REPLACE
python3 scripts/sume_client.py result --owner trusted-local-operator --job job_REPLACE
python3 scripts/sume_client.py cancel --owner trusted-local-operator --job job_REPLACE
```

The CLI retains the job and operation owner in `.sume/jobs.sqlite3` (mode 0600,
gitignored). Reuse the exact `--operation` and request after a lost submit response.
An intentional new take needs a new operation. Restore/retain this database when
moving the helper; losing it loses local ownership and recovery records.

**Backend integration:** import `SumeClient`, derive `owner_id` from your existing
authenticated session, and call its methods on the server. Do not accept an
owner ID from an untrusted browser. This repository has no web app or auth system;
the CLI's `--owner` is a trusted operator label, not login/authentication. Status,
result and cancellation enforce stored ownership before making any remote call.

`max_usd` checks the fresh exact estimate before submission. It is a client-side
check, not a server-enforced invoice ceiling. Use the MCP's `max_spend_usd` when a
hard per-call admission cap is required. There are no automatic paid retries.

## Lifecycle, uploads and errors

- REST: GET `/v1/open/catalog`; POST `/v1/open/estimate` with `{model,input}`;
  POST the matching router with **flattened** `{model,...input,mode:"async"}`.
- Store the accepted job ID, then poll `/v1/jobs/{id}/status`. The live API can
  return uppercase queue `status` and lowercase `sume_status`; use `sume_status`.
- Fetch `/result` only after `completed` and `result_ready`. Stop polling on
  `failed` or `canceled`. A local wait timeout never cancels or re-submits a job.
- Cancellation can fail with 409 after provider work starts. Do not promise
  cancellation or refund before the provider confirms the terminal outcome.
- Normal REST inputs accept fetchable public HTTPS URLs. Replicate-authenticated
  file URLs will not transfer automatically. Use the user's approved media host
  or Sume MCP upload/import; there is no invented public REST upload implementation
  here. Keep returned Sume artifact URLs rather than raw provider result URLs.
- 401: configure the server key; 402: quote required/available dollars; 429: honor
  Retry-After; 5xx/timeout: outcome may be unknown, recover with the same operation.
  API errors expose only bounded error/request IDs, never headers or raw payloads.
- This helper polls. If adding webhooks later, verify the raw-body HMAC-SHA256,
  timestamp/replay window and rotating `sume-v1` signatures, persist events
  idempotently, and look up job ownership locally. Never trust callback owner data.

## Rollout checks

Run `python3 -m unittest discover -s tests -v`. Then quote and complete one real job
for **each** mapped model, verify artifacts, and record the job IDs privately.
Only then change the default or retire unused provider keys. Existing narration,
music, and publishing integrations still need their credentials.

Official sources checked 2026-11-11:
[index](https://docs.sume.com/llms.txt),
[live schema](https://api.sume.com/reference/json),
[catalog](https://api.sume.com/v1/open/catalog),
[avatar](https://docs.sume.com/models/avatar.md),
[media inputs](https://docs.sume.com/workflows/asset-library.md),
[webhooks](https://docs.sume.com/workflows/webhooks.md),
[errors](https://docs.sume.com/workflows/errors-and-credits.md).
Some narrative docs still say credits; current catalog/estimate and MCP prices
are in dollars. Prefer the live schema and current tool contract on conflicts.
