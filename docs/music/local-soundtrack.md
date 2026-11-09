# Website soundtrack replacement

The sect's twelve generated themes were replaced with songs from Jin Yong dramas and donghua. One
track plays on the loading screen and one at each of the eleven stops.

## Final mapping

| Music key | Area | Song | Artist | Show | Source ID | Lyrics |
|---|---|---|---|---|---|---|
| `loading` | Loading screen | 风舞 | Not credited | 斗罗大陆 | `jbF369bXcJU` | Instrumental |
| `gate` | Mountain Gate | 铁血丹心 | Not credited | 射雕英雄传 2017 | `nd9Sdcv5egM` | Instrumental |
| `mirror` | Heart-Mirror Terrace | Throne of Glory | Xian Ke | 神印王座 | `3eSajcF8_Fw` | English |
| `forge` | Artifact Forge | 刀剑如梦 (erhu and guzheng) | Instrumental ensemble | 倚天屠龙记 2019 | `eiquXgRDa40` | Instrumental |
| `arena` | Sword-Discussion Arena | 降临 | Qi You (祁游) | 神印王座 | `n7w5How-ALE` | Chinese |
| `mission` | Mission Hall | 璀璨冒险人 | Zhou Shen (周深) | 斗罗大陆2 | `gUPnXFn-33w` | Chinese |
| `library` | Scripture Pavilion | 化凡 | Yang Zixi (杨子熙) | 仙逆 | `r2a-1S3xNQY` | Chinese |
| `steles` | Stele Forest | 光之少年 | GALA | 神印王座 | `jFXCp-kc4h8` | Chinese |
| `scroll` | Jade Slip Pavilion | 浩瀚 | Zhang Jie (张杰) | 神雕侠侣 2014 | `i2CER52gUVc` | Chinese |
| `formation` | Grand Formation | 天谴觉醒 | Not credited | 神印王座 | `ll17o0KFV-Q` | Instrumental |
| `abode` | Cave Abode | 逍遥 | Wallace Huo (霍建华) | 笑傲江湖 2013 | `dQONNl1YOeY` | Chinese |
| `summit` | Moon-Gazing Summit | 破茧 | Angela Zhang (张韶涵) | 斗罗大陆 | `TjvrbPqfBxI` | Chinese |

The stable keys remain the keys in `client/src/lib/sect/music.ts`. The display names and long source
filenames never become runtime identifiers.

## Source handoff

The working files are outside this repository:

```text
E:\Github\personal\youtube-mp3-downloader\downloads\website-music\
  <title> [<source-id>].mp3
  lyrics\
    <source-id>.json
    manifest.json
    lyrics-preview.html
```

There are twelve 192 kbps MP3s and eight timed lyric files. Import tooling finds an MP3 by the ID in
square brackets and a lyric file by `<id>.json`, then writes opaque storage object names.

## Listening references

- 风舞: https://www.youtube.com/watch?v=jbF369bXcJU
- 铁血丹心: https://www.youtube.com/watch?v=nd9Sdcv5egM
- Throne of Glory: https://www.youtube.com/watch?v=3eSajcF8_Fw
- 刀剑如梦: https://www.youtube.com/watch?v=eiquXgRDa40
- 降临: https://www.youtube.com/watch?v=n7w5How-ALE
- 璀璨冒险人: https://www.youtube.com/watch?v=gUPnXFn-33w
- 化凡: https://www.youtube.com/watch?v=r2a-1S3xNQY
- 光之少年: https://www.youtube.com/watch?v=jFXCp-kc4h8
- 浩瀚: https://www.youtube.com/watch?v=i2CER52gUVc
- 天谴觉醒: https://www.youtube.com/watch?v=ll17o0KFV-Q
- 逍遥: https://www.youtube.com/watch?v=dQONNl1YOeY
- 破茧: https://www.youtube.com/watch?v=TjvrbPqfBxI

## Lyric references

These pages were used to prepare the bilingual source lines. *Throne of Glory* is sung in English;
the other seven pages provide Chinese, pinyin and English.

- [Throne of Glory](https://chinesemusicwiki.com/throne-of-glory-throne-of-seal-ost-by-xian-ke/)
- [降临](https://chinesemusicwiki.com/descent-jiang-lin-throne-of-seal-ost-by-qi-you/)
- [璀璨冒险人](https://chinesemusicwiki.com/the-dazzling-adventurer-cui-can-mao-xian-ren-soul-land-2-the-peerless-tang-clan-ost-by-zhou-shen/)
- [化凡](https://chinesemusicwiki.com/mortify-to-mortal-yang-zixi/)
- [光之少年](https://chinesemusicwiki.com/the-boy-of-light-guang-zhi-shao-nian-throne-of-seal-ost-by-gala-band/)
- [浩瀚](https://chinesemusicwiki.com/vast%e6%b5%a9%e7%80%9ahao-han-romance-of-the-condor-heroes-ost-by-jason-zhang-jie%e5%bc%a0%e6%9d%b0/)
- [逍遥](https://chinesemusicwiki.com/free-and-unfettered-xiao-yao-swordsman-ost-by-wallace-huo-chien-hwa/)
- [破茧](https://chinesemusicwiki.com/break-the-cocoon%e7%a0%b4%e8%8c%a7po-jian-soul-land-ost-by-angela-chang%e5%bc%a0%e9%9f%b6%e6%b6%b5/)

The same URLs remain in the source handoff manifest. Prepared browser-facing lyric files omit them.

## Preparation

`server/scripts/prepare_music.py`:

1. Validate all expected IDs and lyric schemas.
2. Normalize audio to `-17 LUFS` with a `-1.5 dBTP` ceiling.
3. Measure duration, bytes and hashes from the final MP3s.
4. Review instrumental loop points and use full-track loops for sung songs.
5. Verify lyric timing against the final processed audio.
6. Strip source-only metadata from the served lyric copies.
7. Upload audio and lyrics to private storage and publish a metadata-only manifest.

The exact prepared values are in [`soundtrack-assets.md`](soundtrack-assets.md). The old Suno prompts
remain in [`sect-themes/`](sect-themes/README.md) as the record of the original soundtrack.
