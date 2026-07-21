---
name: ai-short-form-video
description: Produce a complete AI-generated short-form video (Reels, Shorts, TikTok) from scratch — script, voiceover, animated scenes, music, captions, assembly, and publishing. Use when the user wants to create a short vertical video, video content for social media, or an AI video with voiceover and captions. Triggers on: make a short video, create a reel, short-form video, TikTok video, YouTube Short, video with AI voiceover.
---

# AI Short-Form Video Production — Agent Playbook

This skill guides an agent through producing a complete short-form video for a creator or brand from scratch. Follow the phases in order. Each phase has decisions to surface to the user before proceeding.

## Requirements

This skill uses external services. Verify access before starting and ask the user to connect anything missing:

- **Video generation** — a Replicate API token (set as the `REPLICATE_API_TOKEN` environment variable, or ask the user how their credentials are stored). Used for Seedance (video) and GPT Image (character art).
- **Text-to-speech** — an ElevenLabs integration (direct API or via an MCP such as Zapier). Voice selection is configured on the user's side.
- **Music/SFX** (optional) — a music generation service such as MusicGPT (direct or via MCP).
- **Publishing** (optional) — a social scheduling integration such as Buffer (direct or via MCP), plus a way to host the finished video at a public URL (e.g. Google Drive with public sharing).
- **FFmpeg** — for assembly, captions, and audio mixing.

If any integration is delivered through an MCP server, note that newly added MCP tools usually only appear in a fresh session, and hosted MCP tokens can expire — if a tool suddenly returns auth errors, ask the user to refresh their token in the provider's dashboard.

**Environment-specific reference:** if the user's setup is a Hermes agent with Zapier MCP (ElevenLabs, MusicGPT, Buffer) and Replicate, read `references/original-playbook.md` — it contains the exact tool calls, setup procedures, and environment-specific pitfalls for that stack.

---

## Phase 0 — Brand Intake

Before writing a single line, gather what you need. Ask the user:

**Required:**

1. **Topic / hook** — what is this video about? What's the one insight or move you want to land?
2. **Target viewer** — who are they? What do they already know? What do they want?
3. **Tone** — pick the closest: confident/authoritative, conspiratorial/"let me show you something", educational/step-by-step, storytelling, entertaining
4. **Brand handle** — for the watermark (e.g. @yourhandle)
5. **Avatar or character** — do they have a branded avatar/character image? If yes, ask them to share it. If no, ask for a description or skip the character pipeline and use scene-only video.

**Optional but improves output:**

6. **Visual style preference** — pixel-art/retro game, cinematic, modern flat design, illustrated, realistic
7. **Platform** — Instagram Reels, YouTube Shorts, TikTok (affects max duration and feel)
8. **CTA** — what should the viewer do at the end? (follow, link in bio, DM, comment, etc.)
9. **SFX preference** — some creators want no whoosh/transition sound effects at all. Ask rather than assume.

**Do not proceed to Phase 1 until you have at minimum: topic, tone, and handle.**

---

## Phase 1 — Script

Write the VO script before generating anything. Visuals are built around the script, not the other way around.

### Script principles

- **One idea per sentence.** Each line should land on its own when heard aloud.
- **Drop into the insight on line 1.** No "In this video I'm going to show you…" — start with the hook.
- **Don't explain the framework — reveal the insight.** The viewer wants the output, not the methodology labels.
- **Specific beats generic.** Concrete details feel real; abstract labels feel like a deck.
- **End on contrast or payoff.** "Most people do X. This is how you do the opposite." / "That's [result] in [time]."
- **Read it aloud.** Does it sound like a conversation or a blog post? Rewrite until it's the former.

**Word count guide:** 30s video ≈ 80–100 words · 45s ≈ 120–150 · 60s ≈ 150–180

**Hook formula that reliably works:**

> "[What most people do] → [The smarter/opposite move]"

### Surface the script to the user before proceeding

Write a draft, show it, and ask: *"Does this sound like you? Anything that feels off — too formal, wrong angle, missing something?"* Iterate until they approve it. A bad script can't be fixed in edit.

### Map the script to a scene timeline

Once approved, break it into beats and estimate timing:

```
0–3s    Hook / visual opener (no VO or first line only)
3–12s   Setup / tension
12–22s  The move / method
22–32s  What it gives you
32–40s  Payoff / CTA
```

Each beat = one video-generation clip.

---

