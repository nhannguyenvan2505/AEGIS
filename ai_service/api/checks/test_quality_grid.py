"""The sharpness check must not depend on how many pixels the same picture has."""
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnosis import assess_quality  # noqa: E402


def noise(width, height, seed=0):
    return np.random.default_rng(seed).integers(0, 256, (height, width, 3), dtype=np.uint8)


def slightly_blurred_picture(width, height):
    """A fixed textured picture with a mild blur, close to the sharpness limit."""
    return Image.fromarray(noise(width, height)).filter(ImageFilter.GaussianBlur(1.4))


def metrics(image):
    return assess_quality(np.asarray(image))["metrics"]


class AnalysisGridTests(unittest.TestCase):
    def test_1024_and_2048_images_are_measured_on_every_second_and_fourth_pixel(self):
        # The published test-set results were measured on 1024 px images this way.
        # A 512 px image is not subsampled, so it shows what the larger one must be measured as.
        # The last four have a short side that is not a multiple of the step: its last line stays in.
        for width, height, step in [(1024, 1024, 2), (2048, 2048, 4), (1024, 768, 2), (768, 1024, 2),
                                    (589, 1024, 2), (1024, 685, 2), (2048, 1365, 4), (1321, 2048, 4)]:
            with self.subTest(size=(width, height)):
                pixels = noise(width, height)
                self.assertEqual(assess_quality(pixels), assess_quality(pixels[::step, ::step]))

    def test_the_same_picture_measures_alike_at_phone_sizes(self):
        for base, sizes in [((1024, 1024), [(2048, 2048), (3000, 3000), (4000, 4000)]),
                            ((1024, 768), [(3264, 2448), (4000, 3000), (4032, 3024)]),
                            ((768, 1024), [(3024, 4032)])]:
            picture = slightly_blurred_picture(*base)
            reference = metrics(picture)["laplacian_variance"]
            for size in sizes:
                with self.subTest(base=base, size=size):
                    seen = metrics(picture.resize(size, Image.LANCZOS))["laplacian_variance"]
                    self.assertAlmostEqual(seen / reference, 1.0, delta=0.15,
                                           msg=f"{size}: {seen} against {reference} at {base}")

    def test_images_up_to_512_are_not_subsampled(self):
        pixels = noise(512, 384)
        self.assertGreater(assess_quality(pixels)["metrics"]["laplacian_variance"],
                           assess_quality(pixels[::2, ::2])["metrics"]["laplacian_variance"] * 0.5)
        self.assertEqual(assess_quality(pixels)["metrics"]["mean_luminance"],
                         round(float((pixels.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)).mean()), 2))

    def test_an_extremely_thin_image_is_judged_instead_of_crashing(self):
        for shape in [(32, 20000, 3), (20000, 32, 3)]:
            with self.subTest(shape=shape):
                result = assess_quality(np.zeros(shape, dtype=np.uint8))
                self.assertFalse(result["ok"])
                self.assertEqual(result["metrics"]["laplacian_variance"], 0.0)


if __name__ == "__main__":
    unittest.main()
