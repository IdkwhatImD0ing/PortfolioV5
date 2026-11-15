#!/bin/bash
# Set up a fresh rented box for the sect and upload the scene with its caches.
#
#     bash tools/box/box_up.sh <host> <port> [scene .blend]
#
# Run it in Git Bash on the PC, from anywhere. It
#   1. writes tools/remote.json (tools/rblender.py reads the box's address there),
#   2. starts tools/box/box_setup.sh on the box (Blender 5.2.2 at /root/blender, checked against the official
#      checksum; the CUDA compat path taken out; "cuda init ok" must show in the last lines it prints),
#   3. uploads what rblender.py does not send: the fonts, the timeline, the camera, the audit cache and chunk plan,
#      and the scene as the box's out/sect_chase.blend. The scene defaults to the round 56 file in the main checkout.
#      The main checkout's own out/sect_chase.blend is an older file: never upload that one.
#   4. prints the scene's md5 on the box and the end of the setup log.
# Rent the box first with tools/box/vast_rent.py (it repairs the image's SSH key file), and destroy it when the job is
# done. docs/scene/rock-r59.md has a run sheet that starts with this script.
H="$1"; P="$2"
SCENE="${3:-E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.r56.blend}"
if [ -z "$H" ] || [ -z "$P" ]; then echo "usage: box_up.sh <host> <port> [scene .blend]"; exit 64; fi
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$(cd "$HERE/../.." && pwd)"                      # this checkout's blender/xianxia-sect
B="/E:/Github/PortfolioV5/blender/xianxia-sect"     # the box mirrors the project at the main checkout's path
R="root@$H"
O="-o BatchMode=yes -o LogLevel=ERROR -o StrictHostKeyChecking=accept-new"
cd "$W" || exit 1
printf '{"host": "%s", "port": %s}\n' "$H" "$P" > tools/remote.json
scp -P "$P" $O "$HERE/box_setup.sh" "$R:/root/box_setup.sh" || exit 2
ssh -p "$P" $O "$R" "nohup bash /root/box_setup.sh > /root/setup.log 2>&1 < /dev/null &
mkdir -p '$B/out/web/full/site' '/C:/Windows/Fonts'" || exit 3
scp -P "$P" $O C:/Windows/Fonts/georgiab.ttf C:/Windows/Fonts/msyh.ttc C:/Windows/Fonts/palab.ttf C:/Windows/Fonts/simkai.ttf "$R:/C:/Windows/Fonts/" || exit 4
scp -P "$P" $O out/section_timeline.json "$R:$B/out/" || exit 5
scp -P "$P" $O out/web/full/vis_cache.npz out/web/full/chunks.npz out/web/full/chunks.json out/web/full/audit.json out/web/full/camcheck.json out/web/full/mist_voxels.bin out/web/full/mist_voxels.json out/web/full/plan_check.json out/web/full/standin_stats.json out/web/full/water_meta.json "$R:$B/out/web/full/" || exit 6
scp -P "$P" $O out/web/full/site/camera.json "$R:$B/out/web/full/site/" || exit 7
scp -P "$P" $O "$SCENE" "$R:$B/out/sect_chase.blend" || exit 8
ssh -p "$P" $O "$R" "md5sum '$B/out/sect_chase.blend'; for i in \$(seq 1 120); do grep -q 'SETUP_OK\|SETUP_FAIL' /root/setup.log && break; sleep 5; done; tail -12 /root/setup.log"
