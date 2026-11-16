"""Rent a Vast offer as tools/cloud/vast.py does, plus a start-up command that repairs /root/.ssh.

    python vast_rent.py <offer id> <label> [disk GB, default 60]

Vast's base image of 2026-11-12 (cuda-13.2.1-auto) starts with an authorized_keys file whose owner or mode the
SSH server refuses ("bad ownership or modes"), so every key is denied on both SSH routes. The start-up command
sets the owner and modes right, and keeps them right for the first ten minutes in case the image writes the file
again. Reads VAST_API_KEY from the environment; prints the new instance id only.
"""
import json
import os
import sys
import urllib.request

API = 'https://console.vast.ai/api/v0'
FIX = ("fix_ssh() { chown root:root /root /root/.ssh /root/.ssh/authorized_keys 2>/dev/null; chmod go-w /root 2>/dev/null; "
       "chmod 700 /root/.ssh 2>/dev/null; chmod 600 /root/.ssh/authorized_keys 2>/dev/null; }; "
       "fix_ssh; (for i in $(seq 1 120); do fix_ssh; sleep 5; done) > /dev/null 2>&1 &")


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method)
    req.add_header('Authorization', 'Bearer ' + os.environ['VAST_API_KEY'])
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, data, timeout=60) as r:
        return json.load(r)


def main():
    oid, label = sys.argv[1], sys.argv[2]
    disk = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    r = call('PUT', f'/asks/{oid}/', {"client_id": "me", "image": "vastai/base-image:@vastai-automatic-tag",
                                      "disk": disk, "runtype": "ssh_direct", "label": label,
                                      "env": "-e NVIDIA_DRIVER_CAPABILITIES=all", "onstart": FIX})
    iid = r.get('new_contract')
    print('rented' if r.get('success') else 'failed', iid)
    if iid:
        try:
            call('PUT', f'/instances/{iid}/', {"label": label})
        except Exception as e:
            print('label not set:', e)


if __name__ == '__main__':
    main()
