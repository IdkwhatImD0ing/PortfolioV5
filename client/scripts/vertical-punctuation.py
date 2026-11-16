"""Gives a font the comma, full stop and pause mark as they are written in an upright column.

Ma Shan Zheng draws them for a line read across only: set in a column (writing-mode: vertical-rl)
its full stop sits at the foot of its square on the left, and its comma at the foot in the middle.
In a column the mark belongs in the upper right of its square, close under the character it
follows. This adds a copy of each mark moved there, and a `vert` feature that swaps the copy in.
Browsers turn `vert` on for upright text in a column on their own; a line read across is unchanged.

    python vertical-punctuation.py font.woff2

scripts/subset-lyrics-font.mjs runs it on the lyrics' cut of the font. Needs fontTools and brotli.
"""
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

# 、 。 ，
MARKS = (0x3001, 0x3002, 0xFF0C)
# Where the mark's ink is centred in its square: three quarters across, three quarters up.
ACROSS, UP = 0.75, 0.75

path = sys.argv[1]
font = TTFont(path)
ascent, descent = font["hhea"].ascent, font["hhea"].descent
cmap = font.getBestCmap()
outlines = font.getGlyphSet()
glyf, hmtx = font["glyf"], font["hmtx"]

swaps = []
for mark in MARKS:
    name = cmap.get(mark)
    if not name:
        continue
    glyph = glyf[name]
    advance = hmtx[name][0]
    dx = round(advance * ACROSS - (glyph.xMin + glyph.xMax) / 2)
    dy = round(descent + (ascent - descent) * UP - (glyph.yMin + glyph.yMax) / 2)
    pen = TTGlyphPen(outlines)
    outlines[name].draw(TransformPen(pen, (1, 0, 0, 1, dx, dy)))
    upright = f"{name}.vert"
    glyf[upright] = pen.glyph()
    hmtx[upright] = (advance, glyph.xMin + dx)
    swaps.append(f"sub {name} by {upright};")

if not swaps:
    sys.exit(f"{path}: none of the marks to move")

font.setGlyphOrder(font.getGlyphOrder())
addOpenTypeFeaturesFromString(
    font,
    "languagesystem DFLT dflt;\nlanguagesystem hani dflt;\nfeature vert {\n" + "\n".join(swaps) + "\n} vert;\n",
    tables=["GSUB"],
)
font.save(path)
print(f"{path}: {len(swaps)} marks for upright columns")
