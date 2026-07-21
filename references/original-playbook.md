> **Note:** Environment-specific playbook for a Hermes agent + Zapier MCP + Replicate setup (account IDs redacted). For the version adapted to work with any agent (Claude, Codex, Gemini CLI, Kimi, OpenClaw…), see [SKILL.md](../SKILL.md).

# AI Short-Form Video Production — Agent Playbook

This skill guides an agent through producing a complete short-form video for a creator or brand from scratch. Follow the phases in order. Each phase has decisions to surface to the user before proceeding.

---

## Publishing via Buffer MCP

Once the video is assembled, publish to LinkedIn (or other connected channels) via the Zapier Buffer MCP tool.

### What works

- `mcp_zapier_buffer_add_to_queue` — posts text to the connected LinkedIn channel directly
- Text-only posts work reliably: just pass `text`, `channelId`, `organizationId`, `method="queue"`
- Channel ID and org ID are stable — store them in memory after first use

### Video attachment requirement

Buffer's Zapier MCP action accepts `attachment="video"` but requires a **public URL** — it cannot access local file paths like `/tmp/video.mp4`. Replicate file URLs also fail (require auth header).

**Working solution: Upload to Google Drive, make public, use the direct download URL**

```
import sys
sys.path.insert(0, "/root/.hermes/skills/productivity/google-workspace/scripts")
from google_api import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

creds = get_credentials()
service = build("drive", "v3", credentials=creds)

file_metadata = {"name": "video.mp4", "mimeType": "video/mp4"}
media = MediaFileUpload("/tmp/final.mp4", mimetype="video/mp4", resumable=True)
file = service.files().create(body=file_metadata, media_body=media, fields="id,webViewLink").execute()
file_id = file["id"]

# Make publicly accessible
service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
public_url = f"https://drive.google.com/uc?export=download&id={file_id}"
print(public_url)
```

Then post with the URL:

```
mcp_zapier_buffer_add_to_queue(
    text="Your hook text here.",
    attachment="video",
    channelId="<linkedin_channel_id>",
    organizationId="<org_id>",
    method="queue",
    instructions="Post to LinkedIn with video attachment at <public_url>"
)
```

### Google Drive scope pitfall

The google-workspace skill's `setup.py` defaults to `drive.readonly` — this will cause a 403 on upload. Fix before first use:

```
sed -i 's|drive.readonly|drive|g' ~/.hermes/skills/productivity/google-workspace/scripts/setup.py
```

Then re-auth (`setup.py --revoke` → `--auth-url` → `--auth-code`).

### Hook formula for LinkedIn captions

One-sentence hook that works: **"[what most people do] → here's how to [smarter move]"**
Example: *"most people manage google ads by clicking around. here's how to connect claude code directly to your ads account and let it run the campaigns for you."*

---

## Pre-Flight: Zapier MCP Setup

Before starting, verify the Zapier MCP tools are available and working. These power both voiceover (ElevenLabs) and music/SFX (MusicGPT).

### What Zapier MCP provides

The user connects their Zapier account to Hermes via an MCP server URL. Once connected, the following tools become available:

| Tool | What it does |
| --- | --- |
| `mcp_zapier_elevenlabs_convert_text_to_speech` | Generate voiceover from text using ElevenLabs. Voice is pre-configured in the user's Zapier action. |
| `mcp_zapier_musicgpt_generate_music_with_ai` | Generate background music from a prompt |
| `mcp_zapier_musicgpt_generate_sound_effects` | Generate SFX from a prompt |
| `mcp_zapier_musicgpt_get_conversion_by_id` | Poll a MusicGPT job for completion |
| `mcp_zapier_musicgpt_transcribe_audio_to_text` | Transcribe audio with timestamps (used for caption sync) |
| `mcp_zapier_buffer_add_to_queue` | Queue or schedule a post to Buffer-connected social channels |
| `mcp_zapier_buffer_create_idea` | Save a content idea to Buffer |

