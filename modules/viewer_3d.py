"""
modules/viewer_3d.py  —  AI Gesture-Controlled 3D Object Viewer.

Pinch-zoom logic:
  - Hold thumb + index PINCHED (gap < threshold) for 2 seconds → armed
  - While armed: EXPAND fingers  → zoom in  (continuous, tracks distance)
  - Hold thumb + index SPREAD (gap > threshold) for 2 seconds → armed
  - While armed: COMPRESS fingers → zoom out (continuous, tracks distance)

No webcam background — clean dark scene.
No voice instruction text on screen.
"""

import sys, os, math, time, threading
import cv2
import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

try:
    from OpenGL.GL import *; from OpenGL.GLU import *; from OpenGL.GLUT import *
except ImportError:
    print("PyOpenGL not found.  pip install PyOpenGL PyOpenGL_accelerate"); sys.exit(1)

try:
    import trimesh; _TRIMESH_OK = True
except ImportError:
    _TRIMESH_OK = False

try:
    from PIL import Image as _PImg; _PIL_OK = True
except ImportError:
    _PIL_OK = False

from core.config import (
    MODEL_3D_W as WIDTH, MODEL_3D_H as HEIGHT,
    ROT_GAIN, SCALE_GAIN, MIN_SCALE, MAX_SCALE, TRANSLATE_GAIN,
    MP_DETECT_CONF, MP_TRACK_CONF,
)
from utils.mp_compat import HandTracker, DrawLandmarks
from utils.gesture import fingers_up, classify_gesture, palm_center_px, inter_palm_distance

try:
    from ml.gesture_cnn import GestureClassifier; _CNN_OK = True
except ImportError:
    _CNN_OK = False

MODEL_DIR    = os.path.join(_PROJECT_ROOT, "3d_module", "models")
GLOBE_OBJ    = os.path.join(MODEL_DIR, "Globe.obj")
TEXTURE_PATH = os.path.join(MODEL_DIR, "Albedo-diffuse.jpg")

# ── Transform state ───────────────────────────────────────────────────────────
rot_x = rot_y = 0.0
tx = ty = 0.0
scale = 1.0
auto_rot_y = 0.0
prev_cx = prev_cy = None
prev_tx_ref = prev_ty_ref = None
mode_label = "No hand — auto-rotate"
cnn_label  = ""; cnn_conf = 0.0
fps_3d = 0; _last_time = time.time()
_current_3d_type = "globe"

# ── Pinch-zoom state machine ──────────────────────────────────────────────────
# State: "idle" | "pinch_arming" | "pinch_armed" | "spread_arming" | "spread_armed"
_pinch_state       = "idle"
_pinch_arm_start   = 0.0    # time we started holding the pinch/spread position
_pinch_arm_dist    = 0.0    # distance at the moment of arming
_pinch_prev_dist   = 0.0    # distance last frame (for delta)
_PINCH_CLOSE       = 0.07   # normalised distance = "pinched"
_SPREAD_OPEN       = 0.18   # normalised distance = "spread open"
_ARM_HOLD_SECS     = 1.5    # seconds to hold before armed
_pinch_indicator   = ""     # HUD string for pinch state

# ── Mesh / textures ───────────────────────────────────────────────────────────
mesh_vertices = mesh_faces = mesh_normals = mesh_uvs = None
texture_id = 0; _globe_list = 0; _globe_loaded = False

# ── Preview overlay ───────────────────────────────────────────────────────────
PREVIEW_W = 220; PREVIEW_H = 165
_preview_tex = 0
_preview_frame = None
_preview_lock  = threading.Lock()

# ── Voice ─────────────────────────────────────────────────────────────────────
_voice = None
_voice_last_cmd = ""; _voice_cmd_timer = 0.0

# ── Camera / tracker ─────────────────────────────────────────────────────────
_tracker = None
cap = cv2.VideoCapture(0)

# ── CNN ───────────────────────────────────────────────────────────────────────
cnn_clf = None
if _CNN_OK:
    cnn_clf = GestureClassifier()
    if not cnn_clf.load(): cnn_clf = None

