import unittest

from nodes.client import build_chat_payload, extract_chat_result, normalize_messages


class ChatClientTests(unittest.TestCase):
    def test_extracts_modern_chat_response(self):
        reply, reasoning, usage = extract_chat_result({
            "choices": [{
                "message": {
                    "content": "Hello",
                    "reasoning": "Checked context",
                }
            }],
            "usage": {"total_tokens": 12},
        })
        self.assertEqual(reply, "Hello")
        self.assertEqual(reasoning, "Checked context")
        self.assertEqual(usage["total_tokens"], 12)

    def test_extracts_legacy_response(self):
        reply, reasoning, usage = extract_chat_result({
            "choices": [{"text": "Legacy"}],
        })
        self.assertEqual(reply, "Legacy")
        self.assertEqual(reasoning, "")
        self.assertEqual(usage, {})

    def test_normalizes_json_messages(self):
        messages = normalize_messages('[{"role":"user","content":"Hi"}]')
        self.assertEqual(messages[0]["content"], "Hi")

    def test_builds_system_and_reasoning(self):
        payload = build_chat_payload(
            "model",
            [{"role": "user", "content": "Hi"}],
            system_prompt="Be concise",
            reasoning_effort="high",
        )
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["reasoning_effort"], "high")


if __name__ == "__main__":
    unittest.main()
