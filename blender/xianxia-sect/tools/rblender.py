#!/usr/bin/env python3
"""Run Blender on the rented GPU box (Vast.ai) exactly as if it ran locally.

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py <blender args...>
    python .../rblender.py --fetch-blend <blender args...>   # also copy back .blend files the run wrote
    python .../rblender.py --sh "<shell command>"             # run a shell command in the project folder there
    python .../rblender.py --pull <path relative to project>  # copy a file or folder from the box

What it does:
1. Uploads the project's source (sect/, spec.md, docs/, small text files under out/tmp/) and the scan
   textures in assets/web/ (tools/prep_textures.mjs; only the ones the box does not have yet) to the box
   at the same path. Files of 5 MB or more are skipped. Only changed files are replaced, each atomically.
2. Runs Blender 5.2.2 there with the working directory set to '/', and the project mirrored at
   '/E:/Github/PortfolioV5/blender/xianxia-sect'. Absolute paths like 'E:/Github/...' therefore
   resolve to the mirror, so scripts and arguments need no changes. The KaiTi/YaHei fonts are
   mirrored at '/C:/Windows/Fonts/'. Use forward slashes in paths.
3. Streams Blender's output back, then copies every file under out/ that the run created or
   changed back to this PC (except .blend files unless --fetch-blend), and exits with Blender's code.

The box address lives in tools/remote.json: {"host": "...", "port": 12345}. Set SECT_REMOTE=tools/remote2.json
(or an absolute path) to talk to a second box instead.
"""
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import uuid

ROOT = 'E:/Github/PortfolioV5/blender/xianxia-sect'
REMOTE_ROOT = '/E:/Github/PortfolioV5/blender/xianxia-sect'
REMOTE_BLENDER = '/root/blender/blender'
UPLOAD_DIRS = ('sect', 'docs', 'assets/web')   # assets/web only: the rest of assets/ is the raw downloads
HASHED_DIRS = ('assets/web',)                   # big files: sent only when the box's copy differs (md5)
UPLOAD_FILES = ('spec.md',)
SCRATCH_EXT = ('.py', '.json', '.txt', '.csv', '.md')
SKIP_PARTS = ('__pycache__',)


def remote():
    # SECT_REMOTE names another box file (e.g. tools/remote2.json) so test work can run on a second box.
    path = os.environ.get('SECT_REMOTE') or os.path.join(ROOT, 'tools', 'remote.json')
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    with open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg['host'], int(cfg['port'])


def ssh_cmd(extra=None):
    host, port = remote()
    cmd = ['ssh', '-p', str(port), '-o', 'StrictHostKeyChecking=accept-new', '-o', 'BatchMode=yes',
           '-o', 'ServerAliveInterval=30', '-o', 'LogLevel=ERROR', f'root@{host}']
    return cmd + ([extra] if extra else [])


def _wanted(rel, scratch):
    if any(p in rel.split('/') for p in SKIP_PARTS):
        return False
    return rel.endswith(SCRATCH_EXT) if scratch else True


def _md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _remote_md5(dirs):
    """{path relative to the project: md5} of the files under these project folders on the box."""
    if not dirs:
        return {}
    q = ' '.join(shlex.quote(d) for d in dirs)
    r = subprocess.run(ssh_cmd(f'cd {shlex.quote(REMOTE_ROOT)} && find {q} -type f -exec md5sum {{}} + 2>/dev/null; true'),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = {}
    for line in r.stdout.splitlines():
        h, _, rel = line.partition('  ')
        out[rel.strip()] = h.strip()
    return out


def upload():
    there = _remote_md5([d for d in HASHED_DIRS if os.path.isdir(os.path.join(ROOT, d))])
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name in UPLOAD_FILES:
            p = os.path.join(ROOT, name)
            if os.path.isfile(p):
                tar.add(p, arcname=name)
        for top, scratch in [(d, False) for d in UPLOAD_DIRS] + [('out/tmp', True)]:
            base = os.path.join(ROOT, top)
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, ROOT).replace('\\', '/')
                    if _wanted(rel, scratch) and os.path.getsize(full) < 5_000_000:
                        if rel in there and there[rel] == _md5(full):
                            continue
                        tar.add(full, arcname=rel)
    tmp = f'/tmp/up_{uuid.uuid4().hex}'
    script = (
        f'set -e; mkdir -p {tmp} {shlex.quote(REMOTE_ROOT)}; tar xzf - -C {tmp}; cd {tmp}; '
        f'find . -type f | while IFS= read -r f; do d={shlex.quote(REMOTE_ROOT)}/"$(dirname "$f")"; '
        f'mkdir -p "$d"; cmp -s "$f" {shlex.quote(REMOTE_ROOT)}/"$f" || mv -f "$f" {shlex.quote(REMOTE_ROOT)}/"$f"; done; '
        f'rm -rf {tmp}'
    )
    r = subprocess.run(ssh_cmd(script), input=buf.getvalue(), capture_output=True)
    if r.returncode != 0:
        sys.stderr.write('rblender: upload failed: ' + r.stderr.decode(errors='replace'))
        sys.exit(2)


def fetch_since(marker, with_blend):
    name_filter = '' if with_blend else "! -name '*.blend' ! -name '*.blend1'"
    script = (f'cd {shlex.quote(REMOTE_ROOT)} && [ -d out ] && '
              f'find out -newer {marker} -type f {name_filter} -print0 | tar czf - --null -T - ; rm -f {marker}')
    r = subprocess.run(ssh_cmd(script), capture_output=True)
    if r.stdout:
        _extract(r.stdout)


def pull(rel):
    rel = rel.replace('\\', '/').replace(ROOT + '/', '')
    r = subprocess.run(ssh_cmd(f'cd {shlex.quote(REMOTE_ROOT)} && tar czf - {shlex.quote(rel)}'), capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode(errors='replace'))
        sys.exit(r.returncode)
    _extract(r.stdout)


def _extract(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        for m in tar.getmembers():
            if m.name.startswith('/') or '..' in m.name.split('/'):
                continue
            tar.extract(m, ROOT)


def _fix_arg(a):
    # Windows-style project paths -> forward slashes so they resolve inside the mirror.
    if len(a) > 2 and a[1] == ':' and '\\' in a:
        return a.replace('\\', '/')
    return a


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    if args[0] == '--sh':
        sys.exit(subprocess.run(ssh_cmd(f'cd {shlex.quote(REMOTE_ROOT)} && {args[1]}')).returncode)
    if args[0] == '--pull':
        pull(args[1])
        return
    with_blend = False
    if args[0] == '--fetch-blend':
        with_blend, args = True, args[1:]
    upload()
    marker = f'/tmp/m_{uuid.uuid4().hex}'
    cmd = ' '.join(shlex.quote(_fix_arg(a)) for a in args)
    rc = subprocess.run(ssh_cmd(f'touch {marker}; sleep 1; cd / && {REMOTE_BLENDER} {cmd}')).returncode
    fetch_since(marker, with_blend)
    sys.exit(rc)


if __name__ == '__main__':
    main()
