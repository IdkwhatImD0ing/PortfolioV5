"""Writes src/app/sect/assets/paper.webp, the faint rice-paper tile on the /sect panels, the reader
and the page view: soft pulp mottling and a few long fibres, as paper-coloured light in the alpha
channel of one colour (a light-only texture compresses far better than light and dark speckle; the
panels darken their base a touch so the mean stays where it was). 256 px, seamless: the noise is
periodic and the fibres are drawn on a 3 x 3 tiling and cropped. Seeded, so a rerun gives the same tile.

    python scripts/paper-texture.py   (needs numpy and Pillow)
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

N = 256
FIBRES = 90
OUT = Path(__file__).resolve().parent.parent / "src/app/sect/assets/paper.webp"
rng = np.random.default_rng(7)


def periodic_noise(n, lo, hi, power):
    """Band-limited noise that tiles: random phases on a 1/f^power spectrum between lo and hi."""
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    amp = np.where((f >= lo) & (f <= hi), 1.0 / np.maximum(f, 1e-6) ** power, 0.0)
    img = np.real(np.fft.ifft2(amp * np.exp(2j * np.pi * rng.random((n, n)))))
    img -= img.mean()
    return img / np.abs(img).max()


mottle = periodic_noise(N, 1 / 128, 1 / 6, 1.2)  # cloudy pulp
grain = periodic_noise(N, 1 / 10, 1 / 3, 0.5)  # tooth

big = Image.new("L", (3 * N, 3 * N), 0)
draw = ImageDraw.Draw(big)
for _ in range(FIBRES):
    x, y = rng.random(2) * N
    a = rng.random() * np.pi
    length = 18 + rng.random() * 46
    bend = (rng.random() - 0.5) * 1.4
    pts = [(x + np.cos(a + bend * t) * length * t, y + np.sin(a + bend * t) * length * t) for t in np.linspace(0, 1, 7)]
    v = int(60 + rng.random() * 140)
    for ox in (0, N, 2 * N):
        for oy in (0, N, 2 * N):
            draw.line([(px + ox, py + oy) for px, py in pts], fill=v, width=1)
big = big.filter(ImageFilter.GaussianBlur(0.7))
fibres = np.asarray(big, dtype=np.float64)[N : 2 * N, N : 2 * N] / 255.0

v = 0.75 * mottle + 0.25 * grain
alpha = np.clip(0.5 + 0.5 * v, 0, 1) * 0.045 + fibres * 0.07
rgba = np.zeros((N, N, 4))
rgba[..., 0], rgba[..., 1], rgba[..., 2] = 245, 236, 220
rgba[..., 3] = alpha * 255
Image.fromarray(np.clip(np.round(rgba), 0, 255).astype(np.uint8), "RGBA").save(
    OUT, "WEBP", lossless=False, quality=60, alpha_quality=50, method=6
)
print(f"{OUT.name}: {OUT.stat().st_size} bytes, mean alpha {alpha.mean():.3f}, max {alpha.max():.3f}")
