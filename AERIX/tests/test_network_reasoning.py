"""Unit tests for AERIX Network Reasoning Engine"""

import unittest
from ml_pipeline.analytics.network_reasoning import NetworkReasoningEngine


class TestNetworkReasoning(unittest.TestCase):

    def setUp(self):
        self.engine = NetworkReasoningEngine(fps=30.0, pixels_per_meter=15.0)
        self.sample_tracks = [
            {
                "track_id": 1,
                "class_label": "car",
                "fine_grained_class": "sedan",
                "trajectory": [
                    {"frame_number": 1, "x": 100, "y": 100},
                    {"frame_number": 30, "x": 180, "y": 100},
                ],
                "kinematics": {
                    "average_speed_kmh": 25.0,
                    "stop_dwell_time_seconds": 0.0,
                    "distance_traveled_meters": 30.0,
                    "current_acceleration_ms2": 0.2,
                },
                "geodetic_position": {
                    "latitude": 18.5590,
                    "longitude": 73.7868,
                    "link_name": "Baner Road Westbound",
                    "lane_id": "Lane 1",
                },
            },
            {
                "track_id": 2,
                "class_label": "car",
                "fine_grained_class": "van",
                "trajectory": [
                    {"frame_number": 10, "x": 200, "y": 100},
                    {"frame_number": 150, "x": 200, "y": 100},
                ],
                "kinematics": {
                    "average_speed_kmh": 2.0,
                    "stop_dwell_time_seconds": 35.0,
                    "distance_traveled_meters": 2.0,
                    "current_acceleration_ms2": -1.8,
                },
                "geodetic_position": {
                    "latitude": 18.5592,
                    "longitude": 73.7870,
                    "link_name": "Baner Road Commercial Corridor",
                    "lane_id": "Lane 1 (Outer)",
                },
            },
        ]

    def test_compute_network_reasoning_structure(self):
        res = self.engine.compute_network_reasoning(self.sample_tracks)
        self.assertTrue(res.get("is_network_reasoned"))
        self.assertIn("congestion_origination", res)
        self.assertIn("signal_performance", res)
        self.assertIn("weaving_and_conflicts", res)
        self.assertIn("desire_line_analysis", res)
        self.assertIn("obstruction_census", res)
        self.assertIn("ai_network_explanation", res)

    def test_congestion_origination_fields(self):
        res = self.engine.compute_network_reasoning(self.sample_tracks)
        orig = res["congestion_origination"]
        self.assertIn("origin_timestamp_seconds", orig)
        self.assertIn("origin_location_link", orig)
        self.assertIn("shockwave_propagation_velocity_kmh", orig)

    def test_obstruction_census(self):
        res = self.engine.compute_network_reasoning(self.sample_tracks)
        obst = res["obstruction_census"]
        self.assertGreaterEqual(obst["total_obstruction_events"], 1)
        self.assertIn("average_dwell_duration_seconds", obst)


if __name__ == "__main__":
    unittest.main()