# ── Object name map ───────────────────────────────────────────────────────────
OBJ_NAMES = {"globe":"Globe","sphere":"Sphere","cube":"Cube",
             "pyramid":"Pyramid","cylinder":"Cylinder"}
OBJ_MAP   = {"obj_globe":"globe","obj_sphere":"sphere","obj_cube":"cube",
             "obj_pyramid":"pyramid","obj_cylinder":"cylinder"}


# ═══════════════════════════════════════════════════════════════════════════════
#  Voice handler
# ═══════════════════════════════════════════════════════════════════════════════
def _apply_voice_3d(action: str):
    global _current_3d_type, scale, rot_x, rot_y, tx, ty
    global _voice_last_cmd, _voice_cmd_timer
    _voice_last_cmd  = action
    _voice_cmd_timer = time.time() + 2.0

    if action in OBJ_MAP:
        _current_3d_type = OBJ_MAP[action]
    elif action == "scale_up":
        scale = min(MAX_SCALE, scale + 0.3)
    elif action == "scale_down":
        scale = max(MIN_SCALE, scale - 0.3)
    elif action == "reset":
        rot_x = rot_y = 0.0; scale = 1.0; tx = ty = 0.0
    elif action == "quit":
        cap.release()
        if _tracker: _tracker.close()
        if _voice:   _voice.stop()
        glutDestroyWindow(glutGetWindow()); os._exit(0)


# ═══════════════════════════════════════════════════════════════════════════════
#  Model loading
# ═══════════════════════════════════════════════════════════════════════════════
def _load_mesh():
    global mesh_vertices,mesh_faces,mesh_normals,mesh_uvs,_globe_loaded
    if not _TRIMESH_OK or not os.path.isfile(GLOBE_OBJ):
        return
    try:
        raw = trimesh.load(GLOBE_OBJ, process=False)
        if isinstance(raw, trimesh.Scene):
            raw = trimesh.util.concatenate(raw.dump())
        raw.apply_scale(1.0 / raw.scale)
        mesh_vertices = raw.vertices.astype(np.float32)
        mesh_faces    = raw.faces
        mesh_normals  = raw.vertex_normals.astype(np.float32)
        mesh_uvs      = (raw.visual.uv.astype(np.float32)
                         if hasattr(raw.visual,"uv") and raw.visual.uv is not None
                         else None)
        _globe_loaded = True
        print(f"[3D] Globe.obj — {len(mesh_faces)} faces")
    except Exception as e:
        print(f"[3D] Globe load failed: {e}")

def _load_texture():
    if not _PIL_OK or not os.path.isfile(TEXTURE_PATH): return 0
    try:
        img  = _PImg.open(TEXTURE_PATH).transpose(_PImg.FLIP_TOP_BOTTOM)
        data = np.array(img.convert("RGB"), dtype=np.uint8)
        tid  = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, data)
        glGenerateMipmap(GL_TEXTURE_2D); return tid
    except: return 0

def _build_globe_list():
    global _globe_list
    if not _globe_loaded: return
    _globe_list = glGenLists(1)
    glNewList(_globe_list, GL_COMPILE)
    glBegin(GL_TRIANGLES)
    for face in mesh_faces:
        for idx in face:
            glNormal3fv(mesh_normals[idx])
            if mesh_uvs is not None: glTexCoord2fv(mesh_uvs[idx])
            glVertex3fv(mesh_vertices[idx])
    glEnd(); glEndList()