## Phase 2 — Voiceover

Generate the VO before scenes — the audio duration drives everything else.

Call your ElevenLabs integration with the approved script, delivery instructions (pace, tone, energy, pauses — e.g. "Calm and confident. Natural pauses between punchy lines. Not hype, not salesy. Like telling a friend something useful over coffee."), and `output_format="mp3_44100_128"`.

- **Download the returned URL immediately** — hosted TTS URLs are often short-lived S3 links that expire in minutes: `wget -q "<url>" -O /tmp/vo.mp3`
- Check actual duration: `ffprobe -v quiet -show_entries format=duration -of csv=p=0 /tmp/vo.mp3`
- Adjust your scene timeline to match the real duration.

---

## Phase 3 — Character Art (skip if no avatar)

If the user has a branded avatar, use GPT Image (img2img) to create a stylized version matching their chosen visual style. This becomes the first frame for the video model.

### Why img2img matters

Without passing the avatar as `input_images`, the model invents a generic character. The avatar reference preserves the face, clothing, accessories, and personality of the brand character.

### Submit to GPT Image via Replicate

Upload the avatar to Replicate's Files API first — **multipart only**: `curl -F "content=@avatar.jpg;type=image/jpeg" -H "Authorization: Bearer $REPLICATE_API_TOKEN" https://api.replicate.com/v1/files` (base64 and `--data-binary` both fail).

```python
import urllib.request, json, os

RT = os.environ["REPLICATE_API_TOKEN"]

payload = json.dumps({"input": {
    "prompt": (
        "Convert this character into [TARGET STYLE — e.g. '2D pixel-art video game sprite in 16-bit SNES RPG style']. "
        "Preserve ALL character features exactly: [describe skin tone, hair, clothing, accessories explicitly — "
        "and include what features are NOT present]. "
        "Full-body front-facing standing pose. Background: [describe scene]. "
        "Style reference: [e.g. 'Chrono Trigger overworld sprites']. "
        "ALL content at least 60px from every edge — nothing cropped."
    ),
    "input_images": ["https://api.replicate.com/v1/files/<uploaded_id>"],
    "aspect_ratio": "2:3",   # ⚠️ "9:16" returns HTTP 422 — always use "2:3", scale in FFmpeg
    "quality": "high",
    "output_format": "png",
    "number_of_images": 1
}}).encode()

req = urllib.request.Request(
    "https://api.replicate.com/v1/models/openai/gpt-image-2/predictions",
    data=payload,
    headers={"Authorization": f"Bearer {RT}", "Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as r:
    pred_id = json.loads(r.read())["id"]
```

Poll until succeeded, download the PNG, and **show it to the user before spending video credits animating it**.

**Skin tone / likeness pitfall:** image models default to generic racial interpretations of illustrated characters. Always (1) pass the original as `input_images` AND (2) describe what the features are NOT (e.g. "NOT dark brown or black skin — warm olive/Mediterranean"). The explicit negation is mandatory.

---

## Phase 4 — Scene Generation

Submit ALL scene predictions in parallel before polling any — they run concurrently on Replicate.

### Seedance 2.0 — key inputs

```json
{
  "prompt": "Scene description. Camera movement. Lighting. Use \"quoted dialogue\" for lip sync.",
  "image": "<first_frame_url_or_uploaded_file>",
  "duration": 8,
  "resolution": "720p",
  "aspect_ratio": "9:16",
  "generate_audio": false
}
```

**⚠️ `image` (first frame) and `reference_audios` are mutually exclusive in Seedance 2.0** (error E006). Choices:

- **`image` only** — controls first frame, mix VO in FFmpeg post. Best for stylized/pixel characters (no lip sync needed).
- **`reference_images[]` + `reference_audios[]`** — character consistency + audio sync, but no guaranteed first frame.

### Parallel submit + poll

