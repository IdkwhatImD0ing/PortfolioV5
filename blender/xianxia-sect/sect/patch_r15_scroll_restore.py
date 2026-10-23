"""Round 15 restore (run in round 24): put the Jade Slip Pavilion's great jade scroll back where the owner liked it, in
an existing out/sect_chase.blend, so the file matches what a fresh build of sect/areas/scroll.py makes. Run on the cloud
box, on a copy first, after sect/patch_r21_motes.py (this patch refuses a file that still has scroll.motes):

    python E:/Github/PortfolioV5/blender/xianxia-sect/tools/rblender.py -b \
        E:/Github/PortfolioV5/blender/xianxia-sect/out/sect_chase.blend --python-exit-code 1 \
        --python E:/Github/PortfolioV5/blender/xianxia-sect/sect/patch_r15_scroll_restore.py [-- DRY_RUN=1]

Why (owner, 2026-10-23): "I dont like the jade strip now, way before it was good, then it was rotated to the weird
previous way." The first build (2026-10-10 .. 10-21) stood it at (-10, -4, 13), full size, unturned: at the 1103 hold it
was big and close, its tall slips nearly flat to the view, the left part past the frame's left edge (screenshots
.playwright-mcp/atmo/base_1103.png and audit/visual/hold_1103.png: the slips from the left edge to x 516 of 1600, y
~362..~765). Round 2 (patch_r2_compose.py, audit D2) moved it to (-4, 6, 13) at 0.9x turned -40 deg ("the weird
previous way"); round 10 (patch_r10_scroll_face.py) to (-8.2, 12, 11.5) at 0.86x, square to a view the client turned
6 deg left ("now"). This brings back the first place, turn and size (scroll.SCROLL_C, SCROLL_YAW, SCROLL_SCALE:
patch_r2_compose.OLD_SCROLL_C, 0, 1.0) and the film's own view at the hold (scroll.HOLD_TURN (0, 0); the client's
STOP_FRAMING.scroll goes in the same release, scratchpad r24/client_scroll.diff).

What it does (everything that belongs to the scroll display; nothing else is touched):
1. scroll.jade_scroll (the 'resume' hotspot): location, turn and scale to SCROLL_C, SCROLL_YAW, SCROLL_SCALE. Its
   meshes are kept as they are: the r8 Jin Yong verses and the script the r12 libs patch cut into the slips
   (props.SLIPS_CUT, mesh tag sect_r12 = 'cut'); the patch checks they are byte for byte the same afterwards.
2. The r5 standing frame (Empty scroll.scroll_frame and .posts / .rails / .bases / .emblems, tagged
   scroll.FRAME_ITEM) is REBUILT with scroll.scroll_frame for the new place and size: its posts run from the terrace
   (plinths on the paving) up past the top rail, the gold sun and the silver moon on their heads. The old frame objects
   and meshes are removed first; the new ones get the same names.
3. The rune rings scroll.ring and scroll.ring_in (raised bands since r12 libs, origins on the paving) move to
   scroll.RING_C, 1 m behind the scroll's centre: (-10, -3), their first place, at their first size (object scale
   scroll.RING_K = 1 in x and y; r10 had 0.956). Same meshes; their spin keeps turning them.
4. The script ring's dark channel in the terrace top (r12 areas: scroll.terrace_channel, painted round the r10 ring
   centre) is painted again round the new centre at the new radii: scroll.terrace.body gets a fresh plain top
   (A.platform, as scroll._terrace builds it) and scroll.terrace_channel paints it, so no ring sits over a channel cut
   for the old place and the dark stone lies exactly under the script band again. Same object and mesh name.
The spirit motes are gone (patch_r21_motes.py), so nothing else follows the scroll.

Recognised states, piece by piece: 'old' (the round-12 file: r10 placement, r12 channel round the r10 ring centre,
verified by rebuilding the r10 painting and comparing the mesh exactly) or 'new' (this design). Anything else fails.
When every piece is new and the frame equals a fresh build: 'PATCH nothing changed: not saving'.

Checks before saving (any failure stops without saving; DRY_RUN=1 runs everything and never saves):
- scroll.py is the restored design (the first build's place, turn, size and ring place; no client turn);
- names exact (no '.001'), the object count unchanged, every frame mesh closed, the scroll's own meshes unchanged and
  still cut;
- the frame: the sill and the top rail meet the slips; each post's plinth stands on free paving between the two ring
  bands; rays down from the plinths' corners meet the terrace within 2 cm of their bottoms;
- the rings lie on the terrace and off the axis walk, nothing standing on the paving sits on a band, the floor just
  outside each band is the paving (the band stands RUNE_TOP proud of it);
- the terrace top is one surface at its height, dark stone exactly under the new channel's radii and paving everywhere
  else (no dark stone left at the old place), and the script band lies inside the channel;
- no scene piece cuts into the scroll or its frame (BVH overlap; only the paving under the sunk plinths is allowed), so
  nothing clashes with the token stand, the rocks, the approach and exit walks or the link stairs;
- the flight (chase.cam, every frame) stays FLIGHT_CLEAR m from the scroll and its frame (their geometry: rounds 2
  and 10 asked it of their box, which is 17.6 m here, at frame 1121, where the camera has turned away from them);
- the hold as the site shows it (site_view: chase.cam's own pose and the client's field of view for the screen):
  chase.cam is still at scroll.HOLD_CAM / HOLD_HEADING; at 1600 x 900 the slips reach from past the left edge to
  x ORIG_RIGHT_PX, their right end's top and bottom at ORIG_TOP_PX / ORIG_BOTTOM_PX (each within ORIG_TOL_PX), as in
  the owner's screenshot; the display keeps PAV_GAP_PX left of the pavilion's silhouette; on the approach (1060-1100)
  it touches the far pavilion's silhouette by at most APPROACH_OVERLAP_PX (the first build's right end came as close).
  The departure and a 390 x 844 phone (no portrait turn) are logged.

Prints 'PATCH DIGEST <md5>' (every touched object's transform and mesh; the same after a first and a second run) and
'PATCH CACHES needs audit' with the chunks to re-bake (the scroll, its frame, the rings and the terrace change boxes):
run the export_web audit, then chunks,meta (the 'resume' hotspot moves), then bakefull (the scroll chunk and the
backdrop at least), then the pack.
"""
import hashlib
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sect.areas import scroll as SC  # noqa: E402
from sect.lib import arch as A  # noqa: E402
from sect.lib import props as P  # noqa: E402

