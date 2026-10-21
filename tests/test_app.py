import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import DatePlannerHandler, IDEAS, rank_ideas


class RecommendationTests(unittest.TestCase):
    def test_returns_ten_unique_recommendations(self):
        answers = {
            "area": "south",
            "budget": "hemat",
            "mood": "ngobrol",
            "style": "first",
        }

        recommendations = rank_ideas(answers)

        self.assertEqual(len(recommendations), 10)
        self.assertEqual(len({idea["id"] for idea in recommendations}), 10)
        self.assertEqual(recommendations[0]["area"], "south")

    def test_mood_changes_the_top_recommendation(self):
        shared = {"area": "any", "budget": "royal", "style": "adventure"}
        food_first = rank_ideas({**shared, "mood": "kuliner"})[0]
        art_first = rank_ideas({**shared, "mood": "seni"})[0]

        self.assertNotEqual(food_first["id"], art_first["id"])

    def test_budget_prefers_activities_that_fit_the_full_estimate(self):
        recommendations = rank_ideas(
            {
                "area": "any",
                "budget": "hemat",
                "mood": "main",
                "style": "adventure",
            }
        )

        self.assertEqual(recommendations[0]["id"], "ragunan")

    def test_all_curated_ideas_have_map_references(self):
        recommendations = rank_ideas(
            {"area": "any", "budget": "royal", "mood": "ngobrol", "style": "regular"}
        )

        self.assertEqual(len(IDEAS), 10)
        self.assertTrue(all(idea["map_url"].startswith("https://") for idea in recommendations))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), DatePlannerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/recommendations",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urlopen(request)

    def test_recommendations_api_returns_ten_ideas(self):
        with self.post_json(
            {"area": "west", "budget": "sedang", "mood": "seni", "style": "first"}
        ) as response:
            payload = json.load(response)

        self.assertEqual(response.status, 200)
        self.assertEqual(len(payload["recommendations"]), 10)
        self.assertIn("Jakarta Barat", payload["summary"])

    def test_invalid_answer_returns_client_error(self):
        with self.assertRaises(HTTPError) as error:
            self.post_json(
                {"area": "moon", "budget": "hemat", "mood": "seni", "style": "first"}
            )

        self.assertEqual(error.exception.code, 400)
        payload = json.load(error.exception)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