```python
import urllib.request, json, time, os

RT = os.environ["REPLICATE_API_TOKEN"]

def submit_scene(prompt, image_url=None, duration=8):
    payload = {"input": {
        "prompt": prompt, "duration": duration,
        "resolution": "720p", "aspect_ratio": "9:16", "generate_audio": False
    }}
    if image_url:
        payload["input"]["image"] = image_url
    req = urllib.request.Request(
        "https://api.replicate.com/v1/models/bytedance/seedance-2.0/predictions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {RT}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["id"]

def poll_scene(pred_id):
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/predictions/{pred_id}",
        headers={"Authorization": f"Bearer {RT}"}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# 1. Submit all at once
scene_ids = {name: submit_scene(prompt, img_url) for name, prompt, img_url in scene_list}

# 2. Poll until all done
done = set()
for _ in range(40):
    time.sleep(14)
    for name, pid in scene_ids.items():
        if name in done: continue
        d = poll_scene(pid)
        if d["status"] == "succeeded":
            url = d["output"]
            url = url if isinstance(url, str) else url[0]
            urllib.request.urlretrieve(url, f"/tmp/{name}.mp4")
            done.add(name)
        elif d["status"] == "failed":
            print(f"Failed: {name} — {d.get('error','')}")
            done.add(name)
    if len(done) == len(scene_ids):
        break
```

### Scene variety — vary camera mode each scene

| Camera mode | Works well for |
| --- | --- |
| Close-up / eye-level | Character hook, talking moments, product reveal |
| Top-down close | Overworld run, top-down map exploration |
| Top-down wide (zoomed out) | City/world overview, scale and geography — great transitional scene |
| Side-scroll | Character walking, left-right environment reveal |
| UI / screen-fill | Data dashboards, stats, rankings, tool interfaces |
| Victory / celebration | End payoff, CTA moment |

Vary the mode between consecutive scenes to avoid the "clips from the same loop" look.

**Zoomed-out world/city map scene — reusable prompt pattern:**

```
Zoomed-out [16-bit SNES RPG / top-down pixel-art] world map view. A tiny [describe character]
sprite runs along a winding road across a large colorful top-down map.
[Describe landmarks, zones, districts]. As the character runs, glowing markers pop up —
[green = opportunity / red = saturation / etc.]. Camera follows with a slow pan.
[Color palette]. Pixel sparkle trails behind the character.
```

### All-animated vs. mixed format

**Default to all-animated scenes** — more cohesive, avoids style mismatch, performs better for fast-cut short-form.

**Static cards (infographic slides)** are useful for "save this" content. If using them:

- Generate with GPT Image using `"aspect_ratio": "2:3"` (not `"9:16"` — returns 422)
- Extract a frame from one of your video scenes and pass it as `input_images` — this forces the card to match the video's palette and style
- Convert to video clip: `ffmpeg -loop 1 -i card.png -t 4 -vf "scale=720:1280..." card.mp4`
- **Do NOT show VO captions over card holds** — the card has its own text.

---

## Phase 5 — Background Music & SFX

Fire music generation in parallel with scene generation — similar duration, completely independent.

### Music audition workflow (strongly recommended)

Don't guess the vibe and bake it in. Generate 3 tracks with distinct moods, send them to the user as audio files, let them pick. This saves a full render cycle.

**Three archetypes to always offer:**

- **A: Lo-fi with momentum** — chill but purposeful. Good for educational/explainer content.
- **B: Cinematic/tense** — minimal electronic pulse. Good for "here's the move" or strategy content.
- **C: Genre-matched texture** — match the visual style. Pixel-art → chiptune. Lifestyle → acoustic. Finance → corporate electronic.

Call your music generation service with: vibe description (tempo, mood, instruments, references, what to avoid), genre tags, negative tags, instrumental=true, and length slightly longer than the video (trim in FFmpeg).

**Music energy must match visual energy:**

- Fast-cut, action, game-style scenes → upbeat, 120–160 BPM
- Talking head / demo → lo-fi, 70–90 BPM
- Emotional / narrative → ambient or score
- **Lo-fi over fast pixel-art scenes feels jarring** — slow tempo fights fast cuts

