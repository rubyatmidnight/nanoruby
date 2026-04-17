import json
import unittest
from unittest.mock import patch

from nodes.video_generator import NanogptImageToVideo, build_image_to_video_payload
from nodes.video_status import NanogptVideoStatus, extract_video_url
from nodes.utils import get_video_model_profile, get_video_models, validate_video_request


class VideoNodeTests(unittest.TestCase):
    def test_curated_video_model_order(self):
        self.assertEqual(
            get_video_models(),
            [
                "wan-video-image-to-video",
                "wan-video-22-turbo",
                "wan-video-22",
                "wan-wavespeed-25",
                "wan-wavespeed-26",
            ],
        )

    def test_video_model_profile_contains_expected_limits(self):
        profile = get_video_model_profile("wan-video-image-to-video")
        self.assertEqual(profile["label"], "Wan 2.6 Image-To-Video Pro")
        self.assertEqual(profile["resolutions"], ["1080p", "2k", "4k"])
        self.assertEqual(profile["durations"], ["5s", "10s", "15s"])

    def test_build_payload_omits_auto_fields(self):
        payload = build_image_to_video_payload(
            prompt="Animate this",
            model="wan-video-image-to-video",
            duration="auto",
            aspect_ratio="auto",
            resolution="auto",
            negative_prompt="",
            seed=-1,
            image_url="https://example.com/image.png",
        )
        self.assertEqual(payload["model"], "wan-video-image-to-video")
        self.assertEqual(payload["prompt"], "Animate this")
        self.assertEqual(payload["imageUrl"], "https://example.com/image.png")
        self.assertNotIn("duration", payload)
        self.assertNotIn("aspect_ratio", payload)
        self.assertNotIn("resolution", payload)
        self.assertNotIn("seed", payload)

    def test_build_payload_prefers_data_url(self):
        payload = build_image_to_video_payload(
            prompt="Animate this",
            model="wan-video-image-to-video",
            image_url="https://example.com/image.png",
            image_data_url="data:image/png;base64,abc",
        )
        self.assertEqual(payload["imageDataUrl"], "data:image/png;base64,abc")
        self.assertNotIn("imageUrl", payload)

    def test_validate_video_request_rejects_bad_resolution(self):
        with self.assertRaisesRegex(ValueError, "supports resolutions"):
            validate_video_request("wan-wavespeed-25", "5s", "4k")

    def test_generate_video_requires_image_source(self):
        node = NanogptImageToVideo()
        with self.assertRaisesRegex(ValueError, "Provide image, image_url, or image_data_url"):
            node.generate_video(
                prompt="Animate this",
                model="wan-video-image-to-video",
                api_key="test-key",
                resolution="1080p",
            )

    def test_generate_video_passes_built_payload(self):
        node = NanogptImageToVideo()
        with patch("nodes.video_generator.nanogpt_video_generate", return_value={"runId": "vid_1", "status": "pending"}):
            run_id, model, status, metadata = node.generate_video(
                prompt="Animate this",
                model="wan-video-image-to-video",
                api_key="test-key",
                image_url="https://example.com/image.png",
                duration="5s",
                aspect_ratio="16:9",
                resolution="1080p",
                custom_model="wan-video-image-to-video",
            )
        self.assertEqual(run_id, "vid_1")
        self.assertEqual(model, "wan-video-image-to-video")
        self.assertEqual(status, "pending")
        meta = json.loads(metadata)
        self.assertEqual(meta["payload"]["imageUrl"], "https://example.com/image.png")
        self.assertEqual(meta["payload"]["model"], "wan-video-image-to-video")
        self.assertEqual(meta["model_profile"]["label"], "Wan 2.6 Image-To-Video Pro")

    def test_extract_video_url(self):
        url = extract_video_url({
            "output": {
                "video": {
                    "url": "https://example.com/video.mp4",
                }
            }
        })
        self.assertEqual(url, "https://example.com/video.mp4")

    def test_status_shortcuts_completed_initial_status(self):
        node = NanogptVideoStatus()
        result = node.check_status(
            run_id="",
            model="wan-video-image-to-video",
            api_key="",
            initial_status=json.dumps({
                "runId": "vid_2",
                "status": "COMPLETED",
                "output": {
                    "video": {
                        "url": "https://example.com/video.mp4",
                    }
                },
            }),
        )
        self.assertEqual(result[0], "vid_2")
        self.assertEqual(result[1], "wan-video-image-to-video")
        self.assertEqual(result[2], "COMPLETED")
        self.assertEqual(result[3], "https://example.com/video.mp4")


if __name__ == "__main__":
    unittest.main()