AREA_ROOT = SC.K + ".root"
SCROLL = SC.K + ".jade_scroll"
RINGS = (SC.K + ".ring", SC.K + ".ring_in")
MOTES = SC.K + ".motes"
TERRACE = SC.K + ".terrace"
BODY = TERRACE + ".body"
CAM = "chase.cam"
HOLD = 1103
APPROACH = tuple(range(1060, 1101, 4))
DEPART = tuple(range(1110, 1161, 5))
RES = (1600, 900)                  # the film's frame (the web's reference aspect)
RES_SMALL = (1366, 768)
RES_PHONE = (390, 844)
PORTRAIT_SHIFT = 0.2               # client scene.tsx PORTRAIT_SHIFT: portrait screens show the image shifted up
MAX_FOV_Y = 70.0                   # client camera-path.ts fovForAspect's cap
TOL = 1e-3
# the first build (patch_r2_compose.OLD_SCROLL_C and RING_DY): what scroll.py must say now
FIRST = dict(c=(-10.0, -4.0, 13.0), yaw=0.0, s=1.0, ring=(-10.0, -3.0), k=1.0)
# the round-12 file: patch_r10_scroll_face's placement (scroll.py of 2026-10-22), the channel painted round its rings
R10_YAW = math.radians(77.27) + math.radians(6.0) - math.pi / 2
R10_K = 0.86 / 0.9
R10 = dict(c=(-8.2, 12.0, 11.5), yaw=R10_YAW, s=0.86, k=R10_K,
           ring=(-8.2 - R10_K * math.sin(R10_YAW), 12.0 + R10_K * math.cos(R10_YAW)))
# the owner's screenshot of the first build at the hold (.playwright-mcp/audit/visual/hold_1103.png, 1600 x 900): the
# slips' right end and, at that end, their top and bottom (measured on the jade's colour)
ORIG_RIGHT_PX, ORIG_TOP_PX, ORIG_BOTTOM_PX = 516.0, 360.0, 761.0
ORIG_TOL_PX = 25.0
PAV_GAP_PX = 20.0                  # at 1600 x 900 (scaled for smaller screens)
APPROACH_OVERLAP_PX = 10.0         # on the approach the display may touch the far pavilion's silhouette by this much
                                   # (its right end comes within a few px of it, as in the first build)
FLIGHT_CLEAR = 18.0                # m from the display's geometry (rounds 2 and 10 asked it of its box)
NEAR = 0.3
CLASH_OK = (TERRACE,)              # the plinths sink 0.12 m into the paving by design
SLIP_PARTS = (".slips", ".script", ".cords")


def log(*a):
    print("PATCH", *a, flush=True)


def options():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    dry = False
    for a in argv:
        k, eq, v = a.partition("=")
        if k == "DRY_RUN" and eq:
            dry = v.strip().lower() not in ("", "0", "false", "no")
        else:
            raise SystemExit("patch_r15_scroll_restore: unknown option %r (DRY_RUN=1)" % a)
    return dry


class Fail(list):
    def add(self, msg):
        log("FAIL", msg)
        self.append(msg)


class Consts:
    """Temporarily give scroll.py another placement (its module globals), to rebuild what that placement built."""

    def __init__(self, st):
        self.kw = dict(SCROLL_C=tuple(st["c"]), SCROLL_YAW=st["yaw"], SCROLL_SCALE=st["s"], RING_K=st["k"],
                       RING_C=tuple(st["ring"]), FRAME_RING_R=7.59 * st["k"])

    def __enter__(self):
        self.old = {k: getattr(SC, k) for k in self.kw}
        for k, v in self.kw.items():
            setattr(SC, k, v)
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            setattr(SC, k, v)


def new_state():
    return dict(c=tuple(SC.SCROLL_C), yaw=SC.SCROLL_YAW, s=SC.SCROLL_SCALE, k=SC.RING_K, ring=tuple(SC.RING_C))


def close(a, b, tol=TOL):
    return max(abs(float(x) - float(y)) for x, y in zip(a, b)) <= tol


def obj(name):
    return bpy.data.objects.get(name)


def which(ob, key, states):
    """'old' / 'new' when ob's transform matches that state for ``key`` ('scroll' or 'ring'), else None (the rings
    spin about z on their own: their turn is not compared)."""
    for tag, st in states.items():
        if key == "scroll":
            ok = close(ob.location, st["c"]) and abs(ob.rotation_euler.z - st["yaw"]) < 1e-4 and \
                close(ob.scale, (st["s"],) * 3, 1e-4) and close(ob.rotation_euler[:2], (0.0, 0.0), 1e-6)
        else:
            ok = close(ob.location, (st["ring"][0], st["ring"][1], SC.RING_Z)) and \
                close(ob.scale, (st["k"], st["k"], 1.0), 1e-4)
        if ok:
            return tag
    return None


# ---- meshes ------------------------------------------------------------------------------------------------------------
def local_co(me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def mesh_sig(me):
    """(vertex coordinates, loop vertex indices, loop totals, material indices, material names) of a mesh."""
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    return local_co(me), lv, lt, mi, [m.name if m else None for m in me.materials]


def same_mesh(a, b, tol=1e-5):
    sa, sb = mesh_sig(a), mesh_sig(b)
    if sa[0].shape != sb[0].shape or (len(sa[0]) and np.abs(sa[0] - sb[0]).max() > tol):
        return False
    return all(np.array_equal(x, y) for x, y in zip(sa[1:4], sb[1:4])) and sa[4] == sb[4]


def mesh_md5(me):
    h = hashlib.md5()
    co, lv, lt, mi, mats = mesh_sig(me)
    h.update(np.round(co, 5).tobytes())
    for x in (lv, lt, mi):
        h.update(x.tobytes())
    h.update(repr(mats).encode())
    h.update(repr(sorted((k, str(me[k])) for k in me.keys() if not k.startswith("_"))).encode())
    return h.hexdigest()


def open_edges(me):
    cnt = {}
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            k = (a, b) if a < b else (b, a)
            cnt[k] = cnt.get(k, 0) + 1
    return sum(1 for e in me.edges if cnt.get(tuple(sorted(e.vertices)), 0) < 2)


def tris(me):
    n = len(me.polygons)
    lt = [0] * n
    me.polygons.foreach_get("loop_total", lt)
    return sum(lt) - 2 * n


def remove_objects(obs):
    """Remove these objects (and their children) and free their meshes when nothing else uses them."""
    obs = list(obs)
    for o in list(obs):
        obs.extend(c for c in o.children_recursive if c not in obs)
    meshes, gone = set(), []
    for o in sorted(obs, key=lambda o: -len(o.children_recursive)):
        if o.name not in bpy.data.objects:
            continue
        if o.type == 'MESH' and o.data is not None:
            meshes.add(o.data)
        gone.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return sorted(gone)


# ---- the terrace top -----------------------------------------------------------------------------------------------------
def body_centre(st):
    """The rings' centre (state ``st``) in scroll.terrace.body's own frame (as patch_r12_areas Scroll.centre)."""
    root, body = obj(AREA_ROOT), obj(BODY)
    m = body.matrix_parent_inverse @ body.matrix_basis
    p = body.parent
    while p is not None and p != root:
        m = p.matrix_parent_inverse @ p.matrix_basis @ m
        p = p.parent
    c = m.inverted() @ Vector((st["ring"][0], st["ring"][1], 0.0))
    return c.x, c.y


def painted_body_mesh(st, name):
    """A new mesh: the terrace body as a fresh build makes it with placement ``st``: A.platform's plain body
    (scroll._terrace's arguments), then scroll.terrace_channel round that placement's ring centre."""
    coll = bpy.data.collections.new("~r15_scratch")
    x0, x1 = SC.TERRACE_X
    y0, y1 = SC.TERRACE_Y
    t = A.platform("~r15.terrace", coll, x1 - x0, y1 - y0, height=SC.TERRACE_H, style="plain", sink=0.8,
                   location=((x0 + x1) / 2, (y0 + y1) / 2, -SC.TERRACE_H))
    tb = bpy.data.objects[t.name + ".body"]
    me = tb.data.copy()
    me.name = name
    scratch = [t] + list(t.children_recursive)
    remove_objects(scratch)
    bpy.data.collections.remove(coll)
    tmp = bpy.data.objects.new("~r15.body", me)
    try:
        with Consts(st):
            SC.terrace_channel(tmp, body_centre(st))
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)
    return me


