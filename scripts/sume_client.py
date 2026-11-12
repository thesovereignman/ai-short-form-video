#!/usr/bin/env python3
"""Server-side Sume client and CLI; standard library only, Python 3.10+.

owner_id MUST come from an authenticated server session. The CLI is a trusted
operator tool, not a multi-user authentication boundary. Never expose it directly
to a browser. No automatic paid retries; reuse the same operation_id on recovery.
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE_URL = "https://api.sume.com"
TERMINAL = {"completed", "failed", "canceled"}
MODEL_MAP = {
    "bytedance/seedance-2.0": "seedance-2",
    "openai/gpt-image-2": "gpt-image-2",
}


class SumeError(RuntimeError):
    pass


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward credentials to another origin.


def load_local_env(path=".env"):
    """Read only known names; never execute shell syntax or interpolate secrets."""
    file = Path(path)
    if not file.exists():
        return
    allowed = {"SUME_API_KEY", "VIDEO_GENERATION_PROVIDER", "SUME_JOB_DB"}
    for line in file.read_text().splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name in allowed:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(name, value)


class Transport:
    def __init__(self, api_key=None):
        self.api_key = api_key if api_key is not None else os.getenv("SUME_API_KEY")
        self.opener = urllib.request.build_opener(NoRedirects())

    def __call__(self, method, path, payload=None, key=None, public=False):
        if not path.startswith("/v1/") or "?" in path or "#" in path:
            raise SumeError("Unsupported API path")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not public:
            if not self.api_key:
                raise SumeError("Set SUME_API_KEY on the server; do not paste it in chat")
            headers["Authorization"] = f"Bearer {self.api_key}"
        if key:
            headers["Idempotency-Key"] = key
        req = urllib.request.Request(BASE_URL + path, method=method, headers=headers,
                                     data=None if payload is None else json.dumps(payload).encode())
        try:
            with self.opener.open(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read()).get("error", {})
            except (ValueError, AttributeError):
                error = {}
            if not isinstance(error, dict):
                error = {}
            # Provider error text may echo inputs. Only return bounded identifiers.
            code = error.get("code", "http_error")
            rid = error.get("request_id", "unknown")
            code = code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,80}", code) else "http_error"
            rid = rid if isinstance(rid, str) and re.fullmatch(r"req_[a-zA-Z0-9]{1,80}", rid) else "unknown"
            raise SumeError(f"Sume HTTP {exc.code}: {code}; request_id={rid}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise SumeError("Sume response unavailable. Submission outcome may be unknown; retry the SAME operation_id and request") from None


def unwrap(value):
    data = value.get("data", value)
    if not isinstance(data, dict):
        raise SumeError("Unexpected Sume response")
    return data


def dollars(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise SumeError("Invalid dollar amount") from None
    if not amount.is_finite() or amount < 0:
        raise SumeError("Invalid dollar amount")
    return amount


def map_legacy(model, inputs):
    """Only exact family/version mappings. Never upgrade or discard fields silently."""
    if model not in MODEL_MAP:
        raise SumeError("No verified Sume match for this legacy model")
    if model == "bytedance/seedance-2.0":
        aliases = {"image": "image_url", "reference_images": "reference_image_urls",
                   "reference_audios": "reference_audio_urls", "reference_videos": "reference_video_urls"}
        allowed = {"prompt", "duration", "resolution", "aspect_ratio", "generate_audio", *aliases}
        defaults = {"duration": 8, "resolution": "720p", "aspect_ratio": "9:16", "generate_audio": False}
    else:
        aliases = {"input_images": "image_urls", "number_of_images": "num_images"}
        allowed = {"prompt", "aspect_ratio", "quality", "output_format", *aliases}
        defaults = {"aspect_ratio": "9:16", "quality": "high", "output_format": "png", "num_images": 1, "resolution": "1K"}
    if set(inputs) - allowed:
        raise SumeError("Unmapped input fields: " + ", ".join(sorted(set(inputs) - allowed)))
    return {"model": MODEL_MAP[model], "input": {**defaults, **{aliases.get(k, k): v for k, v in inputs.items()}}}


class SumeClient:
    def __init__(self, db_path=None, transport=None, provider=None):
        self.http = transport or Transport()
        self.provider = provider or os.getenv("VIDEO_GENERATION_PROVIDER", "legacy")
        path = Path(db_path or os.getenv("SUME_JOB_DB", ".sume/jobs.sqlite3"))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS operations (
            idempotency_key TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            request_hash TEXT NOT NULL, job_id TEXT UNIQUE, estimate_usd TEXT,
            created_at INTEGER NOT NULL)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def catalog(self):
        return unwrap(self.http("GET", "/v1/open/catalog", public=True))["models"]

    def validate(self, request):
        if set(request) != {"model", "input"} or not isinstance(request["input"], dict):
            raise SumeError("Request must contain exactly model and input")
        model = next((m for m in self.catalog() if m["id"] == request["model"]), None)
        if model is None:
            raise SumeError("Model not found in live Sume catalog")
        if model["kind"] not in {"image", "video", "lipsync", "captions"}:
            raise SumeError("This helper supports image/video/lipsync/captions only; preserve the existing audio integration")
        inputs = request["input"]
        if {"model", "mode", "webhook_url", "wait_timeout_seconds"} & inputs.keys():
            raise SumeError("The helper owns model and async queue fields")
        caps = model.get("capabilities", {})
        for field, cap in [("resolution", "resolutions"), ("aspect_ratio", "aspect_ratios"), ("quality", "qualities")]:
            if field in inputs and caps.get(cap) and inputs[field] not in caps[cap]:
                raise SumeError(f"{field} is not listed for this model; choose explicitly")
        if inputs.get("image_url") and any(inputs.get(k) for k in ["reference_image_urls", "reference_video_urls", "reference_audio_urls"]) and request["model"].startswith("seedance"):
            raise SumeError("Seedance first-frame and mixed reference modes must be separate")
        return model

    def estimate(self, request, old_usd=None):
        self.validate(request)
        data = unwrap(self.http("POST", "/v1/open/estimate", request, public=True))
        if data.get("currency") != "USD" or data.get("model") != request["model"]:
            raise SumeError("Estimate did not match the requested model and currency")
        amount = dollars(data.get("usd"))
        return {"model": request["model"], "sume_usd": str(amount),
                "previous_provider_usd": None if old_usd is None else str(dollars(old_usd))}

    def submit(self, owner_id, operation_id, request, max_usd):
        if self.provider != "sume":
            raise SumeError("Sume is disabled: opt in with VIDEO_GENERATION_PROVIDER=sume; legacy remains available")
        if not owner_id or not operation_id or len(owner_id) > 256 or len(operation_id) > 256:
            raise SumeError("Trusted owner_id and stable operation_id are required")
        cap = dollars(max_usd)
        body = json.dumps(request, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(body.encode()).hexdigest()
        key = hashlib.sha256(json.dumps([owner_id, operation_id]).encode()).hexdigest()
        # Commit intent before network I/O, so a crash/timeout can recover the same paid job.
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO operations VALUES (?, ?, ?, NULL, NULL, ?)",
                            (key, owner_id, digest, int(time.time())))
            row = self.db.execute("SELECT * FROM operations WHERE idempotency_key=?", (key,)).fetchone()
        if row["request_hash"] != digest:
            raise SumeError("operation_id already belongs to a different request; recover it before starting another")
        if row["job_id"]:
            return {"job_id": row["job_id"], "estimate_usd": row["estimate_usd"], "reused": True}
        quote = self.estimate(request)
        if dollars(quote["sume_usd"]) > cap:
            raise SumeError("Exact estimate exceeds max_usd; nothing submitted")
        model = self.validate(request)
        route = "image" if model["kind"] == "image" else "video"
        data = unwrap(self.http("POST", f"/v1/{route}-router/generate",
                               {**request["input"], "model": request["model"], "mode": "async"}, key=key))
        job_id = data.get("job", {}).get("id") or data.get("job_id")
        if not isinstance(job_id, str) or not re.fullmatch(r"job_[A-Za-z0-9_-]+", job_id):
            raise SumeError("Submission may have succeeded but returned no valid job ID; retry the SAME operation_id")
        with self.db:
            self.db.execute("UPDATE operations SET job_id=?, estimate_usd=? WHERE idempotency_key=?",
                            (job_id, quote["sume_usd"], key))
        return {"job_id": job_id, "estimate_usd": quote["sume_usd"], "reused": False}

    def owned(self, owner_id, job_id):
        if not re.fullmatch(r"job_[A-Za-z0-9_-]+", job_id):
            raise SumeError("Job not found")
        row = self.db.execute("SELECT 1 FROM operations WHERE owner_id=? AND job_id=?", (owner_id, job_id)).fetchone()
        if row is None:
            raise SumeError("Job not found")

    def status(self, owner_id, job_id):
        self.owned(owner_id, job_id)
        data = unwrap(self.http("GET", f"/v1/jobs/{job_id}/status"))
        value = data.get("sume_status") or data.get("status", "").lower()
        value = {"in_queue": "queued", "in_progress": "processing"}.get(value, value)
        if value not in TERMINAL | {"queued", "processing"}:
            raise SumeError("Unknown Sume job status")
        return {"job_id": job_id, "status": value, "result_ready": data.get("result_ready", value == "completed"),
                "next_poll_after_seconds": data.get("next_poll_after_seconds") or 2}

    def result(self, owner_id, job_id):
        status = self.status(owner_id, job_id)
        if status["status"] != "completed" or not status["result_ready"]:
            raise SumeError("Job result is not ready")
        return unwrap(self.http("GET", f"/v1/jobs/{job_id}/result")).get("result")

    def cancel(self, owner_id, job_id):
        self.owned(owner_id, job_id)
        self.http("POST", f"/v1/jobs/{job_id}/cancel", {})
        return self.status(owner_id, job_id)

    def wait(self, owner_id, job_id, seconds=50):
        deadline = time.monotonic() + min(max(seconds, 0), 55)
        while True:
            status = self.status(owner_id, job_id)
            if status["status"] in TERMINAL:
                return status
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {**status, "timed_out": True}
            time.sleep(min(max(float(status["next_poll_after_seconds"]), 1), remaining))


def main():
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["catalog", "estimate", "map", "submit", "status", "result", "cancel", "wait"])
    parser.add_argument("--request", help="JSON file containing {model, input}")
    parser.add_argument("--owner", help="Trusted operator or authenticated server user ID")
    parser.add_argument("--operation", help="Stable operation ID; reuse on timeout/retry")
    parser.add_argument("--job")
    parser.add_argument("--max-usd")
    parser.add_argument("--old-usd")
    args = parser.parse_args()
    client = None
    try:
        request = json.loads(Path(args.request).read_text()) if args.request else None
        client = SumeClient()
        if args.action in {"map", "estimate", "submit"} and request is None:
            raise SumeError("--request is required")
        if args.action == "catalog":
            output = client.catalog()
        elif args.action == "map":
            output = map_legacy(request["model"], request["input"])
        elif args.action == "estimate":
            output = client.estimate(request, args.old_usd)
        elif args.action == "submit":
            if args.max_usd is None:
                raise SumeError("--max-usd is required")
            output = client.submit(args.owner, args.operation, request, args.max_usd)
        else:
            if not args.owner or not args.job:
                raise SumeError("--owner and --job are required")
            output = getattr(client, args.action)(args.owner, args.job)
        print(json.dumps(output, indent=2))
    except (SumeError, OSError, ValueError, KeyError) as exc:
        # Do not print file contents, requests or a credential-bearing traceback.
        parser.exit(1, (str(exc) if isinstance(exc, SumeError) else "Invalid input or local state") + "\n")
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