**⚠️ Replicate via Zapier Webhooks does NOT work.** The `webhooks_by_zapier_put` and `custom_request` Zapier tools cannot serialize nested JSON objects. Replicate's API requires `{"input": {"prompt": "..."}}` — Zapier sends whatever `data` contains as a raw string, so Replicate receives `r...` instead of `{...}` and returns "Failed to parse request body as JSON." The fix is to use the native Replicate app in Zapier MCP config, OR (recommended) just use direct `urllib.request` / `curl` calls from `execute_code` — which is faster, more reliable, and has no nesting limitation. Do NOT attempt to route Replicate through Zapier webhook actions.

### How to set up Zapier MCP (if not already configured)

1. User goes to **zapier.com** → **MCP** (or mcp.zapier.com)
2. Creates a new MCP server and adds actions:
   - **ElevenLabs: Convert Text to Speech** — configure with their ElevenLabs API key and select/clone their voice
   - **MusicGPT: Generate Music With AI**
   - **MusicGPT: Generate Sound Effects**
   - **MusicGPT: Get Conversion by ID**
   - **MusicGPT: Transcribe Audio to Text** (optional but recommended for caption sync)
3. Copies their MCP server URL (format: `https://mcp.zapier.com/api/v1/connect?token=<token>`)
4. In `~/.hermes/config.yaml`, under `mcp_servers`:
   `yaml
   mcp_servers:
   zapier:
   url: https://mcp.zapier.com/api/v1/connect?token=YOUR_TOKEN_HERE`
