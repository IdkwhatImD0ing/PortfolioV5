"""
Makes the loading screen's poster stills (public/sect/poster/) from captures of the live page.

    python client/scripts/make-poster.py WIDE TALL PORTRAIT OUTDIR

WIDE      the start view in a window of aspect 2.4 on the High tier (1920 x 800)
TALL      the start view in a window of aspect 1.25 on the High tier (1250 x 1000)
PORTRAIT  the start view in a touch phone window of 884 x 1100 CSS pixels on the Low tier
          (any device scale; it is resized to 884 x 1100)
OUTDIR    gets landscape.webp (1640 x 972, under 80,000 bytes) and portrait.webp (884 x 1100,
          under 60,000 bytes)

docs/sect/lux.md "Loading posters" has the capture steps. The geometry is posterBox in
src/lib/sect/opening.ts. With ty0 = tan(fovY / 2) and tx0 = ty0 * 16 / 9, landscape.webp spans
tan(angle) from -TX to TX across and from -TY to TY down, TX = 2.4 * ty0 and TY = tx0 / 1.25.
On screens wider than 16:9 the camera keeps fovY, so WIDE covers the full width and the middle
band of half-height ty0. On narrower ones it keeps the 16:9 horizontal field, so TALL covers the
full height and the middle column of half-width tx0.

TALL is pasted whole over WIDE, so every screen from 1.25 to 16:9 sees TALL alone. The frame's
vignette darkens each capture towards its own edges, so where they meet TALL is about 15% darker
than WIDE. WIDE's wings are brought to TALL's level at the seam and back to their own over 160
pixels, so no step shows. The four corners neither covers (no screen in the range sees them) are
filled with a blur of the picture next to them.
"""
import io
import math
import sys

import numpy as np
from PIL import Image

FOV_Y = 35.1154
REF_ASPECT = 16 / 9
MIN_ASPECT = 1.25
MAX_ASPECT = 2.4
MAX_FOV_Y = 70
LAND_SIZE = (1640, 972)
PORT_SIZE = (884, 1100)
LAND_MAX_BYTES = 80_000
PORT_MAX_BYTES = 60_000
SEAM_STRIP = 16
SEAM_FADE = 160

ty0 = math.tan(math.radians(FOV_Y) / 2)
tx0 = ty0 * REF_ASPECT
TX = MAX_ASPECT * ty0
TY = tx0 / MIN_ASPECT


def box_blur(x, r, axis):
    """Sum over a window of 2r + 1 along one axis (zeros outside), divided by the window."""
    pad = [(0, 0)] * x.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(x, pad), axis=axis)
    n = x.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(x, r):
    """Three box passes on both axes: close to a Gaussian of sigma about r."""
    for _ in range(3):
        x = box_blur(box_blur(x, r, 0), r, 1)
    return x


def place(img, half_w, half_h, size):
    """
    Resamples a capture that spans tan(angle) from -half_w to half_w across and -half_h to half_h
    down onto the poster's grid. Returns the layer, the mask of whole pixels it covers, and their
    range (u0, u1, v0, v1).
    """
    W, H = size
    kx, ky = W / (2 * TX), H / (2 * TY)
    left, right = (TX - half_w) * kx, (TX + half_w) * kx
    top, bottom = (TY - half_h) * ky, (TY + half_h) * ky
    u0, u1 = max(0, math.ceil(left - 1e-6)), min(W, math.floor(right + 1e-6))
    v0, v1 = max(0, math.ceil(top - 1e-6)), min(H, math.floor(bottom + 1e-6))
    sw, sh = img.size
    box = (
        (u0 - left) / (right - left) * sw,
        (v0 - top) / (bottom - top) * sh,
        (u1 - left) / (right - left) * sw,
        (v1 - top) / (bottom - top) * sh,
    )
    part = img.resize((u1 - u0, v1 - v0), Image.LANCZOS, box=box)
    layer = np.zeros((H, W, 3), np.float64)
    mask = np.zeros((H, W), bool)
    layer[v0:v1, u0:u1] = np.asarray(part, np.float64)
    mask[v0:v1, u0:u1] = True
    return layer, mask, (u0, u1, v0, v1)


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def match_wings(wide, tall_layer, wide_rect, tall_rect):
    """Scales WIDE's wings towards TALL's level at each seam, fading back over SEAM_FADE pixels."""
    out = wide.copy()
    tu0, tu1, _, _ = tall_rect
    _, _, wv0, wv1 = wide_rect
    rows = slice(wv0, wv1)
    for side in (-1, 1):
        strip = slice(tu0, tu0 + SEAM_STRIP) if side < 0 else slice(tu1 - SEAM_STRIP, tu1)
        a = wide[rows, strip].mean(1)
        b = tall_layer[rows, strip].mean(1)
        # Smooth along the seam: the gain should follow the vignette, not a cloud that moved.
        gain = (smooth_rows(b) + 1) / (smooth_rows(a) + 1)
        gain = np.clip(gain, 0.6, 1.6)
        if side < 0:
            cols = np.arange(max(0, tu0 - SEAM_FADE), tu0)
            t = (cols - (tu0 - SEAM_FADE)) / SEAM_FADE
        else:
            cols = np.arange(tu1, min(wide.shape[1], tu1 + SEAM_FADE))
            t = ((tu1 + SEAM_FADE) - cols) / SEAM_FADE
        w = smoothstep(t)[None, :, None]
        out[rows, cols] = wide[rows, cols] * (1 + (gain[:, None, :] - 1) * w)
    return out


