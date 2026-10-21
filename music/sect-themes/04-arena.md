# 04 · Sword-Discussion Arena 论剑台 (Hackathons)

A floating 60 m stone dueling ring, ringed by 40 victory banners, with a judges' pavilion and a giant stone sword. This section shows 36 hackathon wins. The music should feel fast, grand and godlike, like an immortal looking down on the mortal world from the heavens. Traditional Chinese instruments only, no Western orchestra. This is the fullest track.

The trick is two speeds at once. Underneath, the music races: rolling dagu drums, erhu and gaohu (high erhu) in rushing tremolo (a bow moving so fast the note shimmers) and sweeping guzheng and yangqin runs. On top, the suona (the Chinese trumpet, a loud double-reed horn) plays long, loud notes that each stretch across several bars. Nothing is choppy. The fast parts flow rather than jab, and the suona soars over them like it is above the fight. The gehu (a Chinese cello) holds the deep notes, so no Western cello is needed.

At 140 BPM one bar is about 1.7 seconds, so a suona note held for four bars rings for about 7 seconds. It ends on a finale with the suona at its loudest and highest. The tempo stays the same through the finale, so the loop trimming in the README still works.

## Suno settings

- **Mode:** Custom (Advanced on the web)
- **Instrumental:** ON
- **Title:** Peerless Under Heaven 论剑台
- **Model:** newest available (v5 or later)
- **Weirdness:** 35%
- **Style Influence:** 85%
- **Key and tempo:** B minor pentatonic (yu mode), 140 BPM

## Style of Music

```
Traditional Chinese orchestra instrumental, Chinese instruments only, fast, grand, majestic and godlike, an immortal looking down on mortals from the heavens, B minor pentatonic (yu mode), 140 BPM, fast driving rhythm underneath with a long soaring melody on top, loud suona lead playing long sustained notes held for several bars, erhu and gaohu section in rushing tremolo, flowing legato erhu lines, deep gehu sustaining underneath, fast rolling dagu and paigu drums, guzheng and yangqin arpeggios sweeping up and down, sheng chords, huge gong swells, triumphant, relentless energy, builds to a towering suona finale, wide mix, moderate loudness
```

Length: 647 characters.

## Exclude styles

```
vocals, singing, humming, choir, chant, female vocals, wordless vocals, shouting, western orchestra, violin, cello, piano, brass section, french horn, trombone, synth, staccato, pizzicato, stabs, choppy, march, military march, marching band, snare drum, snare roll, parade, fanfare, electric guitar, rock drums, heavy metal, EDM, trap, dubstep, taiko, Japanese, drum solo, breakdown, fade out
```

## Structure (paste into the Lyrics box)

```
[Instrumental]

[Intro: gong swell, then fast rolling dagu drums and rushing erhu tremolo kick in at full speed]

[Theme A: suona enters high and loud, one long note held for several bars over the racing drums, then a broad soaring melody]

[Drive: drums and erhu section race forward, guzheng sweeps, gong]

[Theme B: erhu carries a flowing legato melody over the fast rhythm, yangqin shimmering]

[Theme A: suona returns louder, long sustained notes stretching across several bars while the ensemble races beneath]

[Finale: suona at its loudest and highest, holding each note for bars at a time over the full ensemble at full speed, triumphant, looking down on the mortal world]

[Outro: suona holds the final note on B, one last drum roll, gong rings out]

[End]
```

## Alternate styles

Both keep Chinese instruments only, the fast rhythm, the long suona notes and the finale. Use them with the same Structure.

### A. Brighter and more heavenly

Use this if the main prompt sounds too dark.

```
Traditional Chinese orchestra instrumental, Chinese instruments only, fast, radiant, majestic and godlike, a celestial emperor gazing down on the mortal world, A Mixolydian pentatonic (zhi mode), 140 BPM, racing rhythm underneath, loud golden suona lead holding long sustained notes for several bars on top, erhu and gaohu in rushing tremolo, guzheng and yangqin arpeggios, sheng chords, fast rolling dagu drums, gong swells, triumphant and soaring, towering suona finale, moderate loudness
```

Length: 490 characters.

### B. Heavier and more thunderous

Use this if the main prompt comes out too slow or not powerful enough.

```
Traditional Chinese battle drums and suona, Chinese instruments only, fast and overwhelming, godlike, a deity looking down on mortals, B minor pentatonic (yu mode), 140 BPM, relentless fast rolling dagu and paigu drums, thunderous gong and cymbal crashes, deep gehu tremolo, loud suona lead with long held notes stretching across several bars over the storm, erhu doubling the melody in legato, triumphant and immovable, towering suona finale, moderate loudness
```

Length: 461 characters.

## If it comes out wrong

- **Western instruments sneak in (violins, piano, horns):** check the Exclude box has "western orchestra, violin, cello, piano, brass section". Raise Style Influence to 95%. If it persists, delete "orchestra" from the first line of the Style, so it reads "Traditional Chinese instrumental".
- **Suona plays short notes or copies the drums:** move "loud suona lead playing long sustained notes held for several bars" to the very start of the Style. Suno pays most attention to the first words.
- **Comes out slow:** Suno sometimes plays at half speed. Check the real BPM (README step 3). If it is near 70, regenerate or use Alternate B, which leans hardest on fast drums.
- **Turns choppy or stabby again:** check that "staccato, stabs, choppy" are in Exclude styles. Then delete "yangqin" from the Style. It is a hammered instrument and can drift into sharp hits.
- **Too dark or evil, not triumphant:** use Alternate A.
- **Suona is harsh rather than grand:** replace "loud suona lead" with "majestic suona lead in its middle range". It stays loud but sounds rounder.
- **Still sounds like a march:** check that "march, snare drum, fanfare" are in Exclude styles, then raise Weirdness to 45%.
- **No finale, it just stops or fades:** use Extend from the end of the second Theme A. Leave only the [Finale], [Outro] and [End] lines in the Lyrics box.
- **Finale speeds up or slows down:** the loop maths in the README need one tempo. Regenerate, or trim the loop to end before the finale.
- **Drum solo or a quiet breakdown:** keep "drum solo, breakdown" in Exclude styles.
- **Too loud next to the other tracks:** fine for now. Loudness gets evened out when you trim (see README).
