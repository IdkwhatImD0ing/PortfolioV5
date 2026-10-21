# 09 · Grand Sect-Protecting Formation 护宗大阵 (Architecture)

Eight pillars stand around a turning core under a glass dome of light, with runes pulsing in sequence. This section explains how the site works. The music should feel like an ancient stone golem guarding the sect. Most of the time it sleeps: slow, heavy and peaceful, like a mountain breathing. When provoked, it wakes with terrifying, heaven-shaking might. Then it settles back to sleep.

Everything stays slow and ponderous, even at its loudest. The fury comes from weight, not speed: colossal drums land like a mountain taking a step, gongs crash, and deep horns roar. At 60 BPM one bar is 4 seconds, so each big hit has room to shake the air before the next one lands. The track starts and ends calm, so the loop point joins quiet to quiet.

## Suno settings

- **Mode:** Custom (Advanced on the web)
- **Instrumental:** ON
- **Title:** The Stone Guardian Wakes 护宗大阵
- **Model:** newest available (v5 or later)
- **Weirdness:** 40%
- **Style Influence:** 75%
- **Key and tempo:** F# minor pentatonic (yu mode), 60 BPM

## Style of Music

```
Chinese epic cinematic instrumental, slow and ponderous, an ancient stone golem guardian, F# minor pentatonic (yu mode), 60 BPM, starts peaceful and slumbering with a deep slow heartbeat drum, low sheng drone, hollow xun and low guqin notes, distant bronze bells, then provoked it awakens with terrifying heaven-shaking might, colossal dagu and war drums landing like mountain footsteps, huge gong crashes, deep long horn blasts, low brass and low strings, earth-trembling bass, crushing but never fast, then it settles back to calm, deep cavernous reverb, wide powerful mix, moderate loudness
```

Length: 593 characters.

## Exclude styles

```
vocals, singing, humming, choir, chant, female vocals, wordless vocals, fast tempo, speed up, arpeggio, ostinato, EDM, trance, techno, synthwave, electric guitar, rock drums, heavy metal, trap, dubstep, flamenco, Japanese, taiko, pop, drum kit, backbeat, march
```

## Structure (paste into the Lyrics box)

```
[Instrumental]

[Intro: deep slow heartbeat drum, low drone, the stone guardian sleeps]

[Slumber: hollow xun and low guqin notes, distant bronze bells, peaceful and heavy]

[Stirring: the heartbeat grows louder, low strings rumble, bells tremble]

[Awakening: one colossal drum and gong strike, deep horns roar, the ground shakes]

[Fury: slow crushing drum hits like mountain footsteps, gong crashes, low brass and horns, terrifying heaven-shaking might, same slow tempo]

[Fury: even bigger, every hit shakes the sky, still slow and heavy]

[Settling: the hits fade one by one, the drone returns]

[Outro: slow heartbeat drum and low drone, the guardian sleeps again, ends on F#]

[End]
```

## Alternate styles

### A. Gentler giant

Use this if the main prompt is too scary or the calm parts are too short.

```
Chinese cinematic instrumental, slow and ponderous, a peaceful ancient stone guardian that stirs and rises with great might, F# minor pentatonic (yu mode), 60 BPM, long calm sections with deep heartbeat drum, low sheng drone, hollow xun, low guqin, soft bronze bells, one huge awakening with colossal dagu drums, gong crashes and deep horns, slow and heavy, never fast, returns to calm, deep reverb, wide mix, moderate loudness
```

Length: 427 characters.

### B. Heavier fury

Use this if the awakening is not frightening enough.

```
Chinese epic battle score, instrumental, slow, crushing and terrifying, a colossal stone golem awakening, F# minor pentatonic (yu mode), 60 BPM, quiet ominous drone and heartbeat drum at first, then massive dagu and war drums like mountains falling, thunderous gong crashes, roaring deep horns, low brass and low strings, earth-shaking sub bass, heaven-shaking might, never fast, settles back to an ominous calm, huge cavernous reverb, wide powerful mix, moderate loudness
```

Length: 472 characters.

### C. Chinese instruments only

Use this if the main prompt sounds like a Hollywood trailer.

```
Traditional Chinese orchestra instrumental, Chinese instruments only, slow and ponderous, an ancient stone guardian, F# minor pentatonic (yu mode), 60 BPM, peaceful at first with deep heartbeat drum, low sheng drone, hollow xun, low guqin, bronze bells, then it awakens with heaven-shaking might, colossal dagu drums, huge gong crashes, deep gehu and diyin gehu, roaring suona blasts, crushing but never fast, then calm again, deep reverb, moderate loudness
```

Length: 457 characters.

## If it comes out wrong

- **Speeds up when it wakes:** check that "fast tempo, speed up" are in Exclude styles. The power should come from heavier hits, not more of them. If it still speeds up, use Alternate B.
- **Never wakes, stays sleepy:** move "then provoked it awakens with terrifying heaven-shaking might" earlier in the Style, right after the tempo. Or use Alternate B.
- **Never calms down:** use Extend from the end of the second Fury. Leave only the [Settling], [Outro] and [End] lines in the Lyrics box.
- **Sounds like a Hollywood trailer:** use Alternate C, and raise Style Influence to 85%.
- **Still sounds weird or out of tune:** check the key words say "F# minor pentatonic (yu mode)". If it persists, change both key words to "D minor pentatonic". The mood stays the same.
- **Sounds Spanish or Middle Eastern:** keep "flamenco" excluded, and use the D minor fix above.
- **The loud part is much louder than the other tracks:** fine. Loudness gets evened out when you trim (see README). The quiet parts will come up and the loud part will come down.