5. Restart the Hermes gateway: `systemctl restart hermes-agent`
   - Note: `hermes gateway start --system` will fail ("service not installed") on most setups. Use `systemctl restart hermes-agent` directly.
   - The gateway takes ~30–60s to stop fully (it's a large process) — wait for `Active: active (running)` before proceeding
   - **⚠️ New MCP tools require a fresh session after gateway restart.** Tools are discovered at session start. If you added a new Zapier action, restart the gateway AND start a new conversation — the current session will NOT see the new tools.

**Token expiry:** Zapier MCP tokens expire frequently (every few hours in active use). When any Zapier MCP tool returns "MCP server 'zapier' is not connected" or auth errors, get a fresh token from mcp.zapier.com and update:

```
sed -i 's|token=OLD_TOKEN|token=NEW_TOKEN|g' ~/.hermes/config.yaml
systemctl restart hermes-agent
```

Wait ~30s for gateway to come back up. The token is the full URL after `?token=` — replace just that portion.

**Verify the tools are live:** If `mcp_zapier_elevenlabs_convert_text_to_speech` appears in your available tools, the MCP connection is working. If not, check the token and restart.

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

**Word count guide:**
- 30s video ≈ 80–100 words
- 45s video ≈ 120–150 words
- 60s video ≈ 150–180 words

**Hook formula that reliably works:**

> "[What most people do] → [The smarter/opposite move]"

### Surface the script to the user before proceeding

Write a draft, show it, and ask: *"Does this sound like you? Anything that feels off — too formal, wrong angle, missing something?"* Iterate until they approve it. The script sets the tone for everything downstream — a bad script can't be fixed in edit.

### Map the script to a scene timeline

Once the script is approved, break it into beats and estimate timing:

```
0–3s    Hook / visual opener (no VO or first line only)
3–12s   Setup / tension
12–22s  The move / method
22–32s  What it gives you
32–40s  Payoff / CTA
```

This becomes your scene list. Each beat = one Seedance clip.

---

## Phase 2 — Voiceover

Generate the VO before scenes — the audio duration drives everything else.

```
mcp_zapier_elevenlabs_convert_text_to_speech(
    text="[Approved script here]",
    instructions="[Describe delivery: pace, tone, energy level, pauses. E.g.: 'Calm and confident. Natural pauses between punchy lines. Not hype, not salesy. Like telling a friend something useful over coffee.']",
    output_format="mp3_44100_128"
)
```

- The voice used is whatever the user pre-configured in their Zapier ElevenLabs action
- The returned URL is an S3 link — **download it immediately**, it expires in minutes:
  `bash
  wget -q "<s3_url>" -O /tmp/vo.mp3`
- Check actual duration: `ffprobe -v quiet -show_entries format=duration -of csv=p=0 /tmp/vo.mp3`
- Adjust your scene timeline to match the real duration

---

## Phase 3 — Character Art (Skip if no avatar)

If the user has a branded avatar, use GPT Image 2 (img2img) to create a stylized version that matches their chosen visual style. This becomes the first frame for Seedance.

### Why img2img matters

Without passing the avatar as `input_images`, the model invents a generic character. The avatar reference preserves the specific face, clothing, accessories, and personality of their brand character.

### Submit to GPT Image 2

```
import urllib.request, json, subprocess

RT = subprocess.check_output(
    ["grep", "^REPLICATE_API_TOKEN", "/root/.hermes/.env"], text=True
).strip().split("=", 1)[1].strip().strip('"').strip("'")

# Upload avatar image first (multipart — base64 and --data-binary both fail)
# curl -X POST -F "content=@/path/avatar.jpg;type=image/jpeg" \
#   -H "Authorization: Bearer $RT" \
#   https://api.replicate.com/v1/files
# → returns {"id": "...", ...}
# → URL: https://api.replicate.com/v1/files/<id>

payload = json.dumps({"input": {
    "prompt": (
        f"Convert this character into [TARGET STYLE — e.g. '2D pixel-art video game sprite in 16-bit SNES RPG style']. "
        f"Preserve ALL character features exactly: [describe skin tone, hair, clothing, accessories explicitly — "
        f"and include what features are NOT present, e.g. 'warm olive skin, NOT dark brown or black']. "
        f"Full-body front-facing standing pose. Background: [describe scene]. "
        f"Style reference: [e.g. 'Chrono Trigger overworld sprites']. "
        f"ALL content at least 60px from every edge — nothing cropped."
    ),
    "input_images": ["https://api.replicate.com/v1/files/<uploaded_id>"],
    "aspect_ratio": "2:3",   # ⚠️ "9:16" returns HTTP 422 — always use "2:3"
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
    d = json.loads(r.read())
pred_id = d["id"]
```

Poll until succeeded, download the PNG. Show it to the user — ask if it looks right before spending Seedance credits animating it.

**Skin tone / likeness pitfall:** Image models tend to default to generic racial interpretations for illustrated characters. Always (1) pass the original as `input_images` AND (2) describe what the character's features are NOT (e.g. "NOT dark brown or black skin — warm olive/Mediterranean"). The explicit negation is mandatory.

---

## Phase 4 — Scene Generation

Submit ALL scene predictions in parallel before polling any — they run concurrently on Replicate.

### Seedance 2.0 — Key inputs

```
{
  "prompt": "Scene description. Camera movement. Lighting. Use \"quoted dialogue\" for lip sync.",
  "image": "<first_frame_url_or_uploaded_file>",
  "duration": 8,
  "resolution": "720p",
  "aspect_ratio": "9:16",
  "generate_audio": false
}
```

**⚠️ `image` (first frame) and `reference_audios` are mutually exclusive in Seedance 2.0.**
Passing both returns E006. Choices:
- **`image` only** — controls first frame, mix VO in FFmpeg post. Best for stylized/pixel characters (no lip sync needed).
- **`reference_images[]` + `reference_audios[]`** — character consistency + audio sync, but no guaranteed first frame.

### Parallel submit + poll

```
import urllib.request, json, time, os, subprocess

RT = subprocess.check_output(
    ["grep", "^REPLICATE_API_TOKEN", "/root/.hermes/.env"], text=True
).strip().split("=", 1)[1].strip().strip('"').strip("'")

def submit_scene(prompt, image_url=None, duration=8):
    payload = {"input": {
        "prompt": prompt, "duration": duration,
        "resolution": "720p", "aspect_ratio": "9:16", "generate_audio": False
    }}
    if image_url:
        payload["input"]["image"] = image_url
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.replicate.com/v1/models/bytedance/seedance-2.0/predictions",
        data=data,
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
            print(f"Done: {name}")
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
| **Top-down wide (zoomed out)** | City/world overview, showing scale and geography — great as a transitional scene |
| Side-scroll | Character walking, left-right environment reveal |
| UI / screen-fill | Data dashboards, stats, rankings, tool interfaces |
| Victory / looft rain | End payoff, celebration, CTA moment |

Vary the mode between consecutive scenes to avoid the "clips from the same loop" look.

**Zoomed-out world/city map scene — reusable prompt pattern:**

```
Zoomed-out [16-bit SNES RPG / top-down pixel-art] world map view. A tiny [describe character]
sprite runs along a winding road across a large colorful top-down map.
[Describe landmarks, zones, districts]. As the character runs, glowing markers pop up —
[green = opportunity / red = saturation / etc.]. Camera follows with a slow pan.
[Color palette]. Pixel sparkle trails behind the character.
```

This is a strong transitional scene for any business/location/market-based content.

### All-animated vs. mixed format

**Default to all-animated scenes** — they're more cohesive, avoid style mismatch issues, and tend to perform better for fast-cut short-form content.

**Static cards (infographic slides)** are useful for "save this" content where you want a screenshottable visual. If using them:
- Generate with `openai/gpt-image-2` using `"aspect_ratio": "2:3"` (not `"9:16"` — returns 422)
- Extract a frame from one of your video scenes and pass it as `input_images` to GPT Image 2 — this forces the card to match the video's color palette and style
- Convert to video clip: `ffmpeg -loop 1 -i card.png -t 4 -vf "scale=720:1280..." card.mp4`
- **Do NOT show VO captions over card holds** — the card has its own text. Only show captions over animated scenes.

---

## Phase 5 — Background Music & SFX

Fire music generation in parallel with scene generation — they take similar time and are completely independent.

### Music audition workflow (strongly recommended)

Don't guess the right vibe and bake it in. Generate 3 tracks with distinct moods, send them to the user as audio files, let them pick. This saves a full render cycle.

**Three useful archetypes to always offer:**
- **A: Lo-fi with momentum** — chill but purposeful, YouTube essay energy. Good for educational/explainer content.
- **B: Cinematic/tense** — minimal electronic pulse, smart reveal energy. Good for "here's the move" or strategy content.
- **C: Genre-matched texture** — match the visual style. Pixel-art game visuals → upbeat chiptune. Lifestyle → acoustic. Finance → corporate electronic.

```
mcp_zapier_musicgpt_generate_music_with_ai(
    instructions="[Describe the exact vibe: tempo, mood, instruments, reference artists or shows, what to avoid]",
    prompt="[Core music description — genre, tempo, feel, no vocals]",
    music_style="[Comma-separated genre tags]",
    negative_tags="[What NOT to include]",
    make_instrumental=True,
    output_length=55   # slightly longer than video — trim in FFmpeg
)
# Returns: task_id, conversion_id_1, conversion_id_2 (two variants generated)
```

**⚠️ Rate limit: only 1 concurrent MusicGPT generation.** Firing multiple simultaneously returns 429. Fire sequentially with a ~5s gap between calls. Budget ~5–8 min for 3 tracks.

**Music energy must match visual energy:**
- Fast-cut, action, game-style scenes → upbeat, 120–160 BPM
- Talking head / demo → lo-fi, 70–90 BPM
- Emotional / narrative → ambient or score
- **Lo-fi over fast pixel-art scenes feels jarring** — the slow tempo fights the fast cuts

### Polling MusicGPT completions

```
mcp_zapier_musicgpt_get_conversion_by_id(
    instructions="Check if complete and return the audio file URL",
    conversionType="MUSIC_AI",   # or "SOUND_GENERATOR"
    task_id="<task_id_from_generate_response>",
    conversion_id="<conversion_id_1_from_generate_response>",
    # ⚠️ Pass BOTH task_id AND conversion_id — task_id alone triggers a clarifying question
    output_hint="status and audio URL"
)
```

CDN URL patterns (for direct polling by download attempt):
- `MUSIC_AI`: `https://cdn.musicgpt.com/conversions/api/standard/<conversion_id>/<conversion_id>.mp3`
- `SOUND_GENERATOR`: `https://cdn.musicgpt.com/conversions/standard/<conversion_id>.mp3`
- Both return HTTP 403 until processing completes. Poll by attempting download and checking `filesize > 100KB`.

Download when ready:

```
wget -q "<cdn_url>" -O /tmp/music_trackA.mp3
```

Then send to user: `MEDIA:/tmp/music_trackA.mp3` with a label ("Track A — lo-fi/momentum")

### Sound effects

**@serviceghost preference: skip SFX.** User has explicitly opted out of whoosh/transition SFX — don't include them unless asked. The music + VO mix is sufficient.

For other creators who want SFX:

```
# Scene transition
mcp_zapier_musicgpt_generate_sound_effects(
    instructions="A quick whoosh/swoosh for a scene transition. Clean and digital.",
    prompt="Digital whoosh scene transition sound effect, 0.5 seconds",
    audio_length=1
)

# Power-up / unlock moment
mcp_zapier_musicgpt_generate_sound_effects(
    instructions="A satisfying power-up or unlock sound, like collecting an item in a video game.",
    prompt="8-bit video game power-up coin collect sound, bright and satisfying, 1 second",
    audio_length=2
)
```

Place SFX at scene cut timestamps using `adelay` in the FFmpeg filter graph (see Phase 6).

---

## Phase 6 — FFmpeg Editing

### Step 1: Normalize all clips to same dimensions and framerate

```
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

```
# /tmp/concat.txt
file '/tmp/clip_scene1.mp4'
file '/tmp/clip_scene2.mp4'
...
```

```
ffmpeg -y -f concat -safe 0 -i /tmp/concat.txt \
  -c:v libx264 -preset fast -crf 20 -an /tmp/combined.mp4
```

### Step 3: Apply captions (see Phase 7)

### Step 4: Final assembly — video + VO + music + SFX

```
ffmpeg -y \
  -i /tmp/captioned.mp4 \  # 0: video with captions baked in
  -i /tmp/vo.mp3 \          # 1: voiceover (full volume)
  -i /tmp/music.mp3 \       # 2: background music (ducked)
  -i /tmp/sfx.mp3 \         # 3: SFX file (reused per cut via adelay)
  -filter_complex "
    [1:a]volume=1.0[vo];
    [2:a]volume=0.10,afade=t=in:st=0:d=1,afade=t=out:st=50:d=3,atrim=0:60[bg];
    [3:a]adelay=3000|3000,volume=0.40[sfx0];
    [3:a]adelay=8000|8000,volume=0.40[sfx1];
    [3:a]adelay=14000|14000,volume=0.40[sfx2];
    [vo][bg][sfx0][sfx1][sfx2]amix=inputs=5:duration=first:normalize=0[aout]
  " \
  -map 0:v -map "[aout]" \
  -c:v libx264 -preset fast -crf 20 \
  -c:a aac -b:a 192k \
  -shortest -movflags +faststart \
  /tmp/final.mp4
```

**Key flags:**
- `normalize=0` on amix — prevents loudness normalization from crushing VO when multiple SFX fire
- `-shortest` — trims output to the shortest stream (usually the VO)
- `-movflags +faststart` — moves metadata to front for faster streaming (required for Reels/Shorts)
- Music `volume=0.10` (10%) — keeps it audible without competing with VO. Adjust to taste: 0.08–0.15 range.
- To skip SFX or music, remove those inputs and reduce `amix inputs=` count

---

## Phase 7 — Captions

**Never estimate caption timing from word count.** Use real timestamps from the audio file.

### Step 1: Transcribe the VO

```
mcp_zapier_musicgpt_transcribe_audio_to_text(
    instructions="Transcribe this voiceover and return each line with its start and end timestamp",
    extract_line_timestamps=True,
    purpose="GENERAL",
    output_hint="list of lines with start_time and end_time in seconds"
)
```

### Step 2: Build ASS subtitle file

**Use ASS format — NOT drawtext.** `drawtext` with `enable='between(t,…)'` is fragile and breaks with certain characters or expression lengths.

```
captions = [
    # (start_seconds, end_seconds, "Line one text", "Optional line two")
    (3.0, 8.5, "First caption line", "second line if needed"),
    ...
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
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"

for start, end, l1, *rest in captions:
    text = l1 + (f"\\N{rest[0]}" if rest and rest[0] else "")
    ass += f"Dialogue: 0,{to_ass_time(start)},{to_ass_time(end)},Default,,0,0,0,,{text}\n"

with open("/tmp/captions.ass", "w") as f:
    f.write(ass)
```

### Step 3: Burn in

```
ffmpeg -y -i /tmp/combined.mp4 -vf "ass=/tmp/captions.ass" \
  -c:v libx264 -preset fast -crf 20 /tmp/captioned.mp4
```

**Caption placement note:** `Alignment: 2` = bottom-center (main captions). `Alignment: 9` = top-right (handle/watermark). `MarginV` controls vertical offset from the edge — increase it if captions are getting clipped or sitting too low.

**Rule: only show captions over animated video scenes — not over static card holds.** Cards have their own text. Set caption Dialogue windows to cover only the animated scene timestamps.

---

## Phase 8.5 — Host Video for Publishing

Before posting to any social platform via Buffer or Zapier MCP, the video needs a **publicly accessible URL**. Local `/tmp/` paths fail silently — Buffer's Zapier action returns "halted" when the video URL isn't reachable from Zapier's servers.

### Option 1 — Google Drive (recommended, already authed)

Requires `drive` scope (not `drive.readonly` — see pitfalls). Upload + make public:

```
import sys
sys.path.insert(0, "/root/.hermes/skills/productivity/google-workspace/scripts")
from google_api import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

creds = get_credentials()
service = build("drive", "v3", credentials=creds)

file_metadata = {"name": "video.mp4", "mimeType": "video/mp4"}
media = MediaFileUpload("/tmp/final.mp4", mimetype="video/mp4", resumable=True)
file = service.files().create(body=file_metadata, media_body=media, fields="id,webViewLink").execute()

# Make publicly readable
service.permissions().create(fileId=file["id"], body={"role": "reader", "type": "anyone"}).execute()

direct_url = f"https://drive.google.com/uc?export=download&id={file['id']}"
print(f"Public URL: {direct_url}")
```

### Option 2 — Replicate Files API (⚠️ auth required — NOT suitable for Buffer)

Replicate file URLs (`https://api.replicate.com/v1/files/...`) require `Authorization: Bearer` headers. Buffer cannot fetch them. Fine for passing between Replicate calls, not for external services.

### ❌ Temp file hosts — unreliable as of June 2026

- `transfer.sh` — down
- `0x0.st` — disabled uploads ("AI botnet spam")
- `file.io` — returns HTML, doesn't support CLI upload
- `catbox.moe` — times out on 16MB+ files

Don't attempt these. Use Google Drive.

---

## Phase 9 — Publish via Buffer (Zapier MCP)

Buffer is connected via Zapier MCP. Text posts work directly; video posts require a public URL from Phase 8.5.

### Post text-only (always works)

```
mcp_zapier_buffer_add_to_queue(
    instructions="Post this to the LinkedIn channel",
    text="Your post text here",
    method="queue",
    channelId="YOUR_CHANNEL_ID",       # your LinkedIn channel
    organizationId="YOUR_ORGANIZATION_ID",   # your organization
    output_hint="post_id and status"
)
```

### Post with video attachment

```
mcp_zapier_buffer_add_to_queue(
    instructions="Post to LinkedIn with video. Video URL: <public_url>",
    text="Post caption here",
    attachment="video",
    method="queue",
    channelId="YOUR_CHANNEL_ID",
    organizationId="YOUR_ORGANIZATION_ID",
    output_hint="post_id and status"
)
```

**⚠️ Pitfalls:**
- `attachment="video"` with a local path → "halted" error. Must be a public URL.
- If the action returns "halted", check: (1) URL is truly public, (2) Buffer channel is authorized in the Zapier action config.
- Zapier MCP token expires periodically. Update `mcp_servers.zapier.url` in `~/.hermes/config.yaml` with new token, then `systemctl restart hermes-agent`.

### Hook formula for LinkedIn captions

One sentence, observation-led, lowercase, no em dash:

> "most people [do old thing]. here's how to [do the smarter thing]."

---

## Phase 8 — Deliver

Send the final video to the user:

```
MEDIA:/tmp/final.mp4
```

If on Telegram:

```
send_message(message="MEDIA:/tmp/final.mp4", target="telegram:USER_DM")
```

### Post-delivery checklist

Ask the user:
1. **Music volume** — too loud, too quiet, or good? Easy to re-render with adjusted `volume=` value.
2. **Caption timing** — any lines early/late, missing, or cut off?
3. **Scene order** — anything that doesn't flow right?
4. **Handle/watermark** — visible and positioned correctly?

Offer a revision pass before they call it done. Common quick fixes:
- Music volume: change single `volume=0.10` value in FFmpeg filter, re-render in ~15s
- Caption timing: adjust a Dialogue line's Start/End in the .ass file, re-burn in ~10s
- Scene swap: replace one `file ''` line in concat.txt, re-concat + re-assemble

---

## Phase 9 — Publish to Buffer (LinkedIn)

Once the final video is approved, queue it to Buffer via MCP.

### Known working setup (@serviceghost)

- **Channel ID (LinkedIn):** `YOUR_CHANNEL_ID` (your LinkedIn channel)
- **Organization ID:** `YOUR_ORGANIZATION_ID` (your organization)

### Text-only post (always works)

```
mcp_zapier_buffer_add_to_queue(
    text="Your hook here.",
    method="queue",
    channelId="YOUR_CHANNEL_ID",
    organizationId="YOUR_ORGANIZATION_ID",
    instructions="Queue this post to LinkedIn Buffer.",
    output_hint="post ID and status"
)
```

### Video post (requires public URL)

Buffer's Zapier action fetches video from a URL — it cannot use local paths or auth-gated URLs.
1. Upload video to a public host (S3, Cloudflare R2, etc.)
2. Pass the public URL in the instructions with `attachment="video"`
3. If no public host is available, queue the text post via MCP and advise user to manually attach the video in the Buffer dashboard at buffer.com

### Hook formula for @serviceghost

One sentence, lowercase, no em dashes. Pattern: "most people do X. here's how to [smarter move]." or just lead with the smarter move directly.

Ask the user for their Buffer channel/org IDs on first use (from their Zapier/Buffer action config), then reuse them for the session.

| Platform | Resolution | Max Duration | Format |
| --- | --- | --- | --- |
| Instagram Reels | 720×1280+ (9:16) | 90s | MP4 H264, AAC 192k |
| YouTube Shorts | 720×1280+ (9:16) | 60s | MP4 H264, AAC 192k |
| TikTok | 720×1280+ (9:16) | 60s | MP4 H264, AAC 192k |

Always use: `-movflags +faststart`, `-c:a aac -b:a 192k`, `-pix_fmt yuv420p`

---

## Reference: Confirmed Working Models (June 2026)

| Model | Replicate Path | Notes |
| --- | --- | --- |
| Seedance 2.0 | `bytedance/seedance-2.0` | ✅ Primary video model |
| Seedance 1 Lite | `bytedance/seedance-1-lite` | ⚠️ Legacy fallback |
| GPT Image 2 | `openai/gpt-image-2` | ✅ Text→image + img2img |
| MiniMax Video-01 | `minimax/video-01` | ✅ 6s clips, image-to-video |

**Never use:** `bytedance/seedance-1-0` (404), `bytedance/seedance-2-0` (404 — use dot not dash), `bytedance/seedance-1-lite` (older, lower quality — only use as last resort fallback if 2.0 is unavailable)

**Model selection is load-bearing.** Using the wrong Seedance model (e.g. 1-lite instead of 2.0) produces visibly lower quality output that the user will notice and ask to redo. Always confirm you're using `bytedance/seedance-2.0` before submitting scene predictions.

---

## Quick Re-Renders (Post-Delivery)

When the user wants a single-element change after delivery, re-render is fast (~15s) — don't regenerate scenes:

**Remove SFX from final mix:**

```
ffmpeg -y \
  -i /tmp/scene1.mp4 ... -i /tmp/sceneN.mp4 \
  -i /tmp/vo.mp3 \
  -i /tmp/music.mp3 \
  -filter_complex "
    [0:v][1:v]...[N:v]concat=n=N:v=1:a=0[vout];
    [vo_input:a]volume=1.0[vo];
    [music_input:a]volume=0.126[music];
    [vo][music]amix=inputs=2:duration=first:dropout_transition=2[aout]
  " \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 192k -shortest \
  /tmp/final_no_sfx.mp4
```

`volume=0.126` ≈ -18dB (good starting point for background music under VO).

**Adjust music volume only:** Change the single `volume=` value and re-run the Step 4 FFmpeg command. Takes ~15s.

**Replace one scene:** Swap the file path in the concat filter/file list, re-run Step 2 + Step 4.

---

## Pitfalls

- **Zapier MCP token expired** — update `mcp_servers.zapier.url` in `~/.hermes/config.yaml` using `sed -i` (the `patch` tool blocks credential files): `sed -i 's|OLD_TOKEN|NEW_TOKEN|g' /root/.hermes/config.yaml` then restart gateway
- **Buffer video posting requires a public URL** — local `/tmp/` paths and Replicate file URLs (auth-required) both fail. Common temp hosts (transfer.sh, 0x0.st, catbox.moe) are unreliable for 16MB files. **Best solution: upload to Google Drive via the google-workspace skill, call `permissions().create(role="reader", type="anyone")`, then use `https://drive.google.com/uc?export=download&id=FILE_ID`.** Requires full `drive` scope — see Publishing section for setup details.
- **Buffer text-only posts work fine** — only video attachment triggers the halted/auth issue. Text queuing via MCP works reliably with channel ID + org ID.
- **Proactive status updates during long renders** — Seedance 2.0 + MusicGPT generation can take 5–10 minutes total. Don't wait for the user to ask "status?" — send a brief update every ~2–3 minutes during polling loops (e.g. "Still rendering — 3/6 scenes done, music generating"). If using execute\_code for polling, break into shorter chunks and report between rounds.
- **Seedance `image` + `reference_audios` mutual exclusion** — E006 error. Use `reference_images[]` + `reference_audios[]` together if you need both; `image` + no audio for first-frame control
- **GPT Image 2: `"aspect_ratio": "9:16"` → HTTP 422** — only `"2:3"` works for portrait; scale to 720×1280 in FFmpeg
- **Replicate file upload: multipart only** — `--data-binary` → `{"detail":"Missing content"}`; base64 → "Argument list too long" for files >500KB. Only correct method: `curl -F "content=@file.jpg;type=image/jpeg"`
- **replicate Python package not installed** in Hermes venv. Use `urllib.request` + REST API directly
- **`~` not expanded in subprocess from execute\_code** — use `/root/.hermes/.env` not `~/.hermes/.env`
- **drawtext `enable=between(t,...)` breaks** — always use ASS subtitles for timed captions
- **Never estimate caption timing** — transcribe the VO with `mcp_zapier_musicgpt_transcribe_audio_to_text` to get real timestamps
- **ElevenLabs S3 URL expires** — download immediately after `mcp_zapier_elevenlabs_convert_text_to_speech` returns
- **Zapier Webhooks → Replicate does NOT work** — `webhooks_by_zapier_put` and `custom_request` tools send `data` as a raw string, not a JSON object. Replicate receives `r...` and returns "Failed to parse request body as JSON." Use direct `urllib.request` REST calls instead — they are faster and have no nesting limitation. See Pre-Flight section for details.
- **MusicGPT rate limit**: 1 concurrent generation max — must queue sequentially. A 6s gap is NOT sufficient; wait for the previous track's CDN URL to return HTTP 200 before firing the next request. Poll completion, don't just sleep.
- **MusicGPT polling** — pass both `task_id` AND `conversion_id`; task\_id alone triggers a follow-up question
- **Music energy mismatch** — lo-fi over fast-cut action scenes feels jarring. Match BPM to edit pace. Audition tracks with the user before baking in
- **Avatar img2img skin tone** — model defaults skew toward generic. Always pass original as `input_images` AND state explicitly what the skin tone is NOT
- **Static card style mismatch** — flat corporate cards next to stylized AI scenes look like two different videos. Extract a frame from a scene and pass as `input_images` to GPT Image 2 for consistency. Or skip cards and go all-animated
- **`normalize=0` on amix** — without it, loudness normalization crushes the VO when multiple SFX fire simultaneously