# ═══════════════════════════════════════════════════════════════════════════════
#  OpenGL init
# ═══════════════════════════════════════════════════════════════════════════════
def init_gl():
    global texture_id, _preview_tex
    glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LEQUAL)
    glShadeModel(GL_SMOOTH)
    glClearColor(0.07, 0.07, 0.13, 1.0)

    # ── Fix 1: GL_NORMALIZE ─────────────────────────────────────────────────
    # glScalef() stretches normals. GL_NORMALIZE re-normalises them each frame
    # so the lighting dot-product stays in [0,1] and never clamps to white.
    glEnable(GL_NORMALIZE)
    glDisable(GL_CULL_FACE)    # both faces visible — needed for two-sided lighting

    # ── Fix 2: Two-sided lighting ────────────────────────────────────────────
    # Without this, back-facing polygons are lit as if they face the light,
    # producing bright white patches on faces that should be in shadow.
    glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE)

    # ── Fix 3: Local viewer ──────────────────────────────────────────────────
    # Makes specular highlights correct for perspective views.
    glLightModeli(GL_LIGHT_MODEL_LOCAL_VIEWER, GL_TRUE)

    # ── Ambient scene light (prevents pure black on unlit faces) ─────────────
    glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.15, 0.15, 0.18, 1.0])

    glEnable(GL_LIGHTING)

    # ── Light 0: main key light — set in VIEW SPACE (before any model matrix)
    # Position is set every frame in display() so it stays fixed in world space.
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.90, 0.90, 0.88, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.0,  0.0,  0.0,  1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [0.60, 0.60, 0.60, 1.0])

    # ── Light 1: fill light from opposite side ───────────────────────────────
    glEnable(GL_LIGHT1)
    glLightfv(GL_LIGHT1, GL_DIFFUSE,  [0.35, 0.35, 0.40, 1.0])
    glLightfv(GL_LIGHT1, GL_AMBIENT,  [0.0,  0.0,  0.0,  1.0])
    glLightfv(GL_LIGHT1, GL_SPECULAR, [0.0,  0.0,  0.0,  1.0])

    # ── Light 2: weak back/rim light ─────────────────────────────────────────
    glEnable(GL_LIGHT2)
    glLightfv(GL_LIGHT2, GL_DIFFUSE,  [0.15, 0.15, 0.20, 1.0])
    glLightfv(GL_LIGHT2, GL_AMBIENT,  [0.0,  0.0,  0.0,  1.0])
    glLightfv(GL_LIGHT2, GL_SPECULAR, [0.0,  0.0,  0.0,  1.0])

    # ── Color material: face color drives diffuse + ambient ──────────────────
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR,  [0.30, 0.30, 0.30, 1.0])
    glMaterialf (GL_FRONT_AND_BACK, GL_SHININESS, 32.0)

    _preview_tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, _preview_tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    _load_mesh(); texture_id = _load_texture(); _build_globe_list()


# ═══════════════════════════════════════════════════════════════════════════════
#  Corner gesture preview
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_preview():
    with _preview_lock: frame = _preview_frame
    if frame is None: return

    small = cv2.resize(frame, (PREVIEW_W, PREVIEW_H))
    cv2.rectangle(small, (0,0), (PREVIEW_W-1,PREVIEW_H-1), (60,180,255), 2)
    cv2.putText(small, "HAND GESTURES", (4,14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (60,180,255), 1)
    rgb = np.flipud(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))

    glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, _preview_tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, PREVIEW_W, PREVIEW_H, 0,
                 GL_RGB, GL_UNSIGNED_BYTE, rgb)
    m = 10
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, WIDTH, 0, HEIGHT, -1, 1)
    glMatrixMode(GL_MODELVIEW);  glPushMatrix(); glLoadIdentity()
    glColor3f(1,1,1)
    glBegin(GL_QUADS)
    glTexCoord2f(0,0); glVertex2f(m,         m)
    glTexCoord2f(1,0); glVertex2f(m+PREVIEW_W,m)
    glTexCoord2f(1,1); glVertex2f(m+PREVIEW_W,m+PREVIEW_H)
    glTexCoord2f(0,1); glVertex2f(m,          m+PREVIEW_H)
    glEnd()
    glMatrixMode(GL_MODELVIEW);  glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glDisable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING)


# ═══════════════════════════════════════════════════════════════════════════════
#  3D object renderers
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_globe():
    if texture_id:
        glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0,1.0,1.0)
    else:
        glDisable(GL_TEXTURE_2D); glColor3f(0.3,0.6,1.0)
    if _globe_list: glCallList(_globe_list)
    else: _draw_sphere()
    glDisable(GL_TEXTURE_2D)

def _draw_sphere():
    glDisable(GL_TEXTURE_2D); glColor3f(0.25, 0.55, 1.0)
    q = gluNewQuadric()
    gluQuadricNormals(q, GLU_SMOOTH)
    gluQuadricOrientation(q, GLU_OUTSIDE)   # normals point outward
    gluSphere(q, 1.0, 48, 48)
    gluDeleteQuadric(q)

