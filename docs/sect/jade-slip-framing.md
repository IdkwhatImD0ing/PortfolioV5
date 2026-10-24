# Jade slip stop: camera framing

Decided 2026-10-24 (run r42). Code: `client/src/lib/sect/framing.ts` (`STOP_FRAMING.scroll`),
`client/src/lib/sect/opening.ts` (`PORTRAIT_TURN_DEG.scroll`). Tests: `framing.test.ts`,
`opening.test.ts`. Screenshots: `.playwright-mcp/r42/jade_before_*.png` and `jade_after_*.png`
(not committed).

## The problem

The owner: "The jade slip looks too far forward, maybe slightly back might be better." On a desktop
the slip's left end sat 7 px from the screen edge.

## What changed

The camera now stands a little further back along the flight path at this stop. It still turns
8 degrees left and 2.5 down, so the slip faces the viewer.

| Screen | Before | After |
| --- | --- | --- |
| Desktop and laptop | 9 frames back (44 m from the slip) | 12 frames back (48 m) |
| Phone and portrait tablet | 21 frames back (62 m) | 24 frames back (67 m) |

What that looks like:

- **Desktop (1600 x 900):** the slip's left end is now 111 px in from the edge instead of 7. The
  slip is 272 px tall instead of 299, so the text is still readable (about 14 px a character). The
  whole pavilion still sits beside it, left of the info card.
- **Phone (390 x 844):** the slip is 82 px tall instead of 89. The phone's extra turn changed from
  half a degree left to half a degree right, so the slip and pavilion are centred again (26 px and
  24 px from the edges).
- **Portrait tablet (820 x 1180):** steps back the same amount as the phone, as before.

## Design choices

- **Same step back in proportion everywhere.** Desktop moves about 9% further from the slip; phones
  and tablets move about the same share.
- **The camera eases in over 76 frames instead of 64.** A stop may only stand back a third of the
  frames it eases over. Otherwise the camera would slow to less than half the film's speed on the
  way in.
- **The hand-over to the next stop (the formation) is unchanged in shape.** Leaving the stop, the
  view now turns at most 1.17 degrees a frame on desktop (was 1.13) and 1.35 on phones (was 1.30).
  That is still about as gentle as around the Heart-Mirror stop.
- **Known side effect on tablets:** from the new spot, a band of rough rocks shows along the
  bottom-left of the tablet screen, in the empty ground below the plaza. On a tablet the slip is also
  fairly small (about 115 px tall). A tablet-only framing that stands nearer (like the desktop's)
  would fix both; it was left out to keep this change small.
