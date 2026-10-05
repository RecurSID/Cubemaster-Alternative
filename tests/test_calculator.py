import unittest

from acs_load_calculator import (
    CONTAINER_HEIGHT,
    CONTAINER_LENGTH,
    CONTAINER_WIDTH,
    PALLET_LENGTH,
    PALLET_USABLE_HEIGHT,
    PALLET_WIDTH,
    best_2d_pack,
    calculate_40hc,
    calculate_pallet,
)
from hybrid_optimizer import placements_are_valid


class CalculatorRegressionTests(unittest.TestCase):
    def test_pallet_upright_regressions(self):
        # Four supplied historical values require tipping or exceed the usable
        # height.  Their physically valid upright results are asserted here.
        cases = {
            (220, 290, 380): (68, 17, 4),
            (220, 220, 230): (120, 20, 6),
            (280, 270, 320): (60, 12, 5),
            (1000, 400, 120): (39, 3, 13),
            (1000, 360, 230): (18, 3, 6),
            (1080, 430, 60): (52, 2, 26),
            (530, 340, 180): (40, 5, 8),
            (420, 260, 240): (60, 10, 6),
        }
        for dimensions, expected in cases.items():
            with self.subTest(dimensions=dimensions):
                result = calculate_pallet(*dimensions)
                self.assertIsNotNone(result)
                self.assertEqual(
                    (result.total_cartons, result.cartons_per_layer, result.layers),
                    expected,
                )
                self.assertEqual(result.carton_height, dimensions[2])
                self.assertLessEqual(result.loaded_height, PALLET_USABLE_HEIGHT)

    def test_40hc_cubemaster_regressions(self):
        cases = {
            (220, 220, 230): (5940, 540, 11),
            (280, 270, 320): (2816, 352, 8),
            (1000, 400, 120): (1408, 64, 22),
            (1000, 360, 230): (770, 70, 11),
            (1080, 430, 60): (2420, 55, 44),
            (420, 260, 240): (2761, 251, 11),
        }
        for dimensions, expected in cases.items():
            with self.subTest(dimensions=dimensions):
                result = calculate_40hc(*dimensions)
                self.assertIsNotNone(result)
                self.assertEqual(
                    (result.total_cartons, result.cartons_per_layer, result.layers),
                    expected,
                )
                self.assertEqual(result.carton_height, dimensions[2])
                self.assertLessEqual(result.loaded_height, CONTAINER_HEIGHT)

    def test_critical_pallet_utilization_and_layout(self):
        result = calculate_pallet(420, 260, 240)
        self.assertAlmostEqual(result.floor_utilization, 91.0, places=6)
        self.assertAlmostEqual(result.volume_utilization, 81.9, places=6)
        self.assertEqual(len(result.placements), 10)
        self.assertTrue(
            placements_are_valid(result.placements, PALLET_LENGTH, PALLET_WIDTH)
        )

    def test_critical_container_utilization_and_layout(self):
        result = calculate_40hc(420, 260, 240)
        self.assertAlmostEqual(result.floor_utilization, 98.04638398245201)
        self.assertAlmostEqual(result.volume_utilization, 97.49244960966979)
        self.assertEqual(len(result.placements), 251)
        self.assertTrue(
            placements_are_valid(
                result.placements, CONTAINER_LENGTH, CONTAINER_WIDTH
            )
        )

    def test_v4_best_2d_pack_signature_is_preserved(self):
        count, pattern = best_2d_pack(1200, 1000, 420, 260)
        self.assertEqual(count, 10)
        self.assertIn("CP-SAT", pattern)

    def test_historical_pallet_conflicts_are_geometric_not_overrides(self):
        # These requested legacy totals contradict the now-explicit upright
        # height rule.  This test guards against hard-coded/tipped regressions.
        legacy_totals = {
            (220, 290, 380): 70,
            (220, 220, 230): 140,
            (1000, 400, 120): 40,
            (1000, 360, 230): 20,
        }
        for dimensions, legacy_total in legacy_totals.items():
            with self.subTest(dimensions=dimensions):
                result = calculate_pallet(*dimensions)
                self.assertNotEqual(result.total_cartons, legacy_total)
                self.assertEqual(result.layers, PALLET_USABLE_HEIGHT // dimensions[2])


if __name__ == "__main__":
    unittest.main()