def _draw_cube():
    glDisable(GL_TEXTURE_2D)
    faces = [
        ([(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],   (1.0,0.3,0.3),(0,0,1)),
        ([(-1,-1,-1),(-1,1,-1),(1,1,-1),(1,-1,-1)],(0.3,1.0,0.3),(0,0,-1)),
        ([(-1,-1,-1),(-1,-1,1),(-1,1,1),(-1,1,-1)],(0.3,0.3,1.0),(-1,0,0)),
        ([(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)],    (1.0,1.0,0.2),(1,0,0)),
        ([(-1,1,-1),(-1,1,1),(1,1,1),(1,1,-1)],    (0.2,1.0,1.0),(0,1,0)),
        ([(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)],(1.0,0.3,1.0),(0,-1,0)),
    ]
    glBegin(GL_QUADS)
    for verts,col,normal in faces:
        glNormal3fv(normal); glColor3fv(col)
        for v in verts: glVertex3fv(v)
    glEnd()

def _draw_pyramid():
    glDisable(GL_TEXTURE_2D)
    apex=(0.0,1.5,0.0); base=[(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)]
    cols=[(0.3,0.9,0.3),(0.2,0.75,0.2),(0.4,0.85,0.3),(0.25,0.8,0.25)]
    def norm(a,b,c):
        ab=[b[i]-a[i] for i in range(3)]; ac=[c[i]-a[i] for i in range(3)]
        n=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
        l=math.sqrt(sum(x*x for x in n)) or 1; return [x/l for x in n]
    glBegin(GL_TRIANGLES)
    for i in range(4):
        b1,b2=base[i],base[(i+1)%4]; glColor3fv(cols[i]); glNormal3fv(norm(apex,b1,b2))
        glVertex3fv(apex); glVertex3fv(b1); glVertex3fv(b2)
    glColor3f(0.15,0.65,0.15); glNormal3f(0,-1,0)
    glVertex3fv(base[0]); glVertex3fv(base[1]); glVertex3fv(base[2])
    glVertex3fv(base[0]); glVertex3fv(base[2]); glVertex3fv(base[3])
    glEnd()

def _draw_cylinder():
    glDisable(GL_TEXTURE_2D); glColor3f(0.85, 0.25, 0.75)
    glPushMatrix(); glTranslatef(0,-1,0); glRotatef(-90,1,0,0)
    q = gluNewQuadric()
    gluQuadricNormals(q, GLU_SMOOTH)
    gluQuadricOrientation(q, GLU_OUTSIDE)   # normals point outward
    gluCylinder(q, 0.7, 0.7, 2.0, 36, 4)
    glColor3f(0.70, 0.20, 0.65)
    gluDisk(q, 0, 0.7, 36, 1)
    glTranslatef(0, 0, 2.0)
    gluDisk(q, 0, 0.7, 36, 1)
    gluDeleteQuadric(q)
    glPopMatrix()

def _draw_current_object():
    t = _current_3d_type
    if   t == "sphere":   _draw_sphere()
    elif t == "cube":     _draw_cube()
    elif t == "pyramid":  _draw_pyramid()
    elif t == "cylinder": _draw_cylinder()
    else:                 _draw_globe()


# ═══════════════════════════════════════════════════════════════════════════════
#  Pinch-zoom state machine (single hand, thumb + index)
# ═══════════════════════════════════════════════════════════════════════════════
def _pinch_dist_norm(lm) -> float:
    """Normalised 0-1 distance between thumb tip (4) and index tip (8)."""
    t = lm.landmark[4]; i = lm.landmark[8]
    return math.hypot(t.x - i.x, t.y - i.y)

def _update_pinch_zoom(lm, hand_label) -> bool:
    """
    Run the pinch-zoom state machine for ONE hand's landmarks.
    Returns True if pinch-zoom consumed this hand (caller should skip rotate).
    Updates global `scale` directly.
    """
    global _pinch_state, _pinch_arm_start, _pinch_arm_dist
    global _pinch_prev_dist, _pinch_indicator, scale

    now  = time.time()
    dist = _pinch_dist_norm(lm)
    gesture = classify_gesture(lm, hand_label)

    # ── STATE: idle ──────────────────────────────────────────────────────────
    if _pinch_state == "idle":
        if gesture == "pinch":
            _pinch_state     = "pinch_arming"
            _pinch_arm_start = now
            _pinch_arm_dist  = dist
            _pinch_indicator = "Pinch held..."
        else:
            _pinch_indicator = ""
        return False

    # ── STATE: pinch_arming (holding closed, waiting ARM_HOLD_SECS) ──────────
    elif _pinch_state == "pinch_arming":
        if gesture != "pinch":
            _pinch_state = "idle"; _pinch_indicator = ""; return False
        elapsed = now - _pinch_arm_start
        progress = min(elapsed / _ARM_HOLD_SECS, 1.0)
        _pinch_indicator = f"Pinch: arming {'#' * int(progress*10):<10} {int(progress*100)}%"
        if elapsed >= _ARM_HOLD_SECS:
            _pinch_state    = "pinch_armed"
            _pinch_prev_dist = dist
            _pinch_indicator = "ARMED: expand/compress to ZOOM"
        return True

    # ── STATE: pinch_armed (expand = zoom in, compress = zoom out) ───────────
    elif _pinch_state == "pinch_armed":
        delta = (dist - _pinch_prev_dist) * 6.0
        scale = max(MIN_SCALE, min(MAX_SCALE, scale + delta))
        _pinch_prev_dist = dist

        if delta > 0.005:   _pinch_indicator = f"ZOOM IN  |  scale={scale:.2f}"
        elif delta < -0.005: _pinch_indicator = f"ZOOM OUT |  scale={scale:.2f}"

        if gesture != "pinch":
            _pinch_state = "idle"; _pinch_indicator = ""
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  Hand gesture handler
# ═══════════════════════════════════════════════════════════════════════════════
def _update_hands(result, frame_hw):
    global rot_x, rot_y, scale, tx, ty
    global prev_cx, prev_cy, prev_tx_ref, prev_ty_ref
    global mode_label, cnn_label, cnn_conf, auto_rot_y, _pinch_state, _pinch_indicator

    H, W = frame_hw

    if not result.hands:
        prev_cx = prev_cy = None
        prev_tx_ref = prev_ty_ref = None
        mode_label   = "No hand detected"
        _pinch_state = "idle"; _pinch_indicator = ""
        auto_rot_y = 0.0
        return

    auto_rot_y = 0.0

    if len(result.hands) == 2:
        lm0, lm1 = result.hands[0].landmarks, result.hands[1].landmarks
        dist = inter_palm_distance(lm0, lm1, W, H)
        if hasattr(_update_hands, '_two_prev_dist') and _update_hands._two_prev_dist:
            delta = (dist - _update_hands._two_prev_dist) * SCALE_GAIN
            scale = max(MIN_SCALE, min(MAX_SCALE, scale + delta))
        _update_hands._two_prev_dist = dist
        prev_cx = prev_cy = None
        mode_label = f"TWO hands: palm-scale  x{scale:.2f}"
        cnn_label  = "scale"; _pinch_state = "idle"; _pinch_indicator = ""
        return

    _update_hands._two_prev_dist = None

    hand = result.hands[0]
    lm, label = hand.landmarks, hand.label

    if cnn_clf:
        gesture, conf = cnn_clf.predict(lm, label)
        cnn_label = gesture; cnn_conf = conf
    else:
        gesture = classify_gesture(lm, label)
        cnn_label = gesture + " (rule)"; cnn_conf = 1.0

    fup = fingers_up(lm, label)
    cx, cy = palm_center_px(lm, W, H)

    # ── Three fingers → translate ─────────────────────────────────────────────
    if fup[1] and fup[2] and fup[3] and not fup[4]:
        if prev_tx_ref is not None:
            tx += (cx - prev_tx_ref) * TRANSLATE_GAIN
            ty -= (cy - prev_ty_ref) * TRANSLATE_GAIN
        prev_tx_ref, prev_ty_ref = cx, cy
        prev_cx = prev_cy = None
        mode_label = "THREE fingers: TRANSLATE"
        _pinch_state = "idle"; _pinch_indicator = ""
        return
    prev_tx_ref = prev_ty_ref = None

    # ── Pinch / spread → zoom ────────────────────────────────────────────────
    consumed = _update_pinch_zoom(lm, label)
    if consumed:
        prev_cx = prev_cy = None
        mode_label = _pinch_indicator or "Pinch zoom"
        return

    # ── Open Palm → rotate ──────────────────────────────────────────────────
    if gesture == "open_palm":
        if prev_cx is not None:
            rot_y -= (cx - prev_cx) * ROT_GAIN
            rot_x += (cy - prev_cy) * ROT_GAIN
        prev_cx, prev_cy = cx, cy
        mode_label = "OPEN PALM: ROTATE"
        return

    # ── Default: no action ───────────────────────────────────────────────────
    prev_cx = prev_cy = None
    mode_label = f"Show OPEN PALM to rotate ({gesture})"

_update_hands._two_prev_dist = None


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD — clean, no voice instructions
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_hud():
    glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING); glDisable(GL_TEXTURE_2D)
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, WIDTH, 0, HEIGHT, -1, 1)
    glMatrixMode(GL_MODELVIEW);  glPushMatrix(); glLoadIdentity()

    def _t(x, y, txt, r=1.0, g=0.9, b=0.2):
        glColor3f(r,g,b); glRasterPos2i(x,y)
        for ch in txt: glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

    def _ts(x, y, txt, r=1.0, g=0.9, b=0.2):
        glColor3f(r,g,b); glRasterPos2i(x,y)
        for ch in txt: glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, ord(ch))

    # Top-left: FPS, mode, object, scale
    _t(10, HEIGHT-24,  f"FPS: {fps_3d}",                     0.3,1.0,0.3)
    _t(10, HEIGHT-48,  mode_label,                            1.0,0.9,0.2)
    _t(10, HEIGHT-72,  f"Object: {OBJ_NAMES.get(_current_3d_type,'?')}   Scale:{scale:.2f}", 0.5,0.9,1.0)
    if cnn_label:
        _t(10, HEIGHT-96, f"CNN: {cnn_label} {int(cnn_conf*100)}%", 0.4,0.9,0.5)

    # Pinch-zoom indicator (only when active)
    if _pinch_indicator:
        _t(10, HEIGHT-120, _pinch_indicator, 1.0,0.7,0.2)

    # Voice command flash (bottom-right, brief)
    if _voice_last_cmd and time.time() < _voice_cmd_timer:
        label_txt = f"Voice: {_voice_last_cmd}"
        tw = len(label_txt)*10
        _t(WIDTH-tw-10, HEIGHT-30, label_txt, 0.2,1.0,0.5)

    # Mic status dot (no text)
    try:
        import speech_recognition; _sr_ok = True
    except ImportError:
        _sr_ok = False
    mic_col = (0.2,0.9,0.2) if _sr_ok else (0.6,0.2,0.2)
    # Draw a small dot manually with a quad
    dot_x, dot_y, dot_r = WIDTH-15, HEIGHT-15, 5
    glDisable(GL_LIGHTING)
    glColor3fv(mic_col)
    glBegin(GL_QUADS)
    glVertex2f(dot_x-dot_r, dot_y-dot_r); glVertex2f(dot_x+dot_r, dot_y-dot_r)
    glVertex2f(dot_x+dot_r, dot_y+dot_r); glVertex2f(dot_x-dot_r, dot_y+dot_r)
    glEnd()

    # Bottom bar: keyboard shortcuts only
    _ts(10, 6, "R=Reset  Q=Quit  1=Globe 2=Sphere 3=Cube 4=Pyramid 5=Cylinder  "
               "One-hand=Rotate  3-fingers=Move  Pinch/Spread=Zoom", 0.5,0.5,0.5)

    glMatrixMode(GL_MODELVIEW);  glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING)


