"""
Shared constants. Keeping tunable numbers here so the alien's behaviour
can be adjusted without hunting through game logic.
"""

# --- Grid / screen ---------------------------------------------------------
TILE = 24
COLS = 104
ROWS = 44
WORLD_W = COLS * TILE
WORLD_H = ROWS * TILE
VIEW_H = 768
SCREEN_W = 1248
UI_HEIGHT = 90
SCREEN_H = VIEW_H + UI_HEIGHT
FPS = 60
CAMERA_ZOOM = 1.3
CAMERA_W = round(SCREEN_W / CAMERA_ZOOM)
CAMERA_H = round(VIEW_H / CAMERA_ZOOM)

# --- Colors ------------------------------------------------------------
COL_BG = (6, 6, 9)
COL_WALL = (30, 30, 36)
COL_WALL_EDGE = (52, 52, 62)
COL_FLOOR = (23, 23, 28)
COL_FLOOR_ROOM = (30, 30, 37)
COL_FLOOR_TASK = (34, 40, 34)
COL_FOG = (0, 0, 0)
COL_PLAYER = (132, 148, 160)
COL_PLAYER_NOISE = (90, 170, 230, 60)
COL_ALIEN = (130, 55, 50)
COL_TEXT = (195, 195, 205)
COL_TEXT_DIM = (110, 110, 120)
COL_ALARM = (220, 70, 70)
COL_TASK_DONE = (114, 132, 112)
COL_TASK_TODO = (155, 139, 109)
COL_DEBUG = (255, 210, 60)
COL_DEBUG_PATH = (60, 220, 255)
COL_DEBUG_FOV = (255, 90, 90)
COL_DEBUG_SOUND = (255, 255, 255)

# --- Player --------------------------------------------------------------
PLAYER_RADIUS = 8
WALK_SPEED = 118.0
SPRINT_SPEED = 205.0
STAMINA_MAX = 100.0
STAMINA_DRAIN = 30.0     # per second while sprinting
STAMINA_REGEN = 16.0     # per second while not sprinting
STAMINA_MIN_TO_SPRINT = 6.0

INTERACT_HOLD_TIME = 3.5  # seconds holding E to complete a task

# Noise radii (world px) produced by player actions
NOISE_RADIUS_WALK = 75
NOISE_RADIUS_RUN = 260
NOISE_RADIUS_REPAIR = 340

# How strongly each noise type raises alien suspicion (before distance falloff)
NOISE_STRENGTH_WALK = 6
NOISE_STRENGTH_RUN = 22
NOISE_STRENGTH_REPAIR = 30

# --- Player vision (fog of war) --------------------------------------------
PLAYER_VIEW_RADIUS = 230
PLAYER_VIEW_RAYS = 140
FLASHLIGHT_BRIGHTNESS = 3.726  # v0.8 brightness * 1.50; falloff and walls retained

# --- Alien base parameters (scaled per-day in systems.DAY_PARAMS) ----------
ALIEN_RADIUS = 9
ALIEN_WANDER_SPEED = 60.0
ALIEN_INVESTIGATE_SPEED = 85.0
ALIEN_CHASE_SPEED = 150.0          # still slower than sprinting player
ALIEN_SEARCH_SPEED = 80.0

ALIEN_FOV_ANGLE = 100.0            # degrees, total cone width
ALIEN_VIEW_RANGE = 210.0
ALIEN_VIEW_RANGE_CHASE = 260.0     # can see a bit further once actively chasing

SUSPICION_MAX = 100.0
SUSPICION_SUSPICIOUS_THRESHOLD = 18.0
SUSPICION_INVESTIGATE_THRESHOLD = 40.0
SUSPICION_CHASE_THRESHOLD = 72.0
SUSPICION_DECAY_PER_SEC = 6.0

SUSPICIOUS_STATE_MIN_TIME = 0.6
SUSPICIOUS_STATE_MAX_TIME = 1.2

CHASE_LOS_GRACE = 0.5              # seconds alien tolerates losing sight before giving up chase
SEARCH_AREA_BASE_TIME = 18.0       # seconds spent searching nearby rooms
SEARCH_AREA_WAYPOINT_TIME = 2.6    # seconds paused looking at each search waypoint

CATCH_RADIUS = 16                  # distance at which alien catches the player during CHASE

# --- Day / task system -----------------------------------------------------
NUM_DAYS = 8
DAY_LENGTH_SECONDS = 420.0
MISSED_TASK_DAMAGE = 8
TASK_ROOM_NAMES = ["Oxygen", "Reactor", "Power", "Communications", "Cooling",
                   "Navigation", "Cargo Bay", "Storage", "Airlock"]
DAY8_SEQUENCE = ["Power", "Navigation", "Hangar"]

# Debug
DEBUG_TOGGLE_KEY = "F3"

# Vertical-slice stealth and survival tuning
CROUCH_SPEED = 65.0
NOISE_RADIUS_CROUCH = 30
SHIP_INTEGRITY_MAX = 100
DECOY_CHARGES = 3
DECOY_RANGE = 145
DECOY_DELAY = 1.0
DECOY_RADIUS = 420
