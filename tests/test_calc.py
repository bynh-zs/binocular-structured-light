# -*- coding: utf-8 -*-
import importlib.util
import math
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


calc = load("volume_budget", os.path.join("calc", "volume_budget.py"))


class TestVolumeError(unittest.TestCase):
    def test_reference_case(self):
        # δ=0.42 mm, R=50 mm → 2.52%
        self.assertAlmostEqual(calc.volume_error_ratio(0.42, 50) * 100, 2.52, places=2)

    def test_upper_bound_still_within_promise(self):
        # δ 上浮到 0.6 mm 时 3.6%，仍小于 5%
        self.assertAlmostEqual(calc.volume_error_ratio(0.60, 50) * 100, 3.60, places=2)
        self.assertLess(calc.volume_error_ratio(0.60, 50) * 100, 5.0)

    def test_radius_scaling(self):
        # R 翻倍误差减半
        self.assertAlmostEqual(calc.volume_error_ratio(0.42, 100) * 2,
                               calc.volume_error_ratio(0.42, 50))

    def test_invalid_radius(self):
        with self.assertRaises(ValueError):
            calc.volume_error_ratio(0.42, 0)


class TestDeltaRms(unittest.TestCase):
    def test_square_sum(self):
        self.assertAlmostEqual(calc.delta_rms([0.3, 0.4]), 0.5)

    def test_single(self):
        self.assertAlmostEqual(calc.delta_rms([0.42]), 0.42)


class TestVoxel(unittest.TestCase):
    def test_half_mm_grid(self):
        n, total, dist, ww, wn = calc.voxel_memory(0.5, 200)
        self.assertEqual(n, 400)
        self.assertEqual(total, 400 ** 3)
        self.assertAlmostEqual(dist, 400 ** 3 * 4 / 1024 ** 2, delta=1)
        self.assertAlmostEqual(ww, dist * 2, delta=1)

    def test_point_three_mm_grid(self):
        n, total, dist, _, _ = calc.voxel_memory(0.3, 200)
        self.assertEqual(n, 667)
        self.assertGreater(dist, 1000)  # 距离场 >1 GB


class TestWall(unittest.TestCase):
    def test_limits_half_mm(self):
        tau, wall = calc.wall_limits(0.5)
        self.assertAlmostEqual(tau, 1.5)
        self.assertAlmostEqual(wall, 3.0)

    def test_limits_refined(self):
        tau, wall = calc.wall_limits(0.3)
        self.assertAlmostEqual(tau, 0.9, places=6)
        self.assertAlmostEqual(wall, 1.8, places=6)


class TestTiming(unittest.TestCase):
    def test_seven_frames(self):
        _, total = calc.timing_budget(views=6, frames=7)
        self.assertAlmostEqual(total, 19.7, delta=0.1)

    def test_thirteen_frames(self):
        _, total = calc.timing_budget(views=6, frames=13)
        self.assertAlmostEqual(total, 23.8, delta=0.1)

    def test_thirteen_with_retry(self):
        _, total = calc.timing_budget(views=6, frames=13, retry_views=1)
        self.assertGreater(total, 24.0)
        self.assertLess(total, 60.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