# ═══════════════════════════════════════════════════════════════════════════════
#  GLUT callbacks
# ═══════════════════════════════════════════════════════════════════════════════
def display():
    global fps_3d, _last_time, _preview_frame, _voice_last_cmd, _voice_cmd_timer

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    ret, frame = cap.read()
    if ret:
        frame  = cv2.flip(frame, 1)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = _tracker.process(rgb)
        preview = frame.copy()
        for hand in result.hands: DrawLandmarks(preview, hand)
        with _preview_lock: _preview_frame = preview
        _update_hands(result, frame.shape[:2])
    else:
        result = type('R',(),{'hands':[]})()
        _update_hands(result, (480,640))

    if _voice:
        cmd = _voice.poll()
        if cmd:
            _apply_voice_3d(cmd)
            _voice_last_cmd  = cmd
            _voice_cmd_timer = time.time() + 2.0

    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45.0, WIDTH/max(HEIGHT,1), 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW);  glLoadIdentity()
    gluLookAt(0,0,6, 0,0,0, 0,1,0)

    # ── Set light positions HERE — after camera, before object transforms ────
    # This keeps lights fixed in world space regardless of object rotation.
    # Light positions given with w=0 (directional) avoid the distance falloff.
    glLightfv(GL_LIGHT0, GL_POSITION, [ 1.0,  1.0,  1.0, 0.0])   # top-right-front
    glLightfv(GL_LIGHT1, GL_POSITION, [-1.0, -0.5, -0.8, 0.0])   # bottom-left-back
    glLightfv(GL_LIGHT2, GL_POSITION, [ 0.0,  0.0, -1.0, 0.0])   # directly behind

    glTranslatef(tx, ty, 0)
    glScalef(scale, scale, scale)
    glRotatef(rot_x, 1,0,0)
    glRotatef(rot_y + auto_rot_y, 0,1,0)
    _draw_current_object()

    _draw_preview()
    _draw_hud()
    glutSwapBuffers()

    now = time.time()
    fps_3d = int(1.0 / max(now - _last_time, 1e-6))
    _last_time = now

