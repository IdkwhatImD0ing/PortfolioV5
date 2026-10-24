# Deploy and roll back

How the site, the backend, the voice agent and the scene files ship, and how to undo each one. This
page holds no secrets. Key names are listed in [`../../server/README.md`](../../server/README.md) and
[`../../client/.env.local.example`](../../client/.env.local.example). The values live in the hosting
dashboards and in Secret Manager, never in the repo.

## Where things run

| Address | What it is |
|---|---|
| [art3m1s.me](https://art3m1s.me) | The sect, from this repo's `client/` on Vercel. www and billzhang.tech redirect here. |
| [v4.art3m1s.me](https://v4.art3m1s.me) | The previous site, from its own repo and Vercel project. Kept so older versions keep working. |
| One Cloud Run service | The backend in `server/`. Both sites talk to it. |

## The site (`client/`)

- **Ship.** A push to `main` deploys to art3m1s.me.
- **Git LFS must be on.** The scene files are Git LFS files. The Vercel project needs Git LFS turned on
  (Settings, then Git), or visitors get small pointer files instead of the scene, and the sect never
  loads.
- **Roll back.** In Vercel, promote the last good deployment (Instant Rollback). Then revert the bad
  commit on `main`, or the next push brings it back.

## The backend (`server/`)

One service answers for every site. The persona is picked per call: the sect asks for the senior
disciple, and anything that asks for nothing gets the classic persona. That default is what keeps the
old site working.

- **Ship with a safety net.** Deploy with `server/deploy.sh` (options in
  [`../../server/README.md`](../../server/README.md), "Deploy"). On the shared service:
  1. Deploy a new revision that gets no traffic, with a tag (`NO_TRAFFIC=1 TAG=...`).
  2. Test it at its tag URL: the health check, then a text chat with and without the sect persona.
  3. Move the traffic to it with `gcloud run services update-traffic`.
  4. Keep the previous revision.
- **Roll back.** Send all traffic back to the previous revision:
  `gcloud run services update-traffic <service> --region <region> --to-revisions <previous-revision>=100`.
  Revision tags need at least 3 characters.
- **Order.** When a change spans both, ship the server before the client. A new server works with the
  old client; a new client may need the new server.

More: [`docker.md`](docker.md) (the image and Cloud Run settings).

## The voice agent (Retell)

- Never overwrite or delete a published agent version. Publish a new version or a new agent, and keep
  every old one, so every earlier site keeps working.
- The browser dials the agent named in the client's environment. Switching agents means changing that
  setting in Vercel and redeploying the site. Rolling back means pointing it at the previous agent.

## The scene files (`blender/xianxia-sect/`)

- Light bakes run on a rented cloud GPU. Development bakes use fast settings; one
  production bake runs at the end (see the [decisions log](../decisions/README.md)).
- `tools/sect_pack.py` packs the baked files into `client/public/sect/full`. They are committed
  through Git LFS and ship with the next site deploy.
- **Roll back.** Revert the commit that installed the new pack. The old files are still in Git LFS.

## Other services

- [`browserless.md`](browserless.md): a separate headless-browser service on Cloud Run.
