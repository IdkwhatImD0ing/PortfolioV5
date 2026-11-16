#!/bin/bash
# Box setup for the sect (Vast.ai, vastai/base-image). Idempotent. Blender 5.2.2 at /root/blender, the project
# mirror at /E:/Github/PortfolioV5/blender/xianxia-sect, fonts at /C:/Windows/Fonts (copied separately).
set -e
export DEBIAN_FRONTEND=noninteractive
if [ ! -x /root/blender/blender ]; then
  apt-get update -qq
  apt-get install -y -qq wget xz-utils python3 libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxext6 \
    libxrandr2 libxinerama1 libxcursor1 libxkbcommon0 libxkbcommon-x11-0 libsm6 libice6 libdbus-1-3 libgl1 libegl1 \
    libglx0 libglvnd0 libvulkan1 libwayland-client0 libwayland-cursor0 libwayland-egl1 libfontconfig1 libfreetype6 >/dev/null
  cd /root
  # The Berkeley mirror first: the official server gave 10 KB/s to a box on 2026-11-12. The file is then
  # checked against the official checksum list.
  rm -f blender-5.2.2-linux-x64.tar.xz*
  wget -q -T 30 https://mirrors.ocf.berkeley.edu/blender/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz || \
    { rm -f blender-5.2.2-linux-x64.tar.xz*; wget -q https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz; }
  if wget -q -T 30 -O blender.sha256 https://download.blender.org/release/Blender5.2/blender-5.2.2.sha256; then
    grep 'blender-5.2.2-linux-x64.tar.xz' blender.sha256 | sha256sum -c - || { echo "SETUP_FAIL: Blender checksum"; exit 1; }
  else
    echo "SETUP_WARN: no checksum list, Blender archive not verified"
  fi
  tar xf blender-5.2.2-linux-x64.tar.xz
  mv blender-5.2.2-linux-x64 blender
  rm blender-5.2.2-linux-x64.tar.xz
fi
mkdir -p "/E:/Github/PortfolioV5/blender/xianxia-sect/out" "/C:/Windows/Fonts"
/root/blender/blender --version | head -1
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
nproc
free -g | sed -n '2p'
df -h / | tail -1
ls /usr/lib/x86_64-linux-gnu/libEGL_nvidia.so* >/dev/null 2>&1 && echo "EGL_nvidia ok" || echo "SETUP_WARN: no libEGL_nvidia (EEVEE would run on the CPU)"
ls /usr/lib/x86_64-linux-gnu/libnvoptix.so* >/dev/null 2>&1 && echo "optix ok" || echo "SETUP_WARN: no libnvoptix (Cycles must use CUDA)"
# The Vast base image loads a CUDA compat library newer than the host driver, which a GeForce refuses (cuInit 804).
if ls /etc/ld.so.conf.d/00-compat-*.conf >/dev/null 2>&1; then
  mkdir -p /root/ld_off && mv /etc/ld.so.conf.d/00-compat-*.conf /root/ld_off/ && ldconfig
  echo "cuda compat path removed"
fi
CU=$(python3 -c "import ctypes; print(ctypes.CDLL('libcuda.so.1').cuInit(0))" 2>&1 | tail -1)
[ "$CU" = "0" ] && echo "cuda init ok" || echo "SETUP_WARN: cuInit says $CU (Cycles will find no GPU)"
echo SETUP_OK