def write_mesh(dst, src):
    """Copy mesh ``src``'s geometry, attributes, materials and shading into ``dst`` (in place: same datablock)."""
    bm = bmesh.new()
    bm.from_mesh(src)
    bm.to_mesh(dst)
    bm.free()
    dst.materials.clear()
    for m in src.materials:
        dst.materials.append(m)
    mi = np.empty(len(src.polygons), np.int32)
    src.polygons.foreach_get("material_index", mi)
    dst.polygons.foreach_set("material_index", mi)
    sm = np.empty(len(src.polygons), bool)
    src.polygons.foreach_get("use_smooth", sm)
    dst.polygons.foreach_set("use_smooth", sm)
    dst.update()


# ---- the frame -----------------------------------------------------------------------------------------------------------
def frame_names():
    return [SC.FRAME] + [SC.FRAME + "." + p for p in ("posts", "rails", "bases", "emblems")]


def frame_objects_in_file():
    want = set(frame_names())
    return [o for o in bpy.data.objects if o.get("sect_item") == SC.FRAME_ITEM or o.name in want]


def fresh_frame_meshes():
    """{part: mesh copy} of the frame a fresh build makes now (built in a scratch collection, then removed)."""
    coll = bpy.data.collections.new("~r15_frame")
    tmp_root = bpy.data.objects.new("~r15.root", None)
    coll.objects.link(tmp_root)
    grp = SC.scroll_frame(coll, tmp_root)
    out = {}
    for c in grp.children:
        part = c.name[len(SC.FRAME) + 1:].split(".")[0]
        me = c.data.copy()
        me.name = "~r15.frame." + part
        out[part] = me
    remove_objects([tmp_root])
    bpy.data.collections.remove(coll)
    return out


def frame_matches(fresh):
    """True when the file's frame objects carry exactly the fresh build's meshes (and the Empty is in place)."""
    for part, me in fresh.items():
        o = obj(SC.FRAME + "." + part)
        if o is None or o.type != 'MESH' or not same_mesh(o.data, me):
            return False
    return len(fresh) == 4


# ---- views -------------------------------------------------------------------------------------------------------------
def world_pts(ob, step=1):
    co = local_co(ob.data)[::step]
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def world_box(ob):
    if ob.type != 'MESH' or not len(ob.data.vertices):
        return None
    P_ = world_pts(ob)
    return tuple(np.round(P_.min(0), 3).tolist()), tuple(np.round(P_.max(0), 3).tolist())


def inside(box, outer, tol=1e-3):
    return all(box[0][k] >= outer[0][k] - tol and box[1][k] <= outer[1][k] + tol for k in range(3))


def top_under(o, root):
    while o is not None and o.parent is not None and o.parent != root:
        o = o.parent
    return o if o is not None and o.parent == root else None


def area_points(root, tops=None, n=300):
    """{top-level owner under root: world points} of every mesh the area shows (evaluated instances included)."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for inst in dg.object_instances:
        o = inst.object
        if o.type != 'MESH':
            continue
        src = inst.parent.original if inst.is_instance and inst.parent is not None else o.original
        top = top_under(src, root)
        if top is None or (tops is not None and top.name not in tops):
            continue
        me = o.data
        k = len(me.vertices)
        if not k:
            continue
        co = np.empty(k * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)[::max(1, k // n)]
        A_ = np.array(inst.matrix_world)
        out.setdefault(top.name, []).append(co @ A_[:3, :3].T + A_[:3, 3])
    return {k: np.concatenate(v) for k, v in out.items()}


def site_view(sc, cam, f, res=RES):
    """The view the site shows at path frame ``f`` on a res[0] x res[1] screen: chase.cam's own place and orientation
    there (r15: no stop framing at the scroll; scroll.hold_turn is none, asserted in main), the client's field of view
    for that screen (camera-path.ts fovForAspect: the film's vertical FOV, widened to keep the film's horizontal FOV on
    narrower screens, at most MAX_FOV_Y), and on portrait screens (height over 1.15 x width) the picture shifted up by
    PORTRAIT_SHIFT of its height (scene.tsx)."""
    sc.frame_set(f)
    M = cam.matrix_world
    yaw, pitch = SC.hold_turn(f)
    R = Matrix.Rotation(yaw, 3, 'Z') @ M.to_3x3().normalized() @ Matrix.Rotation(pitch, 3, 'X')
    film = RES[0] / RES[1]
    tx_film = cam.data.sensor_width / 2.0 / cam.data.lens          # sensor fit AUTO, landscape: horizontal
    ty_film = tx_film / film
    aspect = res[0] / res[1]
    ty = min(max(tx_film / aspect, ty_film), max(ty_film, math.tan(math.radians(MAX_FOV_Y / 2.0))))
    shift = PORTRAIT_SHIFT if res[1] > res[0] * 1.15 else 0.0
    return dict(loc=np.array(M.translation), R=np.array(R), tx=ty * aspect, ty=ty, res=res, f=f, yaw=yaw,
                shift=shift)


def project(view, P_):
    """World points -> (x px, y px from the top, depth) on the view's screen."""
    L = (np.asarray(P_, dtype=float) - view["loc"]) @ view["R"]
    depth = -L[:, 2]
    d = np.where(np.abs(depth) < 1e-9, 1e-9, depth)
    W, H = view["res"]
    return np.stack([(1.0 + L[:, 0] / (d * view["tx"])) * W / 2.0,
                     (1.0 - L[:, 1] / (d * view["ty"])) * H / 2.0 - round(view["shift"] * H), depth], -1)


def in_frame(q, res):
    return (q[:, 0] >= 0) & (q[:, 0] <= res[0]) & (q[:, 1] >= 0) & (q[:, 1] <= res[1]) & (q[:, 2] > 0)