**MusicGPT-specific notes (if that's the provider):**

- **Rate limit: 1 concurrent generation.** Fire sequentially; wait for the previous track's CDN URL to return HTTP 200 before firing the next. Budget ~5–8 min for 3 tracks.
- When polling, pass BOTH `task_id` AND `conversion_id` — task_id alone triggers a clarifying question.
- CDN URLs return HTTP 403 until processing completes. Poll by attempting download and checking `filesize > 100KB`.

### Sound effects (only if the user wants them)

Generate short SFX (whoosh transitions ~0.5s, power-up/unlock ~1s) via the same service, and place them at scene-cut timestamps with `adelay` in the FFmpeg filter graph (Phase 6). Many creators prefer no SFX — music + VO is often sufficient.

---

## Phase 6 — FFmpeg Editing

### Step 1: Normalize all clips to same dimensions and framerate

```bash
# Video clip
ffmpeg -y -stream_loop -1 -i input.mp4 -t DURATION \
  -vf "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30" \
  -c:v libx264 -preset fast -crf 20 -an /tmp/clip_NAME.mp4

# Still image (card)
ffmpeg -y -loop 1 -i card.png -t DURATION \
  -vf "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30" \
  -c:v libx264 -preset fast -crf 20 -an /tmp/clip_NAME.mp4
```

### Step 2: Concatenate

```bash
# /tmp/concat.txt — one line per clip: file '/tmp/clip_scene1.mp4'
ffmpeg -y -f concat -safe 0 -i /tmp/concat.txt \
  -c:v libx264 -preset fast -crf 20 -an /tmp/combined.mp4
```

### Step 3: Apply captions (see Phase 7)

### Step 4: Final assembly — video + VO + music + SFX

```bash
ffmpeg -y \
  -i /tmp/captioned.mp4 \   # 0: video with captions baked in
  -i /tmp/vo.mp3 \          # 1: voiceover (full volume)
  -i /tmp/music.mp3 \       # 2: background music (ducked)
  -i /tmp/sfx.mp3 \         # 3: SFX (reused per cut via adelay)
  -filter_complex "
    [1:a]volume=1.0[vo];
    [2:a]volume=0.10,afade=t=in:st=0:d=1,afade=t=out:st=50:d=3,atrim=0:60[bg];
    [3:a]adelay=3000|3000,volume=0.40[sfx0];
    [3:a]adelay=8000|8000,volume=0.40[sfx1];
    [vo][bg][sfx0][sfx1]amix=inputs=4:duration=first:normalize=0[aout]
  " \
  -map 0:v -map "[aout]" \
  -c:v libx264 -preset fast -crf 20 \
  -c:a aac -b:a 192k \
  -shortest -movflags +faststart \
  /tmp/final.mp4
```

**Key flags:**

- `normalize=0` on amix — prevents loudness normalization from crushing VO when SFX fire
- `-shortest` — trims output to the shortest stream (usually the VO)
- `-movflags +faststart` — required for Reels/Shorts streaming
- Music `volume=0.10` (10%) — audible without competing with VO; 0.08–0.15 range. `volume=0.126` ≈ -18dB is a good starting point.
- To skip SFX or music, remove those inputs and reduce `amix inputs=` count

---

## Phase 7 — Captions

**Never estimate caption timing from word count.** Transcribe the VO with a timestamped transcription service (e.g. a transcribe-audio tool with line timestamps) and use real start/end times.

### Build an ASS subtitle file

**Use ASS format — NOT drawtext.** `drawtext` with `enable='between(t,…)'` is fragile and breaks with certain characters.

```python
captions = [
    # (start_seconds, end_seconds, "Line one text", "Optional line two")
    (3.0, 8.5, "First caption line", "second line if needed"),
]

ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,36,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,3,2,40,40,160,1
Style: Handle,DejaVu Sans,26,&H00AAFFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,2,9,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# Always-on handle watermark
ass += "Dialogue: 0,0:00:00.00,0:59:00.00,Handle,,0,0,0,,@BRAND_HANDLE\n"

def to_ass_time(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"

for start, end, l1, *rest in captions:
    text = l1 + (f"\\N{rest[0]}" if rest and rest[0] else "")
    ass += f"Dialogue: 0,{to_ass_time(start)},{to_ass_time(end)},Default,,0,0,0,,{text}\n"

open("/tmp/captions.ass", "w").write(ass)
```

### Burn in

```bash
ffmpeg -y -i /tmp/combined.mp4 -vf "ass=/tmp/captions.ass" \
  -c:v libx264 -preset fast -crf 20 /tmp/captioned.mp4
```

**Placement:** `Alignment: 2` = bottom-center (captions), `Alignment: 9` = top-right (handle watermark). `MarginV` controls vertical offset — increase if captions clip or sit too low.

**Rule: only show captions over animated scenes — not over static card holds.**

---

## Phase 8 — Deliver & Revise

Send the final video to the user for review. Then ask:

1. **Music volume** — too loud, too quiet, or good?
2. **Caption timing** — any lines early/late, missing, or cut off?
3. **Scene order** — anything that doesn't flow right?
4. **Handle/watermark** — visible and positioned correctly?

Offer a revision pass. Common quick fixes (each ~10–15s, no scene regeneration):

- Music volume: change the single `volume=` value, re-run Step 4
- Caption timing: adjust a Dialogue line's Start/End in the .ass file, re-burn
- Scene swap: replace one line in concat.txt, re-concat + re-assemble

---

## Phase 9 — Host & Publish (optional)

### Hosting — the video needs a public URL

Social publishing integrations (e.g. Buffer via Zapier MCP) fetch video from a URL. Local paths fail silently ("halted" errors), and auth-gated URLs (like Replicate file URLs) fail too.

**Recommended: Google Drive.** Upload via the Drive API, then make it public:

```python
# after uploading with files().create(...) → file_id
service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
public_url = f"https://drive.google.com/uc?export=download&id={file_id}"
```

Note: this requires the full `drive` scope — `drive.readonly` returns 403 on upload.

**Avoid temp file hosts** (transfer.sh, 0x0.st, file.io, catbox.moe) — unreliable or dead as of mid-2026. Use Drive, S3, or Cloudflare R2.

### Publishing via Buffer (or similar)

- Text-only posts work reliably: pass text + channel ID + organization ID.
- **Ask the user for their channel ID and organization ID on first use** (found in their Buffer/Zapier action config), then remember them for the session — they're stable.
- Video posts: pass the public URL with `attachment="video"`. If the action returns "halted", check (1) the URL is truly public, (2) the channel is authorized in the integration config.
- If no public host is available, queue the text post and advise the user to attach the video manually in the Buffer dashboard.

### Caption hook formula

One sentence, observation-led:

> "most people [do old thing]. here's how to [do the smarter thing]."

Match the user's caption style preferences (capitalization, punctuation) — ask if unknown.

### Platform specs

| Platform | Resolution | Max Duration | Format |
| --- | --- | --- | --- |
| Instagram Reels | 720×1280+ (9:16) | 90s | MP4 H264, AAC 192k |
| YouTube Shorts | 720×1280+ (9:16) | 60s | MP4 H264, AAC 192k |
| TikTok | 720×1280+ (9:16) | 60s | MP4 H264, AAC 192k |

Always use: `-movflags +faststart`, `-c:a aac -b:a 192k`, `-pix_fmt yuv420p`

---

## Reference: Confirmed Working Models (as of June 2026 — verify before use)

| Model | Replicate Path | Notes |
| --- | --- | --- |
| Seedance 2.0 | `bytedance/seedance-2.0` | ✅ Primary video model |
| Seedance 1 Lite | `bytedance/seedance-1-lite` | ⚠️ Legacy fallback only |
| GPT Image 2 | `openai/gpt-image-2` | ✅ Text→image + img2img |
| MiniMax Video-01 | `minimax/video-01` | ✅ 6s clips, image-to-video |

**Never use:** `bytedance/seedance-1-0` (404), `bytedance/seedance-2-0` (404 — use dot, not dash).

**Model selection is load-bearing.** The wrong Seedance model produces visibly lower quality the user will notice. Confirm `bytedance/seedance-2.0` before submitting scenes.

---

## Pitfalls (condensed)

- **Proactive status updates during long renders** — scene + music generation can take 5–10 min total. Send a brief update every ~2–3 minutes during polling ("3/6 scenes done, music generating").
- **Seedance `image` + `reference_audios` are mutually exclusive** (E006).
- **GPT Image `"9:16"` → HTTP 422** — use `"2:3"` and scale to 720×1280 in FFmpeg.
- **Replicate file upload: multipart only** — base64 and `--data-binary` both fail.
- **Prefer direct REST calls (`urllib.request`/`curl`) to Replicate** over routing through generic webhook actions (e.g. Zapier webhooks) — webhook intermediaries often can't serialize the nested `{"input": {...}}` JSON Replicate requires.
- **TTS URLs expire** — download immediately.
- **drawtext timed captions break** — always use ASS subtitles.
- **Never estimate caption timing** — transcribe the VO for real timestamps.
- **Music energy mismatch** — match BPM to edit pace; audition tracks with the user before baking in.
- **Avatar img2img skin tone drift** — pass the original as `input_images` AND state explicitly what the skin tone is NOT.
- **Static card style mismatch** — pass a video-scene frame as `input_images` to keep cards on-palette, or go all-animated.
- **`normalize=0` on amix** — without it, loudness normalization crushes the VO.