def idle(): glutPostRedisplay()

def reshape(w,h):
    glViewport(0,0,w,h)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45.0, w/max(h,1), 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)

def keyboard(key, x, y):
    global rot_x, rot_y, scale, tx, ty, _current_3d_type
    k = key.decode("utf-8", errors="ignore").lower()
    if k in ("q","\x1b"):
        cap.release()
        if _tracker: _tracker.close()
        if _voice:   _voice.stop()
        glutDestroyWindow(glutGetWindow()); os._exit(0)
    elif k == "r":
        rot_x=rot_y=0.0; scale=1.0; tx=ty=0.0
    elif k=="1": _current_3d_type="globe"
    elif k=="2": _current_3d_type="sphere"
    elif k=="3": _current_3d_type="cube"
    elif k=="4": _current_3d_type="pyramid"
    elif k=="5": _current_3d_type="cylinder"


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════
def run(initial_3d_type=None):
    global _current_3d_type, _tracker, _voice
    if initial_3d_type: _current_3d_type = initial_3d_type
    if not cap.isOpened(): print("[3D] Camera unavailable — gestures disabled.")

    _tracker = HandTracker(max_hands=2, detect_conf=MP_DETECT_CONF, track_conf=MP_TRACK_CONF)

    try:
        from modules.voice import VoiceCommandListener
        _voice = VoiceCommandListener(mode="3d"); _voice.start()
    except Exception as e:
        print(f"[Voice] Not available: {e}"); _voice = None

    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(WIDTH, HEIGHT)
    glutCreateWindow(b"AI Virtual Drawing - 3D Viewer")
    init_gl()
    glutDisplayFunc(display); glutIdleFunc(idle)
    glutReshapeFunc(reshape);  glutKeyboardFunc(keyboard)

    print("[3D] Controls:")
    print("  Move hand          → Rotate")
    print("  3 fingers          → Translate")
    print("  Pinch (hold 1.5s)  → Expand to ZOOM IN")
    print("  Spread (hold 1.5s) → Compress to ZOOM OUT")
    print("  Two hands          → Scale (palm distance)")
    print("  1-5 keys           → Switch object")
    print("  R = Reset  |  Q = Quit")
    glutMainLoop()

if __name__ == "__main__":
    run()