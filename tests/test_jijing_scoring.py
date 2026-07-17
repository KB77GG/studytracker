import unittest

from app import app


class ListeningJijingSubmissionTest(unittest.TestCase):
    def test_client_forged_score_is_ignored(self):
        client = app.test_client()
        response = client.post(
            "/api/listening/jijing/xiahuar_009_p3/submit",
            json={
                "answers": {},
                "correct": 999,
                "total": 999,
                "results": [{"q": "forged", "marks": 999, "awarded": 999, "correct": True}],
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()["result"]
        self.assertNotEqual(result["correct"], 999)
        self.assertEqual(result["correct"], 0)
        self.assertEqual(result["total"], 10)
        self.assertEqual(result["results"][0]["value"], "")


if __name__ == "__main__":
    unittest.main()
