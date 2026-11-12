import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("sume_client", Path(__file__).parents[1] / "scripts/sume_client.py")
sume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sume)

REQUEST = {"model": "seedance-2", "input": {"prompt": "A roofer working safely", "duration": 8, "resolution": "720p", "aspect_ratio": "9:16", "generate_audio": False}}


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.statuses = ["completed"]
        self.timeout_once = False
        self.submitted_keys = []

    def __call__(self, method, path, payload=None, key=None, public=False):
        self.calls.append((method, path, payload, key, public))
        if path.endswith("/catalog"):
            return {"data": {"models": [
                {"id": "seedance-2", "kind": "video", "capabilities": {"resolutions": ["720p"], "aspect_ratios": ["9:16"]}},
                {"id": "gpt-image-2", "kind": "image", "capabilities": {"aspect_ratios": ["9:16"], "resolutions": ["1K"]}}
            ]}}
        if path.endswith("/estimate"):
            return {"data": {"model": payload["model"], "currency": "USD", "usd": "1.2096"}}
        if path.endswith("/generate"):
            self.submitted_keys.append(key)
            if self.timeout_once:
                self.timeout_once = False
                raise sume.SumeError("Submission outcome unknown")
            return {"data": {"job": {"id": "job_one"}}}
        if path.endswith("/status"):
            state = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return {"data": {"sume_status": state, "result_ready": state == "completed"}}
        if path.endswith("/result"):
            return {"data": {"result": {"artifacts": [{"url": "https://media.sume.com/example.mp4"}]}}}
        if path.endswith("/cancel"):
            self.statuses = ["canceled"]
            return {"data": {}}
        raise AssertionError(path)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "jobs.sqlite3"
        self.api = FakeAPI()
        self.client = sume.SumeClient(self.db, self.api, "sume")

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def submit(self, request=None, operation="scene1"):
        return self.client.submit("owner1", operation, request or REQUEST, "2")

    def test_paid_submit_flattens_input_and_persists_job(self):
        receipt = self.submit()
        self.assertEqual(receipt["job_id"], "job_one")
        call = next(c for c in self.api.calls if c[1].endswith("/generate"))
        self.assertNotIn("input", call[2])
        self.assertEqual(call[2]["mode"], "async")
        self.assertTrue(call[3])
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)

    def test_cross_owner_reads_and_cancel_make_no_network_calls(self):
        self.submit()
        for method in [self.client.status, self.client.result, self.client.cancel, self.client.wait]:
            before = len(self.api.calls)
            with self.assertRaises(sume.SumeError):
                method("other", "job_one")
            self.assertEqual(len(self.api.calls), before)

    def test_idempotent_recovery_after_timeout_and_restart(self):
        self.api.timeout_once = True
        with self.assertRaises(sume.SumeError):
            self.submit()
        self.client.close()
        self.client = sume.SumeClient(self.db, self.api, "sume")
        self.submit()
        self.assertEqual(len(set(self.api.submitted_keys)), 1)
        before = len(self.api.calls)
        self.assertTrue(self.submit()["reused"])
        self.assertEqual(len(self.api.calls), before)

    def test_same_operation_different_input_rejected(self):
        self.submit()
        changed = json.loads(json.dumps(REQUEST))
        changed["input"]["prompt"] = "Different scene"
        with self.assertRaises(sume.SumeError):
            self.submit(changed)
        self.assertEqual(len(self.api.submitted_keys), 1)

    def test_spend_cap_and_feature_flag_prevent_paid_call(self):
        with self.assertRaises(sume.SumeError):
            self.client.submit("owner1", "cheap", REQUEST, "1")
        self.client.provider = "legacy"
        with self.assertRaises(sume.SumeError):
            self.submit()
        self.assertEqual(self.api.submitted_keys, [])

    def test_nonfinite_budget_rejected(self):
        for value in ["NaN", "Infinity", "-1"]:
            with self.assertRaises(sume.SumeError):
                self.client.submit("owner1", value, REQUEST, value)
        self.assertEqual(self.api.submitted_keys, [])

    def test_pending_and_failed_jobs_never_fetch_result(self):
        self.submit()
        for state in ["queued", "processing", "failed", "canceled"]:
            self.api.statuses = [state]
            with self.assertRaises(sume.SumeError):
                self.client.result("owner1", "job_one")
        self.assertFalse(any(c[1].endswith("/result") for c in self.api.calls))

    def test_success_fetches_result_and_cancel_reads_actual_state(self):
        self.submit()
        self.assertIn("artifacts", self.client.result("owner1", "job_one"))
        self.assertEqual(self.client.cancel("owner1", "job_one")["status"], "canceled")

    def test_wait_timeout_does_not_cancel_or_resubmit(self):
        self.submit()
        self.api.statuses = ["processing"]
        self.assertTrue(self.client.wait("owner1", "job_one", seconds=0)["timed_out"])
        self.assertEqual(len(self.api.submitted_keys), 1)
        self.assertFalse(any(c[1].endswith("/cancel") for c in self.api.calls))

    def test_exact_mapping_and_unmapped_models_fields(self):
        mapped = sume.map_legacy("bytedance/seedance-2.0", {"prompt": "Scene", "image": "https://example.com/photo.png"})
        self.assertEqual(mapped["model"], "seedance-2")
        self.assertIn("image_url", mapped["input"])
        for name in ["minimax/video-01", "bytedance/seedance-1-lite"]:
            with self.assertRaises(sume.SumeError):
                sume.map_legacy(name, {})
        with self.assertRaises(sume.SumeError):
            sume.map_legacy("openai/gpt-image-2", {"unknown": 1})

    def test_unsupported_resolution_and_image_ratio_require_choice(self):
        request = sume.map_legacy("openai/gpt-image-2", {"prompt": "portrait", "aspect_ratio": "2:3"})
        with self.assertRaises(sume.SumeError):
            self.client.estimate(request)
        request = json.loads(json.dumps(REQUEST))
        request["input"]["resolution"] = "4K"
        with self.assertRaises(sume.SumeError):
            self.client.estimate(request)

    def test_images_use_image_router(self):
        self.submit(sume.map_legacy("openai/gpt-image-2", {"prompt": "Portrait"}))
        self.assertTrue(any(c[1] == "/v1/image-router/generate" for c in self.api.calls))


if __name__ == "__main__":
    unittest.main()
