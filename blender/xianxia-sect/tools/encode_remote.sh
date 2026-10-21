#!/bin/bash
# Encode the rendered blocking frames on the cloud box (run via: ssh ... 'bash -s' < encode_remote.sh).
set -e
cd "/E:/Github/PortfolioV5/blender/xianxia-sect/out"
mkdir -p video
n=$(ls frames/*.png | wc -l)
echo "frames: $n"
X264="-c:v libx264 -pix_fmt yuv420p -movflags +faststart"
# Full flight for viewing.
ffmpeg -nostdin -loglevel error -y -framerate 24 -start_number 1 -i frames/%04d.png $X264 -preset slow -crf 18 video/flythrough_blocking.mp4
# Every frame a keyframe, so a website can seek to any scroll position instantly.
ffmpeg -nostdin -loglevel error -y -framerate 24 -start_number 1 -i frames/%04d.png $X264 -preset medium -crf 23 -g 1 video/flythrough_scrub_allkey.mp4
# One clip per segment (frame ranges from section_timeline.json; boundary frames are shared).
i=1
for r in 1:288 288:497 497:739 739:942 942:1188 1188:1343 1343:1535 1535:1729; do
  s=${r%:*}; e=${r#*:}
  ffmpeg -nostdin -loglevel error -y -framerate 24 -start_number $s -i frames/%04d.png -frames:v $((e - s + 1)) $X264 -preset slow -crf 18 "video/seg0${i}.mp4"
  i=$((i + 1))
done
ls -la video
