# Music volume slider: when it shows

Decided 2026-10-24 (run r42). Code: `client/src/lib/sect/volume-reveal.ts` (the rules, with tests),
`client/src/app/sect/experience/sound-toggle.tsx` (the controls), `client/src/app/sect/sect.css`
(the fade).

## The problem

The owner: "The music button there is no way to close the slider after it opens." The slider beside
the sound toggle showed the whole time the music played.

## What it does now

The slider comes out when someone wants it and goes away on its own.

It shows:

- for about 4 seconds after the music turns on, so visitors notice it;
- while the mouse is over the speaker button or the slider;
- while keyboard focus is on either one (Tab onto the speaker shows it, the next Tab goes into it);
- on a phone or tablet, when you tap the speaker while music plays and the slider is hidden. That
  tap opens the slider instead of muting. A tap while it shows mutes. Phone video players work the
  same way.

It hides:

- about 0.7 seconds after the mouse leaves (so crossing the small gap to the slider does not close it);
- right away on a click or tap anywhere else;
- on Escape (focus goes back to the speaker button);
- after about 4 seconds with no use, but never while the mouse is over it, the keyboard is on it, or
  someone is dragging it;
- when the music is muted (as before).

## Design choices

- **Same place as before.** Left of the speaker on wide screens, standing upright under it on
  phones. When it hides, its space closes up, so the graphics button slides back next to the
  speaker, where it sat when the music was muted.
- **Short fade and slide** (0.2 to 0.25 seconds), in the style of the other panels. No motion for
  visitors who ask their system for reduced motion.
- **Hidden means really gone.** A hidden slider is `inert`: Tab skips it, screen readers skip it,
  and clicks pass through to the scene.
- **A mouse click and Enter/Space always mute.** Only a touch or pen tap on the hidden slider's
  speaker opens it instead.
- **One Escape does one thing.** If Escape closes the slider, the scene does not also recentre.
- **The rules are a small pure function** (a reducer) so they can be unit tested without a browser.
  The component only runs its one timer and passes events in.
- **Untouched:** the loading screen's "Turn on sound" button, and the music ducking during a voice
  call.
