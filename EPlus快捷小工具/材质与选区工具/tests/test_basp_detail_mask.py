"""Offline asset invariants; run with Python 3 + Pillow."""
import sys
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from pbr_mask_core import build, region


class DetailMaskTests(unittest.TestCase):
    def test_base_pigment_removed(self):
        mask = Image.new('RGBA', (8, 8), (255, 0, 0, 80))
        dark = build(Image.new('RGBA', (8, 8), (25, 25, 25, 255)), mask)[0]
        bright = build(Image.new('RGBA', (8, 8), (220, 220, 220, 255)), mask)[0]
        self.assertEqual(dark.tobytes(), bright.tobytes())
        self.assertEqual(dark.getpixel((4, 4)), (230, 0, 0, 80))

    def test_alpha_and_region_identity(self):
        mask = Image.new('RGBA', (5, 1))
        mask.putdata([(255, 0, 0, 0), (0, 255, 0, 64), (0, 0, 255, 128),
                      (255, 255, 0, 192), (255, 0, 255, 255)])
        result, ids, _, _ = build(Image.new('RGBA', mask.size, (80, 80, 80, 255)), mask)
        for i in range(5):
            self.assertEqual(result.getpixel((i, 0))[3], mask.getpixel((i, 0))[3])
            self.assertEqual(region(result.getpixel((i, 0))[:3]), ids[i])

    def test_groove_and_wear_remain_ordered(self):
        source = Image.new('RGBA', (15, 15), (80, 80, 80, 255))
        source.putpixel((6, 7), (20, 20, 20, 255))
        source.putpixel((8, 7), (150, 150, 150, 255))
        result = build(source, Image.new('RGBA', source.size, (255, 0, 0, 255)))[0]
        groove, base, wear = [result.getpixel((x, 7))[0] for x in (6, 7, 8)]
        self.assertLess(groove, base - 60)
        self.assertGreater(wear, base + 10)
        self.assertLessEqual(wear, 252)

    def test_neighboring_regions_do_not_bleed(self):
        source, mask = Image.new('RGBA', (10, 10)), Image.new('RGBA', (10, 10))
        for y in range(10):
            for x in range(10):
                v = 20 if x < 5 else 220
                source.putpixel((x, y), (v, v, v, 255))
                mask.putpixel((x, y), (255, 0, 0, 0) if x < 5 else (0, 255, 0, 255))
        result = build(source, mask)[0]
        self.assertEqual(result.getpixel((4, 5)), (230, 0, 0, 0))
        self.assertEqual(result.getpixel((5, 5)), (0, 230, 0, 255))


if __name__ == '__main__':
    unittest.main()