def smooth_rows(v, r=20):
    """Smooths a (rows, 3) profile along the rows, keeping its ends (edge values repeated)."""
    p = np.pad(v, ((3 * r, 3 * r), (0, 0)), mode="edge")
    for _ in range(3):
        p = box_blur(p, r, 0)
    return p[3 * r : -3 * r]


def fill_holes(img, mask):
    """
    Fills the pixels outside `mask` with a blur of the pixels inside it, finer near them and
    broader further out (normalized convolution at radii from 128 down to 4 pixels).
    """
    m = mask.astype(np.float64)
    fill = None
    for r in (128, 64, 32, 16, 8, 4):
        den = blur(m, r)
        num = blur(img * m[..., None], r)
        est = num / np.maximum(den, 1e-9)[..., None]
        if fill is None:
            fill = est
        else:
            w = np.clip(den / 0.3, 0, 1)[..., None]
            fill = fill * (1 - w) + est * w
    return np.where(mask[..., None], img, fill)


def encode(img, max_bytes):
    for q in range(92, 19, -2):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() < max_bytes:
            return buf.getvalue(), q
    raise SystemExit(f"cannot fit {img.size} under {max_bytes} bytes")


def check_aspect(name, img, want, tol=0.01):
    a = img.size[0] / img.size[1]
    if abs(a - want) > tol * want:
        raise SystemExit(f"{name} is {img.size[0]} x {img.size[1]} (aspect {a:.4f}); want aspect {want:.4f}")


def landscape(wide, tall):
    check_aspect("WIDE", wide, MAX_ASPECT)
    check_aspect("TALL", tall, MIN_ASPECT)
    # WIDE keeps fovY (aspect over 16:9); TALL keeps the 16:9 horizontal field.
    wa = wide.size[0] / wide.size[1]
    ta = tall.size[0] / tall.size[1]
    assert math.degrees(2 * math.atan(tx0 / ta)) < MAX_FOV_Y
    a, ma, ra = place(wide, wa * ty0, ty0, LAND_SIZE)
    b, mb, rb = place(tall, tx0, tx0 / ta, LAND_SIZE)
    a = match_wings(a, b, ra, rb)
    comp = np.where(mb[..., None], b, a)
    comp = fill_holes(comp, ma | mb)
    return Image.fromarray(np.clip(np.rint(comp), 0, 255).astype(np.uint8), "RGB")


def portrait(cap):
    check_aspect("PORTRAIT", cap, PORT_SIZE[0] / PORT_SIZE[1], tol=0.005)
    return cap.resize(PORT_SIZE, Image.LANCZOS)


def main(argv):
    if len(argv) != 5:
        raise SystemExit(__doc__)
    wide, tall, port, out = argv[1:]
    open_rgb = lambda p: Image.open(p).convert("RGB")
    jobs = [
        ("landscape.webp", landscape(open_rgb(wide), open_rgb(tall)), LAND_MAX_BYTES),
        ("portrait.webp", portrait(open_rgb(port)), PORT_MAX_BYTES),
    ]
    for name, img, limit in jobs:
        data, q = encode(img, limit)
        path = f"{out.rstrip('/')}/{name}"
        with open(path, "wb") as f:
            f.write(data)
        print(f"{path}: {img.size[0]} x {img.size[1]}, {len(data):,} bytes (quality {q}, limit {limit:,})")


if __name__ == "__main__":
    main(sys.argv)