def silhouette_gap(q_disp, q_pav):
    """Smallest (pavilion's leftmost x - display's rightmost x) over the 10 px screen rows both cover (a row's
    pavilion edge is the leftmost of it and its two neighbours); negative = they overlap on screen."""
    rows = {}
    for x, y, z in q_pav:
        if z <= 0:
            continue
        r = int(y // 10)
        rows[r] = min(rows.get(r, 1e9), x)
    best = 1e9
    for x, y, z in q_disp:
        if z <= 0:
            continue
        r = int(y // 10)
        lim = min(rows.get(r + k, 1e9) for k in (-1, 0, 1))
        if lim < 1e9:
            best = min(best, lim - x)
    return best


def scroll_dims():
    """props.bamboo_slip_scroll's slip count, characters per slip, cell and arc."""
    W, H = SC.SCROLL_W, SC.SCROLL_H
    N = max(8, int(round(W / (H * 0.075))))
    pitch = W / N
    cell = pitch * 0.88 * 0.80
    rows = int(H * 0.84 / cell)
    d = max(1e-4, SC.SCROLL_CURVE * W)
    R = (W * W / 4 + d * d) / (2 * d)
    return N, rows, cell, R, math.asin(min(1.0, W / 2 / R))


def end_slip(view, js):
    """Screen y of the top and the bottom of the right end's slip, on its centre line."""
    N, rows, cell, R, half = scroll_dims()
    a = -half + 2 * half * (N - 0.5) / N
    x, y = R * math.sin(a), -R + R * math.cos(a)
    M = np.array(js.matrix_world)
    P_ = np.array([[x, y, SC.SCROLL_H / 2.0, 1.0], [x, y, -SC.SCROLL_H / 2.0, 1.0]])
    q = project(view, (P_ @ M.T)[:, :3])
    return float(q[0, 1]), float(q[1, 1])


def cells_at(view, js):
    """(slips wholly in frame, [character cell height px of each])."""
    N, rows, cell, R, half = scroll_dims()
    M = np.array(js.matrix_world)
    top = rows * cell / 2.0
    W, H = view["res"]
    seen, px = [], []
    for i in range(N):
        a = -half + 2 * half * (i + 0.5) / N
        x, y = R * math.sin(a), -R + R * math.cos(a)
        P_ = np.array([[x, y, top - 0.5 * cell, 1.0], [x, y, top - 1.5 * cell, 1.0], [x, y, -top + 0.5 * cell, 1.0]])
        q = project(view, (P_ @ M.T)[:, :3])
        if (q[:, 2] > 0).all() and all(0 <= q[k, 0] <= W and 0 <= q[k, 1] <= H for k in (0, 2)):
            seen.append(i)
            px.append(abs(q[0, 1] - q[1, 1]))
    return seen, px


# ---- checks --------------------------------------------------------------------------------------------------------------
def source_check(fail):
    st = new_state()
    ok = close(st["c"], FIRST["c"], 1e-9) and abs(st["yaw"] - FIRST["yaw"]) < 1e-12 and abs(st["s"] - FIRST["s"]) < 1e-12 \
        and close(st["ring"], FIRST["ring"], 1e-9) and abs(st["k"] - FIRST["k"]) < 1e-12 \
        and tuple(SC.HOLD_TURN) == (0.0, 0.0) and SC.hold_turn(HOLD) == (0.0, 0.0)
    log("source: scroll.py places the scroll at %s, turn %.2f deg, scale %.3f, rings at (%.2f, %.2f) x %.3f, client "
        "turn %s" % (st["c"], math.degrees(st["yaw"]), st["s"], st["ring"][0], st["ring"][1], st["k"],
                     tuple(SC.HOLD_TURN)), "= the first build, ok" if ok else "NOT the first build %s" % FIRST)
    if not ok:
        fail.add("scroll.py is not the restored design")


def frame_fit_check(fail):
    """The sill's top and the top rail's bottom meet the slips (scroll frame z, unscaled) (patch_r5_scroll)."""
    js = obj(SCROLL)
    sl = [c for c in js.children if c.type == 'MESH' and c.name.startswith(SCROLL + ".slips")]
    fr = obj(SC.FRAME)
    Mi = fr.matrix_world.inverted()
    zs = [(Mi @ (o.matrix_world @ v.co)).z for o in sl for v in o.data.vertices]
    lv = SC._frame_levels()
    d0, d1 = min(zs) - lv["sill"][1], lv["top"][0] - max(zs)
    ok = abs(d0) < 0.02 and abs(d1) < 0.02
    log("frame fit: slips z %.3f .. %.3f (scroll frame); gap to the sill top %.3f, to the top rail %.3f" % (
        min(zs), max(zs), d0, d1), "ok" if ok else "BAD")
    if not ok:
        fail.add("frame does not meet the slips")


def post_plinth_check(fail):
    (t0, t1), (s0, s1) = SC.ring_bands()
    lo, hi = t1 + 0.02, s0 - 0.02
    fp = SC.frame_points()
    zg = SC._ground_z()
    for side, a in ((-1, fp["a_l"]), (1, fp["a_r"])):
        off = SC.FRAME_POST_GAP + SC.FRAME_POST_R
        x, y = SC._arc_xy(a, off)
        tang = (math.cos(a), -math.sin(a))
        back = (math.sin(a), math.cos(a))
        w, d = SC.FRAME_PLINTH[0] / 2.0, SC.FRAME_PLINTH[1] / 2.0
        rs = []
        for su in (-1, 1):
            for sv in (-1, 1):
                q = (x + su * w * tang[0] + sv * d * back[0], y + su * w * tang[1] + sv * d * back[1], zg)
                X, Y, _ = SC.scroll_to_root(q)
                rs.append(math.hypot(X - SC.RING_C[0], Y - SC.RING_C[1]))
        X, Y, _ = SC.scroll_to_root((x, y, zg))
        ok = lo <= min(rs) and max(rs) <= hi
        log("post", "left" if side < 0 else "right", "at (%.2f, %.2f) in scroll.root's frame, arc angle %.2f deg; "
            "plinth corners %.2f .. %.2f m from the ring centre (free paving %.2f .. %.2f)" % (
                X, Y, math.degrees(a), min(rs), max(rs), lo, hi), "ok" if ok else "ON A RING BAND")
        if not ok:
            fail.add("post plinth on a ring band")


def ground_check(root, fail, tol=0.02):
    """Rays straight down from each plinth's four corners (pulled 5 cm in) meet the paving within ``tol`` of the
    plinth's bottom .. the paving top."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    M, Mi = root.matrix_world, root.matrix_world.inverted()
    down = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    skip = set(frame_names()) | {SCROLL} | {c.name for c in obj(SCROLL).children_recursive}
    fp = SC.frame_points()
    zb = SC.scroll_to_root((0.0, 0.0, SC._ground_z() - SC.FRAME_PLINTH[3]))[2]   # plinth bottom (root z)
    bad, hits = [], []
    for side, a in ((-1, fp["a_l"]), (1, fp["a_r"])):
        off = SC.FRAME_POST_GAP + SC.FRAME_POST_R
        x, y = SC._arc_xy(a, off)
        tang = (math.cos(a), -math.sin(a))
        back = (math.sin(a), math.cos(a))
        w, d = SC.FRAME_PLINTH[0] / 2.0 - 0.05 / SC.SCROLL_SCALE, SC.FRAME_PLINTH[1] / 2.0 - 0.05 / SC.SCROLL_SCALE
        for su in (-1, 1):
            for sv in (-1, 1):
                X, Y, _ = SC.scroll_to_root((x + su * w * tang[0] + sv * d * back[0],
                                             y + su * w * tang[1] + sv * d * back[1], 0.0))
                o = M @ Vector((X, Y, zb + 0.5))
                hit = None
                for _ in range(8):
                    ok, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, down, distance=3.5)
                    if not ok:
                        break
                    if ob.original.name in skip:
                        o = loc + down * 1e-3
                        continue
                    hit = ((Mi @ loc).z, ob.original.name)
                    break
                hits.append(hit)
                if hit is None or not (zb - tol <= hit[0] <= zb + SC.FRAME_PLINTH[3] * SC.SCROLL_SCALE + tol) or \
                        hit[1] != BODY:
                    bad.append(((round(X, 2), round(Y, 2)), hit))
    log("ground: plinth bottoms at z %.3f; under the corners: %s" % (zb, sorted({(h[1], round(h[0], 3)) if h else None
                                                                                 for h in hits}, key=str)),
        "all 8 corners stand on the paving, ok" if not bad else "OFF THE PAVING %s" % bad)
    if bad:
        fail.add("frame feet not on the terrace")


def ring_check(root, fail):
    """The rings lie on the terrace and off the axis walk; nothing standing on the paving sits on a band; the floor
    just outside each band is the paving."""
    (t0, t1), (s0, s1) = SC.ring_bands()
    rx, ry = SC.RING_C
    x0, x1 = SC.TERRACE_X[0] + 0.6, SC.TERRACE_X[1] - 0.6
    y0, y1 = SC.TERRACE_Y[0], SC.TERRACE_Y[1] - 0.6
    walk_x0 = SC.PAV[0] - 2.0
    ok = rx - s1 >= x0 and rx + s1 <= min(x1, walk_x0) and ry - s1 >= y0 and ry + s1 <= y1
    log("rings: centre (%.2f, %.2f), scale %.3f, bands %.3f..%.3f and %.3f..%.3f m; reach x %.2f..%.2f y %.2f..%.2f "
        "(terrace inside the rails x %.1f..%.1f y %.1f..%.1f, axis walk from x %.1f)" % (
            rx, ry, SC.RING_K, t0, t1, s0, s1, rx - s1, rx + s1, ry - s1, ry + s1, x0, x1, y0, y1, walk_x0),
        "ok" if ok else "OFF THE TERRACE / ON THE WALK")
    if not ok:
        fail.add("rings off the terrace or under the walk")
    for nm in RINGS:
        o = obj(nm)
        if not o.data.name.endswith(".v%d" % P.RUNE_KEY_VERSION):
            fail.add("%s's mesh %s is not the raised band (v%d)" % (nm, o.data.name, P.RUNE_KEY_VERSION))
    skip = {SCROLL, SC.FRAME, SC.K + ".terrace", SC.K + ".walk", SC.K + ".approach"} | set(RINGS)
    Mi = np.array(root.matrix_world.inverted())
    on = {}
    for top, P_ in area_points(root, n=3000).items():
        if top in skip:
            continue
        L = P_ @ Mi[:3, :3].T + Mi[:3, 3]
        L = L[L[:, 2] <= 0.5]               # what stands on the paving: its vertices within 0.5 m of it
        if not len(L):
            continue
        r = np.hypot(L[:, 0] - rx, L[:, 1] - ry)
        for a, b in ((t0, t1), (s0, s1)):
            m = (r > a - 0.05) & (r < b + 0.05)
            if m.any():
                on[top] = round(float(r[m].min()), 2)
    log("rings: pieces standing on a band:", sorted(on.items()) if on else "none, ok")
    if on:
        fail.add("pieces stand on the ring bands: %s" % sorted(on))
    # the floor just outside each band (patch_r12_libs Rune.check): rays down the ring's axis 1 cm past its outer edge
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    for nm in RINGS:
        o = obj(nm)
        c = local_co(o.data)
        r_out = float(np.hypot(c[:, 0], c[:, 1]).max())
        W = o.matrix_world
        Wi = W.inverted()
        zl, miss, names = [], 0, set()
        for k in range(72):
            a = 2.0 * math.pi * k / 72
            pw = W @ Vector(((r_out + 0.01) * math.cos(a), (r_out + 0.01) * math.sin(a), 0.5))
            qw = W @ Vector(((r_out + 0.01) * math.cos(a), (r_out + 0.01) * math.sin(a), -0.5))
            d = qw - pw
            hit, loc, nor, fi, ob, mx = sc.ray_cast(dg, pw, d.normalized(), distance=d.length)
            if not hit:
                miss += 1
                continue
            zl.append((Wi @ loc).z)
            names.add(ob.original.name)
        zl = np.array(zl) if zl else np.zeros(0)
        bad = int(((zl < -P.RUNE_SINK + 0.002) | (zl > P.RUNE_TOP - 0.02)).sum()) if len(zl) else 0
        log("rings: %s: the floor just outside its band at z %s (%d of 72 rays, on %s)" % (
            nm, "%.4f..%.4f" % (zl.min(), zl.max()) if len(zl) else "-", len(zl), sorted(names)),
            "ok" if len(zl) >= 70 and not bad else "BAD")
        if len(zl) < 70 or bad:
            fail.add("%s: the floor next to its band is not the paving (%d bad, %d misses)" % (nm, bad, miss))


def channel_check(fail):
    """The terrace top is one surface at its height: dark stone exactly under the channel round the rings' centre
    (scroll.channel_radii), the paving everywhere else (patch_r12_areas Scroll.check); the script band lies inside the
    channel."""
    body = obj(BODY)
    V = local_co(body.data)
    tree = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(p.vertices) for p in body.data.polygons])
    mi = [p.material_index for p in body.data.polygons]
    zt = V[:, 2].max()
    cx, cy = body_centre(new_state())
    c0, c1 = SC.channel_radii()
    cosh = math.cos(math.pi / SC.CHANNEL_SEGS)
    bad, holes, n = 0, 0, 0
    xs, ys = V[:, 0], V[:, 1]
    for k in range(1440):
        a = 2 * math.pi * (k + 0.5) / 1440
        for r in np.arange(0.3, c1 + 3.0, 0.07):
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if not (xs.min() + 0.05 < x < xs.max() - 0.05 and ys.min() + 0.05 < y < ys.max() - 0.05):
                continue
            n += 1
            loc, nor, fi, d = tree.ray_cast(Vector((x, y, zt + 1.0)), Vector((0, 0, -1)), 2.0)
            if loc is None or abs(loc.z - zt) > 1e-4:
                holes += 1
                continue
            if c0 + 0.005 < r < c1 * cosh - 0.005:
                bad += mi[fi] != 2
            elif r < c0 * cosh - 0.005 or r > c1 + 0.005:
                bad += mi[fi] != 1
    # dark faces anywhere off the channel (the old one's place included)
    off = 0
    for p in body.data.polygons:
        if p.material_index != 2:
            continue
        r = math.hypot(p.center.x - cx, p.center.y - cy)
        off += not (c0 * cosh - 0.01 <= r <= c1 + 0.01)
    dark = sum(1 for m in mi if m == 2)
    (t0, t1), (s0, s1) = SC.ring_bands()
    ring = obj(RINGS[0])
    co = local_co(ring.data)
    rr = np.hypot(co[:, 0], co[:, 1]) * ring.scale.x
    inside_ok = c0 + 0.01 <= rr.min() and rr.max() <= c1 - 0.01 and close(ring.location[:2], SC.RING_C, 1e-4)
    log("channel: the terrace top is one surface at its height (%d samples, %d holes, %d wrong stone); %d dark faces, "
        "%d of them off the channel r %.3f..%.3f round (%.2f, %.2f) (body frame); the script band spans r %.3f..%.3f" % (
            n, holes, bad, dark, off, c0, c1, cx, cy, rr.min(), rr.max()),
        "ok" if not (holes or bad or off) and dark == SC.CHANNEL_SEGS and inside_ok else "BAD")
    if holes or bad or off or dark != SC.CHANNEL_SEGS:
        fail.add("terrace top: %d holes, %d wrong stone, %d dark faces off the channel, %d dark faces" % (
            holes, bad, off, dark))
    if not inside_ok:
        fail.add("the script band (r %.3f..%.3f) does not lie inside the channel (%.3f..%.3f)" % (
            rr.min(), rr.max(), c0, c1))


def clash_check(display, fail):
    """No scene mesh cuts into the display (BVH overlap), apart from the paving under the plinths; logs every piece
    within NEAR m."""
    dg = bpy.context.evaluated_depsgraph_get()
    names = {o.name for o in display}
    found, cut = [], []
    data = []
    for ob in display:
        P_ = world_pts(ob)
        bvh = BVHTree.FromPolygons([Vector(p) for p in P_], [tuple(p.vertices) for p in ob.data.polygons])
        data.append((ob, P_, bvh, P_.min(0) - NEAR, P_.max(0) + NEAR))
    for inst in dg.object_instances:
        o2 = inst.object
        if o2.type != 'MESH':
            continue
        src = inst.parent.original if inst.is_instance and inst.parent is not None else o2.original
        if o2.original.name in names or src.name in names:
            continue
        M = inst.matrix_world
        cs = np.array([tuple(M @ Vector(c)) for c in o2.bound_box])
        lo2, hi2 = cs.min(0), cs.max(0)
        hits = [d for d in data if (lo2 <= d[4]).all() and (hi2 >= d[3]).all()]
        if not hits:
            continue
        me = o2.data
        if not len(me.polygons):
            continue
        P2 = [M @ v.co for v in me.vertices]
        bvh2 = BVHTree.FromPolygons(P2, [tuple(p.vertices) for p in me.polygons])
        label = o2.original.name + ("" if not inst.is_instance else " (in %s)" % src.name)
        for ob, P_, bvh, lo, hi in hits:
            if bvh.overlap(bvh2):
                if not any(label.startswith(k) for k in CLASH_OK):
                    cut.append((ob.name, label))
                continue
            ds = [h[3] for h in (bvh2.find_nearest(Vector(p), NEAR) for p in P_[::3]) if h[0] is not None]
            if ds:
                found.append((round(min(ds), 3), ob.name, label))
    for d, a, b in sorted(set(found)):
        log("near %.3f m: %s - %s" % (d, a, b))
    if not found:
        log("near: nothing within %.1f m of the display" % NEAR)
    log("clash: display pieces cut by scene pieces:", sorted(set(cut)) if cut else "none (the paving under the "
        "plinths is by design), ok")
    if cut:
        fail.add("scene pieces cut into the display: %s" % sorted(set(cut))[:6])


def flight_check(display, fail):
    sc = bpy.context.scene
    cam = obj(CAM)
    P_ = np.concatenate([world_pts(o) for o in display])
    lo, hi = P_.min(0), P_.max(0)
    verts, faces, k = [], [], 0
    for o in display:
        W = world_pts(o)
        verts += [Vector(p) for p in W]
        faces += [tuple(k + i for i in p.vertices) for p in o.data.polygons]
        k += len(W)
    bvh = BVHTree.FromPolygons(verts, faces)
    best, near = (1e9, None), (1e9, None)
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        c = np.array(cam.matrix_world.translation)
        d = float(np.linalg.norm(np.maximum(np.maximum(lo - c, c - hi), 0.0)))
        if d < best[0]:
            best = (d, f)
        if d < FLIGHT_CLEAR + 15.0:
            hit = bvh.find_nearest(Vector(c.tolist()), 100.0)
            if hit[0] is not None and hit[3] < near[0]:
                near = (hit[3], f)
    log("flight: closest %.1f m from the scroll and its frame (frame %s); %.1f m from their box (frame %d)" % (
        near[0], near[1], best[0], best[1]), "ok" if near[0] >= FLIGHT_CLEAR else "TOO CLOSE (< %.1f)" % FLIGHT_CLEAR)
    if near[0] < FLIGHT_CLEAR:
        fail.add("the flight passes %.1f m from the scroll" % near[0])


def hold_and_flight_view(root, display, fail):
    sc = bpy.context.scene
    cam = obj(CAM)
    js = obj(SCROLL)
    pav_tops = {SC.K + ".pavilion", SC.K + ".plaque", SC.K + ".lantern", SC.K + ".lantern.001"}
    slips = [c for c in js.children if c.type == 'MESH' and c.name.startswith(SCROLL + ".slips")]
    pav = np.concatenate(list(area_points(root, pav_tops).values()))
    Ps = np.concatenate([world_pts(o, 2) for o in slips])
    Pa = np.concatenate([world_pts(o, 3) for o in display])
    v = site_view(sc, cam, HOLD)
    Mi = np.array(root.matrix_world.inverted())
    cl = Mi[:3, :3] @ v["loc"] + Mi[:3, 3]
    fw0 = Mi[:3, :3] @ (-np.array(cam.matrix_world.to_3x3().normalized())[:, 2])
    h0 = math.degrees(math.atan2(fw0[1], fw0[0]))
    ok = math.dist(cl, SC.HOLD_CAM) < 0.05 and abs(h0 - math.degrees(SC.HOLD_HEADING)) < 0.05
    log("hold %d: chase.cam at (%.2f, %.2f, %.2f) heading %.2f deg in %s's frame (scroll.HOLD_CAM %s, HOLD_HEADING "
        "%.2f); the site shows this view itself (no stop framing)" % (
            HOLD, cl[0], cl[1], cl[2], h0, AREA_ROOT, SC.HOLD_CAM, math.degrees(SC.HOLD_HEADING)),
        "agree" if ok else "DIFFER: the camera moved, update scroll.HOLD_CAM / HOLD_HEADING")
    if not ok:
        fail.add("chase.cam at the hold differs from scroll.HOLD_CAM / HOLD_HEADING")
    # the scroll's face against the view, in plan (0 = parallel to the picture)
    n = Vector(np.array(js.matrix_world.to_3x3()) @ np.array((0.0, -1.0, 0.0)))
    back = Vector(v["R"][:, 2].tolist())
    plan = math.degrees(Vector((n.x, n.y, 0)).normalized().angle(Vector((back.x, back.y, 0)).normalized()))
    log("hold %d: the slips' face is %.1f deg off parallel to the picture in plan (the first build's; r10 had 1.3, r2 "
        "~30)" % (HOLD, plan))
    for res in (RES, RES_SMALL):
        v = site_view(sc, cam, HOLD, res)
        W, H = res
        k = W / RES[0]
        q = project(v, Ps)
        right = q[:, 0].max()
        top, bot = end_slip(v, js)
        seen, px = cells_at(v, js)
        log("hold %d %dx%d: the slips from x %.0f to %.0f (%.0f %% of their points in frame), y %.0f .. %.0f; the right "
            "end's slip y %.0f .. %.0f; %d of %d slips wholly in frame, a character cell %.1f .. %.1f px tall" % (
                HOLD, W, H, q[:, 0].min(), right, 100.0 * in_frame(q, res).mean(), q[:, 1].min(), q[:, 1].max(), top,
                bot, len(seen), scroll_dims()[0], min(px) if px else 0, max(px) if px else 0))
        if res == RES:
            dev = (right - ORIG_RIGHT_PX, top - ORIG_TOP_PX, bot - ORIG_BOTTOM_PX)
            ok = max(abs(x) for x in dev) <= ORIG_TOL_PX and q[:, 0].min() < 0
            log("hold %d: against the owner's screenshot (right end x %.0f, its top %.0f, bottom %.0f, the rest past "
                "the left edge): %+.0f, %+.0f, %+.0f px" % ((HOLD, ORIG_RIGHT_PX, ORIG_TOP_PX, ORIG_BOTTOM_PX) + dev),
                "ok" if ok else "DOES NOT READ LIKE IT (tolerance %.0f px)" % ORIG_TOL_PX)
            if not ok:
                fail.add("the hold does not match the first build's framing: %s px" % [round(x) for x in dev])
        for o in display:
            if o in slips:
                continue
            qo = project(v, world_pts(o, 2))
            log("hold %d %dx%d: %-32s x %6.0f .. %6.0f, y %5.0f .. %5.0f, %3.0f %% in frame" % (
                HOLD, W, H, o.name, qo[:, 0].min(), qo[:, 0].max(), qo[:, 1].min(), qo[:, 1].max(),
                100.0 * in_frame(qo, res).mean()))
        qp = project(v, pav)
        gap = silhouette_gap(project(v, Pa), qp)
        ok = gap >= PAV_GAP_PX * k
        log("hold %d %dx%d: the display keeps %.0f px left of the pavilion's silhouette (pavilion x %.0f .. %.0f)" % (
            HOLD, W, H, gap, qp[:, 0].min(), qp[:, 0].max()),
            "ok" if ok else "OVERLAPS / CROWDS IT (< %.0f px)" % (PAV_GAP_PX * k))
        if not ok:
            fail.add("the scroll crowds the pavilion at the hold (%dx%d)" % res)
    v = site_view(sc, cam, HOLD, RES_PHONE)
    q = project(v, Ps)
    qa = project(v, Pa)
    qp = project(v, pav)
    log("hold %d %dx%d (phone, no portrait turn): the slips x %.0f .. %.0f, %.0f %% of their points in frame; the "
        "display %.0f %% in frame; the pavilion x %.0f .. %.0f" % (
            HOLD, RES_PHONE[0], RES_PHONE[1], q[:, 0].min(), q[:, 0].max(), 100.0 * in_frame(q, RES_PHONE).mean(),
            100.0 * in_frame(qa, RES_PHONE).mean(), qp[:, 0].min(), qp[:, 0].max()))
    worst = (1e9, None, 1e9)
    Pd = np.concatenate([world_pts(o, 6) for o in display])
    for f in APPROACH + DEPART:
        v = site_view(sc, cam, f)
        q = project(v, Pd)
        qs = project(v, Ps)
        qf = q[q[:, 2] > 0]
        rng = "x %6.0f .. %6.0f y %5.0f .. %5.0f" % (qf[:, 0].min(), qf[:, 0].max(), qf[:, 1].min(),
                                                    qf[:, 1].max()) if len(qf) else "behind the camera"
        if f in APPROACH:
            qp = project(v, pav)
            g, gs = silhouette_gap(q, qp), silhouette_gap(qs, qp)
            if g < worst[0]:
                worst = (g, f, gs)
        sn, spx = cells_at(v, js)
        log("%s %d: display %s, %3.0f %% in frame (slips %3.0f %%), %2d slips whole (cells %s px)%s" % (
            "approach" if f in APPROACH else "depart", f, rng, 100 * in_frame(q, RES).mean(),
            100 * in_frame(qs, RES).mean(), len(sn), "%.1f .. %.1f" % (min(spx), max(spx)) if spx else "-",
            ", %.0f px left of the pavilion (the slips alone %.0f)" % (g, gs) if f in APPROACH else ""))
    ok = worst[0] >= -APPROACH_OVERLAP_PX
    log("approach: closest the display comes to the pavilion on screen %.0f px (frame %s; the slips alone %.0f)" % worst,
        "ok (it may touch it by %.0f px)" % APPROACH_OVERLAP_PX if ok else "OVERLAPS IT")
    if not ok:
        fail.add("the scroll overlaps the pavilion on the approach (%.0f px)" % -worst[0])


# ---- main ----------------------------------------------------------------------------------------------------------------
def digest(names):
    h = hashlib.md5()
    for n in sorted(set(names)):
        ob = obj(n)
        if ob is None:
            h.update(("gone:" + n).encode())
            continue
        h.update(n.encode())
        if n in RINGS:       # they spin with scene time: place, size and mesh only
            h.update(np.round(np.array(tuple(ob.location) + tuple(ob.scale)), 6).tobytes())
        else:
            h.update(np.round(np.array(ob.matrix_basis), 6).tobytes())
        h.update(repr(ob.parent.name if ob.parent else None).encode())
        if ob.type == 'MESH':
            h.update(ob.data.name.encode())
            h.update(mesh_md5(ob.data).encode())
    return h.hexdigest()


def main():
    t0 = time.time()
    dry = options()
    fail = Fail()
    sc = bpy.context.scene
    keep = (sc.frame_current, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage)
    root, js, fr, body = obj(AREA_ROOT), obj(SCROLL), obj(SC.FRAME), obj(BODY)
    if root is None or js is None or fr is None or body is None or obj(CAM) is None:
        raise SystemExit("patch_r15_scroll_restore: no %s / %s / %s / %s / %s: is this out/sect_chase.blend?" % (
            AREA_ROOT, SCROLL, SC.FRAME, BODY, CAM))
    if obj(MOTES) is not None:
        raise SystemExit("patch_r15_scroll_restore: %s is still in the file: run sect/patch_r21_motes.py first" % MOTES)
    source_check(fail)
    rings = [obj(n) for n in RINGS]
    for nm, ob in [(SCROLL, js), (SC.FRAME, fr)] + list(zip(RINGS, rings)):
        if ob is None or ob.parent != root:
            fail.add("%s missing or not under %s" % (nm, AREA_ROOT))
    if fail:
        log("NOT SAVED: %d problems" % len(fail))
        raise SystemExit(1)
    coll = fr.users_collection[0]
    states = dict(old=R10, new=new_state())
    st = {SCROLL: which(js, "scroll", states), SC.FRAME: which(fr, "scroll", states)}
    for nm, ob in zip(RINGS, rings):
        st[nm] = which(ob, "ring", states)
    # the terrace: the r12 painting round the r10 rings, or this one
    me_old = painted_body_mesh(R10, "~r15.body.old")
    me_new = painted_body_mesh(states["new"], "~r15.body.new")
    st[BODY] = "new" if same_mesh(body.data, me_new) else "old" if same_mesh(body.data, me_old) else None
    log("terrace: the file's top has %d faces, %d dark; the r12 painting round the r10 rings %d faces, this one %d" % (
        len(body.data.polygons), sum(1 for p in body.data.polygons if p.material_index == 2), len(me_old.polygons),
        len(me_new.polygons)))
    bpy.data.meshes.remove(me_old)
    fresh = fresh_frame_meshes()
    frame_ok = st[SC.FRAME] == "new" and frame_matches(fresh)
    log("state:", st, "| frame meshes", "= a fresh build" if frame_ok else "to rebuild",
        "| new placement: centre %s, turn %.2f deg, scale %.3f; rings at (%.2f, %.2f) x %.3f" % (
            tuple(round(v, 3) for v in SC.SCROLL_C), math.degrees(SC.SCROLL_YAW), SC.SCROLL_SCALE, SC.RING_C[0],
            SC.RING_C[1], SC.RING_K))
    if any(v is None for v in st.values()):
        bad = {k: (tuple(round(c, 3) for c in obj(k).location), round(math.degrees(obj(k).rotation_euler.z), 2),
                   round(obj(k).scale.x, 4)) for k, v in st.items() if v is None}
        for m in list(fresh.values()) + [me_new]:
            bpy.data.meshes.remove(m)
        fail.add("neither the round-12 file (r10 placement) nor this design (location, turn deg, scale): %s" % bad)
        log("NOT SAVED: the file is not in a state this patch knows")
        raise SystemExit(1)
    todo = not (all(v == "new" for v in st.values()) and frame_ok)
    sc.frame_set(keep[0])
    js_kids = [c for c in js.children_recursive if c.type == 'MESH']
    kids0 = {c.name: (c.data.name, mesh_md5(c.data), c.data.get(P.R12_TAG)) for c in js_kids}
    for nm, (mn, md5, tag) in sorted(kids0.items()):
        log("scroll mesh %s: %s md5 %s tag %s" % (nm, mn, md5, tag))
    display_old = js_kids + [c for c in fr.children_recursive if c.type == 'MESH']
    before = {o.name: world_box(o) for o in display_old + rings + [body]}
    n_obj = len(bpy.data.objects)

    if todo:
        # 1. the scroll
        js.location = SC.SCROLL_C
        js.rotation_euler = (0.0, 0.0, SC.SCROLL_YAW)
        js.scale = (SC.SCROLL_SCALE,) * 3
        # 2. its frame, rebuilt
        gone = remove_objects(frame_objects_in_file())
        log("removed the frame:", gone)
        for m in list(bpy.data.meshes):
            if m.users == 0 and any(m.name == w or m.name.startswith(w + ".") for w in frame_names()):
                bpy.data.meshes.remove(m)
        grp = SC.scroll_frame(coll, root)
        log("rebuilt the frame:", sorted([grp.name] + [c.name for c in grp.children]))
        # 3. the rings
        for ob in rings:
            ob.location = (SC.RING_C[0], SC.RING_C[1], SC.RING_Z)
            ob.scale = (SC.RING_K, SC.RING_K, 1.0)
        # 4. the channel in the terrace top
        if st[BODY] != "new":
            write_mesh(body.data, me_new)
            log("terrace: painted the channel round the new ring centre: %d faces, %d dark" % (
                len(body.data.polygons), sum(1 for p in body.data.polygons if p.material_index == 2)))
        bpy.context.view_layer.update()
    for m in list(fresh.values()) + [me_new]:
        bpy.data.meshes.remove(m)

    fr = obj(SC.FRAME)
    got = sorted([fr.name] + [o.name for o in fr.children])
    if got != sorted(frame_names()) or len(bpy.data.objects) != n_obj:
        fail.add("frame names %s (wanted %s), objects %d -> %d: a name was taken" % (
            got, sorted(frame_names()), n_obj, len(bpy.data.objects)))
    for o in fr.children:
        if o.type == 'MESH' and o.data.name != o.name:
            fail.add("%s's mesh is called %s" % (o.name, o.data.name))
    if any("~r15" in o.name for o in bpy.data.objects) or any("~r15" in m.name for m in bpy.data.meshes) or \
            any("~r15" in c.name for c in bpy.data.collections):
        fail.add("scratch data left in the file")
    log("objects %d -> %d (expected +0)" % (n_obj, len(bpy.data.objects)))
    frame_obs = [obj(n) for n in frame_names()[1:]]
    display = js_kids + frame_obs
    for ob in frame_obs:
        oe = open_edges(ob.data)
        log("mesh", ob.name, "tris", tris(ob.data), "slots", [s.material.name if s.material else None
                                                             for s in ob.material_slots],
            "closed" if oe == 0 else "OPEN (%d edges)" % oe)
        if oe:
            fail.add("%s is open" % ob.name)
    for c in js_kids:
        now = (c.data.name, mesh_md5(c.data), c.data.get(P.R12_TAG))
        if now != kids0[c.name]:
            fail.add("%s's mesh changed: %s -> %s" % (c.name, kids0[c.name], now))
    cut = [c.name for c in js_kids if c.name.endswith((".slips", ".script")) and c.data.get(P.R12_TAG) != "cut"]
    log("scroll meshes unchanged; the script cut into the slips (props.SLIPS_CUT):", "yes" if not cut else
        "NOT CUT %s" % cut)
    if cut:
        fail.add("the slips' script is not cut: %s" % cut)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    frame_fit_check(fail)
    post_plinth_check(fail)
    ground_check(root, fail)
    ring_check(root, fail)
    channel_check(fail)
    clash_check(display, fail)
    flight_check(display, fail)
    hold_and_flight_view(root, display, fail)

    # the checks scrubbed the timeline: back to the file's own frame and render size
    sc.frame_set(keep[0])
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = keep[1:]
    moved = []
    for o in display + rings + [body]:
        nb, ob_ = world_box(o), before.get(o.name)
        ok = ob_ is not None and nb is not None and inside(nb, ob_, 0.01)
        if not ok:
            moved.append(o.name)
        log("box", o.name, "before", ob_, "after", nb, "inside the old box" if ok else "LEAVES the old box")
    touched = [SCROLL] + [c.name for c in js_kids] + frame_names() + list(RINGS) + [BODY]
    log("DIGEST", digest(touched))
    if fail:
        log("NOT SAVED: %d checks failed:" % len(fail))
        for f in fail:
            log("  -", f)
        raise SystemExit(1)
    if moved:
        log("CACHES needs audit: %d boxes moved %s - run export_web.py -- audit --profile full, then chunks,meta (the "
            "'resume' hotspot moved), then bake_web.py bakefull for scroll and the backdrop, then tools/sect_pack.py"
            % (len(moved), moved))
    else:
        log("CACHES ok: every box inside its old one%s" % ("; re-bake scroll and the backdrop, then pack" if todo
                                                          else "; nothing changed"))
    if not todo:
        log("nothing changed: not saving (%.1f s)" % (time.time() - t0))
        return
    if dry:
        log("DRY_RUN: checks passed, not saving (%.1f s)" % (time.time() - t0))
        return
    bpy.ops.wm.save_mainfile()
    log("saved", bpy.data.filepath, "objects", len(bpy.data.objects), "(%.1f s)" % (time.time() - t0))


if __name__ == "__main__":
    main()
