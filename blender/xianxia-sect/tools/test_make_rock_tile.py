"""Offline test of tools/make_rock_tile.py's maths on synthetic images. No Blender, no source files read. Run on
the PC with

    python -P E:/Github/PortfolioV5/.claude/worktrees/saltline-game-architecture-ae3e16/blender/xianxia-sect/tools/test_make_rock_tile.py

(-P, not -I: numpy lives in the user site on this PC). Prints 'test_make_rock_tile ok' when every check passes.
"""
import os
import sys

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import make_rock_tile as T  # noqa: E402


def periodic_image(n=240, seed=3):
    """RGB 0-1 that tiles: a few whole-period sines plus wrap-blurred noise, three slightly different channels."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] * (2 * np.pi / n)
    base = 0.5 + 0.12 * np.sin(2 * x + 0.4) * np.cos(3 * y) + 0.08 * np.sin(5 * x + 7 * y + 1.0)
    noise = gaussian_filter(rng.normal(size=(n, n)), 2.0, mode="wrap")
    base = base + 0.25 * noise / noise.std() * 0.3
    return np.clip(np.stack([base * 1.1, base, base * 0.8], -1), 0.01, 1.0)


def gl_normals(z):
    """GL normal vectors of height z (pixels): n = (-dz/dx, +dz/d(row), 1), normalised (rows go down, green up)."""
    zx = np.gradient(z, axis=1)
    zr = np.gradient(z, axis=0)
    n = np.stack([-zx, zr, np.ones_like(z)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def sine_surface(n=256):
    y, x = np.mgrid[0:n, 0:n] * (2 * np.pi / n)
    return 6.0 * np.sin(2 * x) * np.cos(3 * y) + 3.0 * np.sin(x + 2 * y + 0.5) + 2.0 * np.cos(4 * x - y)


def test_wrap_is_seamless():
    """The wrap of an image that does not tile at its own size makes a tile with seam ratio 1.2 or less."""
    img = periodic_image()[:, :200][:200]          # cut off mid-period: the raw square has a seam
    raw = T.seam_ratio(img)
    assert max(raw) > 2.0, raw
    (out,), (p_across, p_down) = T.wrap_mincut([img], len(img) // 6)
    assert out.shape == (200 - 200 // 6,) * 2 + (3,), out.shape
    s = T.seam_ratio(out)
    assert max(s) <= T.SEAM_MAX, s
    assert max(T.seam_ratio_global(out)) <= T.SEAM_MAX, T.seam_ratio_global(out)
    # the second cut runs along columns that already tile: it must meet itself across the left-right edge
    assert abs(int(p_down[0]) - int(p_down[-1])) <= 1, (p_down[0], p_down[-1])
    # and it survives the wrap-around enlargement the tool writes, where a plain (edge-clamped) one shows a seam
    big = T.upscale_wrap(out, 400)
    s2 = T.seam_ratio(big)
    assert max(s2) <= T.SEAM_MAX, s2
    plain = np.stack([np.asarray(T.Image.fromarray(np.ascontiguousarray(out[..., i], np.float32))
                                 .resize((400, 400), T.Image.LANCZOS)) for i in range(3)], -1)
    assert min(T.seam_ratio(plain)) > 1.5, T.seam_ratio(plain)


def test_one_cut_for_colour_and_height():
    """The same image fed as colour and as height gets the identical cut."""
    img = periodic_image()[:180, :180]
    (col, h), paths = T.wrap_mincut([img, img[..., 1]], 30)
    assert np.array_equal(col[..., 1], h)
    # a separate guide cuts both the same way too
    (c2, h2), _ = T.wrap_mincut([img, img[..., 1]], 30, guide=img[..., ::-1])
    assert np.array_equal(c2[..., 1], h2)


def test_normals_integrate_back():
    """A sine surface turned into GL normals integrates back within 2 % RMS."""
    z = sine_surface()
    zr = T.height_from_normals(gl_normals(z), 1.0, highpass=None, clamp=None)
    z0 = z - z.mean()
    err = np.sqrt(((zr - z0) ** 2).mean()) / np.sqrt((z0 ** 2).mean())
    assert err < 0.02, err
    # a crop that does not tile integrates too (the mirror), within the same bound away from nothing
    zc = sine_surface(300)[:200, :230]
    zcr = T.height_from_normals(gl_normals(zc), 1.0, highpass=None, clamp=None)
    zc0 = zc - zc.mean()
    err_c = np.sqrt(((zcr - zc0) ** 2).mean()) / np.sqrt((zc0 ** 2).mean())
    assert err_c < 0.02, err_c


def test_curl_picks_the_green_sign():
    """The curl check reads a GL map as GL and the same map with green flipped as DX."""
    n = gl_normals(sine_surface())
    sign, gl, dx = T.green_sign(n)
    assert sign == 1.0 and gl < dx, (gl, dx)
    f = n.copy()
    f[..., 1] *= -1.0
    sign, gl, dx = T.green_sign(f)
    assert sign == -1.0 and dx < gl, (gl, dx)


def test_flatten_keeps_mean():
    """flatten keeps the mean linear luminance."""
    img = periodic_image()
    for sigma, k in ((240 / 5.0, 0.85), (240 / 8.0, 1.0)):
        out = T.flatten(img, sigma, k)
        assert abs(T.lum(out).mean() / T.lum(img).mean() - 1.0) < 1e-9
        # and it does flatten: the big blobs shrink
        assert gaussian_filter(T.lum(out), 60, mode="wrap").std() < gaussian_filter(T.lum(img), 60, mode="wrap").std()


def test_log_gain_scales_spread():
    """log_gain scales the log spread by its factor within 2 %, and keeps the hue."""
    img = periodic_image()
    s0 = np.log2(T.lum(img)).std()
    for g in (1.35, 0.7, 1.0):
        out = T.log_gain(img, g)
        s = np.log2(T.lum(out)).std()
        assert abs(s / s0 - g) / g < 0.02, (g, s / s0)
        c0 = img / T.lum(img)[..., None]
        c1 = out / T.lum(out)[..., None]
        assert np.allclose(c0, c1)


def test_turn_moves_colour_and_height_together():
    """turn() moves colour and height by the same k; pick_turn's k is a counter-clockwise quarter turn."""
    img = periodic_image()[:120, :120]
    img[5:15, 90:110] = 1.0                        # a marker near the top-right corner
    h = img[..., 0].copy()
    for k in range(4):
        c, hh = T.turn(k, img, h)
        assert np.array_equal(c[..., 0], hh)
        assert np.array_equal(c, np.rot90(img, k, axes=(0, 1)))
    c, hh = T.turn(1, img, h)                      # counter-clockwise: the top-right corner goes top-left
    assert c[10:30, 5:15].min() == 1.0 and hh[10:30, 5:15].min() == 1.0
    # real up 54 degrees clockwise of image up (the attack's measure): one counter-clockwise turn, 36 left
    k, left = T.pick_turn(54.0)
    assert k == 1 and abs(left + 36.0) < 1e-9, (k, left)
    assert T.pick_turn(-30.0) == (0, -30.0)
    assert T.pick_turn(170.0)[0] == 2


def main():
    test_wrap_is_seamless()
    test_one_cut_for_colour_and_height()
    test_normals_integrate_back()
    test_curl_picks_the_green_sign()
    test_flatten_keeps_mean()
    test_log_gain_scales_spread()
    test_turn_moves_colour_and_height_together()
    print("test_make_rock_tile ok")


if __name__ == "__main__":
    main()
