#!/usr/bin/env python3
"""NEON STRIKER '96 - a 90s-style side-scrolling arcade shooter.

Controls: arrows/WASD move, Z/Space fire (hold), X bomb, P pause, Enter start,
F11 fullscreen, Esc quit.
All graphics and sounds are generated at startup; no asset files needed.
Run `python neon_striker.py --selftest` for a headless autopilot run.
Options: --lives=N, --credits=N, --start-weapon-level=N, --start-level=N (see --help).
"""
import argparse
import math
import os
import random
import sys
from pathlib import Path

if "--selftest" in sys.argv:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

import numpy as np
import pygame

# --- screen -----------------------------------------------------------------
W, H = 320, 180          # native low-res playfield, scaled up for chunky pixels
SCALE = 4                # window scale; fullscreen picks the largest integer scale that fits
FPS = 60
GROUND_Y = 140           # horizon line of the synthwave floor
HUD_TOP = 12             # playfield starts below the score line
SCANLINE_ALPHA = 70
SCROLL_SPEED = 1.0

# --- audio ------------------------------------------------------------------
SAMPLE_RATE = 22050
SFX_VOLUME = 0.3
MUSIC_VOLUME = 0.45

# Songs: 4 chords x 16 sixteenth-steps, played twice (lead an octave up the second time).
# bass = semitone offset from the chord root per step, arp = index into the chord tones
# (0-2, 3-5 an octave up), None = rest. kick/snare/hat list the steps they hit on.
ODD_STEPS, EVEN_STEPS = tuple(range(1, 16, 2)), tuple(range(0, 16, 2))
SONGS = [
    dict(name="NEON HIGHWAY", bpm=140, duty=0.25,
         chords=[(57, 60, 64), (55, 59, 62), (53, 57, 60), (52, 56, 59)],  # Am G F E
         bass=[0, 0, 12, 0] * 4, arp=[0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5, 0, 1, 2, 3],
         kick=(0, 4, 8, 12), snare=(), hat=ODD_STEPS),
    dict(name="SUNSET RUN", bpm=160, duty=0.125,
         chords=[(60, 64, 67), (55, 59, 62), (57, 60, 64), (53, 57, 60)],  # C G Am F
         bass=[0, 12] * 8, arp=[0, 2, 4, 2, 1, 3, 5, 3] * 2,
         kick=(0, 4, 8, 12), snare=(4, 12), hat=(2, 6, 10, 14)),
    dict(name="CYBER DUNGEON", bpm=118, duty=0.5,
         chords=[(62, 65, 69), (58, 62, 65), (60, 64, 67), (57, 61, 64)],  # Dm Bb C A
         bass=[0, None, 0, 12, None, 0, None, 7] * 2,
         arp=[0, None, 1, None, 2, None, 4, None, 3, None, 2, None, 1, None, None, None],
         kick=(0, 6, 8), snare=(4, 12), hat=EVEN_STEPS),
    dict(name="BOSS RUSH", bpm=175, duty=0.25,
         chords=[(64, 67, 71), (60, 64, 67), (62, 66, 69), (59, 63, 66)],  # Em C D B
         bass=[0, 0, 12, 0, 0, 12, 0, 12] * 2, arp=[5, 4, 3, 2, 1, 0, 1, 2] * 2,
         kick=(0, 4, 8, 12), snare=(4, 12), hat=ODD_STEPS),
    dict(name="MELTDOWN", bpm=150, duty=0.125,
         chords=[(60, 63, 67), (56, 60, 63), (58, 62, 65), (55, 59, 62)],  # Cm Ab Bb G
         bass=[0, 0, 12, 0, 7, 0, 12, 0] * 2,
         arp=[0, None, 2, 3, None, 5, 4, None, 2, None, 3, 1, None, 2, 0, None],
         kick=(0, 3, 8, 11), snare=(4, 12), hat=ODD_STEPS),
    dict(name="FROZEN CIRCUIT", bpm=132, duty=0.5,
         chords=[(54, 57, 61), (50, 54, 57), (57, 61, 64), (52, 56, 59)],  # F#m D A E
         bass=[0, None, 12, None] * 4, arp=[0, 2, 4, 5, 4, 2] * 2 + [0, 2, 4, 5],
         kick=(0, 8), snare=(4, 12), hat=EVEN_STEPS),
    dict(name="VAPOR MALL", bpm=100, duty=0.5,
         chords=[(53, 57, 60), (52, 55, 59), (50, 53, 57), (48, 52, 55)],  # F Em Dm C
         bass=[0, None, None, 7, None, None, 12, None] * 2,
         arp=[0, None, 2, None, 4, None, 3, None, 5, None, 4, None, 2, None, 1, None],
         kick=(0, 10), snare=(4, 12), hat=ODD_STEPS),
    dict(name="ECLIPSE", bpm=128, duty=0.25,
         chords=[(59, 62, 66), (55, 59, 62), (52, 55, 59), (54, 58, 61)],  # Bm G Em F#
         bass=[0, 0, 0, 12] * 4,
         arp=[3, None, None, 0, None, None, 4, None, 3, None, None, 1, None, None, 2, None],
         kick=(0, 4, 8, 12), snare=(12,), hat=ODD_STEPS),
    dict(name="BLOOD MOON", bpm=168, duty=0.125,
         chords=[(55, 58, 62), (51, 55, 58), (53, 57, 60), (50, 54, 57)],  # Gm Eb F D
         bass=[0, 12] * 8, arp=[0, 1, 2, 3, 4, 5, 4, 3] * 2,
         kick=(0, 4, 8, 10, 12), snare=(4, 12), hat=EVEN_STEPS),
]
STAGE_SONGS = ["NEON HIGHWAY", "SUNSET RUN", "CYBER DUNGEON", "MELTDOWN",  # one per stage theme
               "FROZEN CIRCUIT", "VAPOR MALL", "ECLIPSE", "BLOOD MOON"]
BOSS_SONG = "BOSS RUSH"

# --- player -----------------------------------------------------------------
PLAYER_SPEED = 1.8
PLAYER_START = (40, H // 2)
PLAYER_LIVES = 3
MAX_LIVES = 99           # 3 digits no longer fit the HUD
START_BOMBS = 2
MAX_BOMBS = 99           # 3 digits no longer fit the HUD
MAX_WEAPON = 5
START_WEAPON = 1
WEAPON_DAMAGE = (1, 1, 1, 1.2, 1.4)  # per bullet, by weapon level; floats are fine
LASER_LEVEL = 4          # from this level on, level 3's spread fires laser bolts
FIRE_COOLDOWN = 7
PLAYER_BULLET_SPEED = 6
INVULN_FRAMES = 120
RESPAWN_FRAMES = 90
HIT_FLASH_FRAMES = 3
MAX_SHIELD = 3           # each shield level absorbs one hit
SHIELD_HIT_INVULN = 60   # grace frames after the bubble pops, so one burst can't drain it all
SHIELD_RADIUS = 12
SHIELD_COLORS = ((60, 140, 255), (60, 240, 255), (220, 255, 255))  # by shield level
FLASH_ALPHA = 200
FLASH_ALPHA_BOSS = 110

# --- enemies / stage --------------------------------------------------------
STAGE_FRAMES = 40 * FPS  # wave phase length before the boss shows up
START_STAGE = 1          # stage a new game begins on; 9+ loops the themes
WAVE_INTERVAL = 110
WAVE_INTERVAL_MIN = 50
WAVE_SPEEDUP = 12        # frames shaved off the wave interval per stage
DART_AIM_FRAMES = 40
ENEMY_BULLET_SPEED = 1.6
DROP_CHANCE = 0.1
ENEMY_HP = {"drone": 1, "dart": 2, "turret": 6, "mine": 3, "weaver": 2, "gunship": 14}
ENEMY_SCORE = {"drone": 100, "dart": 150, "turret": 300, "mine": 120, "weaver": 200, "gunship": 800}
ENEMY_SIZE = {"drone": (10, 8), "dart": (12, 5), "turret": (11, 11), "mine": (9, 9), "weaver": (10, 6),
              "gunship": (20, 9)}
MINE_BURST = 8           # bullets in the ring a mine releases when shot down
WEAVER_FIRST_STAGE = 2
WEAVER_TURN = 0.06       # vertical steering per frame towards the player
WEAVER_MAX_VY = 1.5
GUNSHIP_FIRST_STAGE = 3
GUNSHIP_X = 260          # where the gunship parks
GUNSHIP_STAY = 6 * FPS   # frames from spawn until it breaks off
GUNSHIP_FIRE_INTERVAL = 70

BOSS_X = 250
BOSS_BASE_HP = 176
BOSS_HP_PER_STAGE = 96
BOSS_PATTERN_FRAMES = 240
BOSS_MAX_ESCORTS = 8     # carrier stops launching drones above this many enemies
LASER_CYCLE = 120        # laser pattern: charge, then fire, then a short breather
LASER_CHARGE = 50
LASER_END = 110
LASER_HALF_WIDTH = 4
BOSS_DEATH_FRAMES = 120
BOSS_BONUS = 5000
WARNING_FRAMES = 150
CLEAR_FRAMES = 200

BOMB_DAMAGE = 10
BOMB_BOSS_DAMAGE = 30
BOMB_FLASH_FRAMES = 12

# --- meta -------------------------------------------------------------------
ATTRACT_DELAY = 8 * FPS
DEMO_FRAMES = 40 * FPS
CONTINUE_SECONDS = 9
START_CREDITS = 3        # continues per game; with none left it's back to stage 1
MAX_CREDITS = 99         # 3 digits no longer fit the continue screen
NO_CREDITS_FRAMES = 4 * FPS  # final game-over screen before returning to the title
HISCORE_FILE = Path(__file__).with_name("hiscore.txt")
HISCORE_DEFAULT = 20000
SELFTEST_FRAMES = 90000  # eight bosses take the autopilot ~40-65k frames

WHITE, BLACK = (255, 255, 255), (0, 0, 0)
CYAN, PINK, YELLOW = (60, 240, 255), (255, 70, 200), (255, 230, 60)
FIRE = [(255, 255, 200), (255, 220, 60), (255, 140, 0), (255, 60, 30), (140, 20, 20)]

PAL = {
    "c": (0, 90, 160), "b": (40, 160, 255), "w": (230, 250, 255),
    "m": (120, 0, 120), "p": (220, 60, 220), "r": (255, 40, 60),
    "g": (0, 120, 60), "l": (80, 255, 120),
    "o": (200, 90, 0), "y": (255, 210, 40), "d": (60, 60, 80), "s": (130, 130, 155),
}
PLAYER_ART = [
    "...cc...........",
    "...cbcc.........",
    "....cbbcc.......",
    "..ccbbbbbbccc...",
    ".cbbbbbwwwbbbbc.",
    "..ccbbbbbbccc...",
    "....cbbcc.......",
    "...cbcc.........",
    "...cc...........",
]
DRONE_ART = [
    "...mmmm...",
    ".mmppppmm.",
    "mppprrpppm",
    "mpprwwrppm",
    "mpprwwrppm",
    "mppprrpppm",
    ".mmppppmm.",
    "...mmmm...",
]
DART_ART = [
    "......gggg..",
    "...gglllll..",
    "wllllllllggg",
    "...gglllll..",
    "......gggg..",
]
WEAVER_ART = [
    "........oo.",
    "......oyyo.",
    "..ooyyyyyoo",
    "wyyyrrryyyy",
    "..ooyyyyyoo",
    "......oyyo.",
    "........oo.",
]
GUNSHIP_ART = [
    "..........dddddddd....",
    "........ddssssssssdd..",
    "oooddddddssssssssssd..",
    "..dsssssssssrrsssssssd",
    "wddsssssssrwwrssssssdd",
    "..dsssssssssrrsssssssd",
    "oooddddddssssssssssd..",
    "........ddssssssssdd..",
    "..........dddddddd....",
]

THEMES = [
    dict(sky=((10, 0, 30), (180, 40, 120)), sun=((255, 230, 80), (255, 50, 150)),
         far=(70, 20, 100), near=(35, 5, 60), floor=(15, 0, 30), grid=(255, 40, 200)),
    dict(sky=((0, 5, 30), (0, 110, 150)), sun=((220, 255, 255), (0, 200, 220)),
         far=(0, 60, 90), near=(0, 25, 50), floor=(0, 10, 25), grid=(0, 255, 220)),
    dict(sky=((0, 15, 5), (90, 160, 20)), sun=((240, 255, 120), (120, 220, 0)),
         far=(20, 70, 20), near=(5, 35, 10), floor=(0, 15, 5), grid=(170, 255, 0)),
    dict(sky=((25, 0, 0), (220, 90, 0)), sun=((255, 255, 160), (255, 80, 0)),
         far=(100, 25, 0), near=(50, 5, 0), floor=(20, 0, 0), grid=(255, 180, 0)),
    dict(sky=((5, 5, 35), (110, 130, 230)), sun=((255, 255, 255), (150, 170, 255)),
         far=(40, 50, 110), near=(15, 20, 60), floor=(5, 5, 25), grid=(140, 170, 255)),
    dict(sky=((30, 0, 50), (255, 140, 200)), sun=((255, 250, 180), (120, 240, 255)),
         far=(110, 60, 150), near=(60, 25, 90), floor=(25, 0, 40), grid=(120, 255, 255)),
    dict(sky=((0, 0, 0), (70, 70, 85)), sun=((40, 40, 45), (15, 15, 20)),  # eclipsed sun
         far=(45, 45, 55), near=(22, 22, 28), floor=(5, 5, 8), grid=(230, 230, 240)),
    dict(sky=((10, 0, 5), (150, 0, 30)), sun=((255, 220, 200), (255, 0, 50)),
         far=(80, 0, 20), near=(40, 0, 10), floor=(15, 0, 3), grid=(255, 30, 70)),
]


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def make_sprite(rows):
    s = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                s.set_at((x, y), PAL[ch])
    return s


def white_silhouette(surf):
    return pygame.mask.from_surface(surf).to_surface(setcolor=WHITE, unsetcolor=(0, 0, 0, 0))


def make_battleship():
    s = pygame.Surface((56, 40), pygame.SRCALPHA)
    hull = [(4, 20), (18, 6), (44, 2), (54, 10), (54, 30), (44, 38), (18, 34)]
    pygame.draw.polygon(s, (70, 40, 110), hull)
    pygame.draw.polygon(s, (170, 120, 230), hull, 1)
    pygame.draw.rect(s, (40, 20, 70), (24, 8, 24, 24))
    for y in (11, 19, 27):
        pygame.draw.line(s, (120, 80, 180), (26, y), (46, y))
    for y in (8, 28):  # twin cannons
        pygame.draw.rect(s, (90, 90, 110), (6, y, 16, 4))
        pygame.draw.rect(s, (200, 200, 220), (6, y, 3, 4))
    return s


def make_carrier():
    s = pygame.Surface((72, 28), pygame.SRCALPHA)
    hull = [(0, 14), (10, 4), (64, 2), (71, 8), (71, 20), (64, 26), (10, 24)]
    pygame.draw.polygon(s, (120, 140, 165), hull)
    pygame.draw.polygon(s, (120, 220, 255), hull, 1)
    pygame.draw.rect(s, (170, 190, 210), (46, 0, 10, 5))  # bridge tower
    pygame.draw.rect(s, (5, 20, 30), (4, 9, 16, 10))     # hangar mouth the drones fly out of
    for x in (6, 11, 16):
        pygame.draw.line(s, YELLOW, (x, 10), (x + 2, 14))
        pygame.draw.line(s, YELLOW, (x + 2, 14), (x, 18))
    for x in range(26, 62, 6):  # deck lights
        s.set_at((x, 7), (0, 90, 160))
        s.set_at((x, 21), (0, 90, 160))
    return s


def make_orb():
    s = pygame.Surface((48, 48), pygame.SRCALPHA)
    c = 24
    for k in range(8):  # spikes
        a = k * math.tau / 8
        tip = (c + math.cos(a) * 23, c + math.sin(a) * 23)
        side = [(c + math.cos(a + d) * 14, c + math.sin(a + d) * 14) for d in (-0.3, 0.3)]
        pygame.draw.polygon(s, (180, 255, 80), [side[0], tip, side[1]])
    pygame.draw.circle(s, (40, 90, 20), (c, c), 16)
    pygame.draw.circle(s, (180, 255, 80), (c, c), 16, 1)
    pygame.draw.circle(s, (10, 30, 5), (c, c), 9)
    return s


def make_lancer():
    s = pygame.Surface((80, 22), pygame.SRCALPHA)
    hull = [(0, 11), (24, 8), (56, 4), (79, 2), (79, 19), (56, 17), (24, 14)]
    pygame.draw.polygon(s, (75, 70, 95), hull)
    pygame.draw.polygon(s, (255, 160, 40), hull, 1)
    pygame.draw.polygon(s, (255, 160, 40), [(58, 4), (70, 0), (76, 0), (70, 4)])  # tail fins
    pygame.draw.polygon(s, (255, 160, 40), [(58, 17), (70, 21), (76, 21), (70, 17)])
    pygame.draw.line(s, YELLOW, (26, 11), (54, 11))
    return s


def make_fortress():
    s = pygame.Surface((60, 44), pygame.SRCALPHA)
    hull = [(2, 22), (12, 10), (12, 2), (58, 2), (58, 42), (12, 42), (12, 34)]
    pygame.draw.polygon(s, (90, 110, 170), hull)
    pygame.draw.polygon(s, (200, 230, 255), hull, 1)
    for y in range(8, 40, 8):  # armour plating
        pygame.draw.line(s, (150, 180, 230), (20, y), (54, y))
    for y in (12, 32):  # ice cannons
        pygame.draw.rect(s, (160, 200, 255), (0, y - 2, 14, 4))
    return s


def make_prism():
    s = pygame.Surface((50, 50), pygame.SRCALPHA)
    c = 25
    outer = [(0, c), (c, 0), (49, c), (c, 49)]
    pygame.draw.polygon(s, (120, 60, 160), outer)
    pygame.draw.polygon(s, (60, 200, 220), [(10, c), (c, 10), (39, c), (c, 39)])
    for p in outer:  # facets
        pygame.draw.line(s, (255, 170, 230), p, (c, c))
    pygame.draw.polygon(s, (255, 170, 230), outer, 1)
    return s


def make_eye():
    s = pygame.Surface((52, 52), pygame.SRCALPHA)
    c = 26
    for k in range(12):  # corona flares
        a = k * math.tau / 12
        pygame.draw.line(s, (220, 220, 230), (c + math.cos(a) * 18, c + math.sin(a) * 18),
                         (c + math.cos(a) * 25, c + math.sin(a) * 25), 2)
    pygame.draw.circle(s, (20, 20, 25), (c, c), 19)
    pygame.draw.circle(s, WHITE, (c, c), 19, 1)
    pygame.draw.circle(s, (230, 230, 240), (c - 6, c), 11)  # eyeball, glaring at the player
    pygame.draw.circle(s, (180, 0, 30), (c - 8, c), 6)
    return s


def make_dreadnought():
    s = pygame.Surface((88, 40), pygame.SRCALPHA)
    hull = [(0, 20), (14, 10), (40, 6), (60, 0), (87, 4), (87, 36), (60, 39), (40, 34), (14, 30)]
    pygame.draw.polygon(s, (70, 15, 25), hull)
    pygame.draw.polygon(s, (255, 60, 80), hull, 1)
    pygame.draw.rect(s, (40, 5, 10), (44, 12, 36, 16))  # engine block
    for x in range(48, 78, 6):  # vents
        pygame.draw.line(s, (255, 60, 80), (x, 14), (x, 25))
    for y in (11, 29):  # broadside cannons
        pygame.draw.rect(s, (110, 90, 95), (10, y - 2, 18, 4))
        pygame.draw.rect(s, (230, 210, 215), (10, y - 2, 3, 4))
    return s


# One boss per stage theme; stage 9+ loops around with more HP and faster bullets.
# Offsets (core, guns) are relative to the boss centre; swing = (vertical, horizontal) drift.
BOSSES = [
    dict(name="HUGE BATTLESHIP", draw=make_battleship, size=(52, 36), core=(-14, 0),
         guns=((-22, -10), (-22, 10)), swing=(50, 20), patterns=("fan", "spiral", "ring")),
    dict(name="STAR CARRIER", draw=make_carrier, size=(66, 22), core=(-24, 0),
         guns=((-28, -6), (-28, 6)), swing=(55, 10), patterns=("launch", "fan5", "stream")),
    dict(name="PLAGUE ORB", draw=make_orb, size=(36, 36), core=(0, 0),
         guns=((-16, 0),), swing=(65, 40), patterns=("spiral4", "ring", "stream")),
    dict(name="INFERNO LANCER", draw=make_lancer, size=(70, 14), core=(6, 0),
         guns=((-38, 0),), swing=(45, 15), patterns=("laser", "fan5", "stream")),
    dict(name="CRYO FORTRESS", draw=make_fortress, size=(54, 40), core=(-14, 0),
         guns=((-30, -10), (-30, 10)), swing=(45, 15), patterns=("sweep", "ring", "fan")),
    dict(name="PRISM ENGINE", draw=make_prism, size=(34, 34), core=(0, 0),
         guns=((-22, 0),), swing=(60, 35), patterns=("scatter", "spiral4", "fan5")),
    dict(name="ECLIPSE EYE", draw=make_eye, size=(36, 36), core=(-8, 0),
         guns=((-10, 0),), swing=(55, 30), patterns=("laser", "ring", "minelay")),
    dict(name="CRIMSON DREADNOUGHT", draw=make_dreadnought, size=(80, 32), core=(-24, 0),
         guns=((-44, 0), (-34, -9), (-34, 9)), swing=(50, 10),
         patterns=("fan", "sweep", "laser", "scatter", "minelay")),
]


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


class Sfx:
    """Chiptune-ish sounds synthesized with numpy. Silent if no audio device."""

    def __init__(self):
        self.sounds = {}
        try:
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        except pygame.error:
            return
        self.rate, _, self.channels = pygame.mixer.get_init()
        self.sounds = {
            "shoot": self.make(self.sweep(1400, 500, 0.06), 0.4),
            "zap": self.make(self.sweep(2400, 900, 0.08), 0.4),
            "shieldhit": self.make(self.sweep(600, 200, 0.2) * 0.7 + self.noise(0.2, 6) * 0.3, 0.35),
            "hit": self.make(self.noise(0.05, 8), 0.3),
            "boom": self.make(self.noise(0.35, 5, smooth=6)),
            "bigboom": self.make(self.noise(1.2, 3, smooth=12), 1.0),
            "die": self.make(self.sweep(800, 60, 0.6) * 0.6 + self.noise(0.6, 3, smooth=4) * 0.6),
            "powerup": self.make(np.concatenate([self.sweep(midi(n), midi(n), 0.06) for n in (72, 76, 79, 84)])),
            "bomb": self.make(self.noise(1.0, 2, smooth=20), 1.0),
            "alarm": self.make(np.concatenate([self.sweep(f, f, 0.18) for f in (880, 660) * 4]), 0.6),
            "dart": self.make(self.sweep(300, 1200, 0.15), 0.3),
            "laser": self.make(self.sweep(220, 140, 1.0) * 0.6 + self.noise(1.0, 1) * 0.4, 0.35),
        }
        pygame.mixer.set_reserved(1)  # sound effects never steal the music channel
        self.music_ch = pygame.mixer.Channel(0)
        self.songs = {spec["name"]: self.make(self.song(spec), MUSIC_VOLUME) for spec in SONGS}
        self.current = None

    def make(self, wave, vol=SFX_VOLUME):
        a = (np.clip(wave, -1, 1) * 32767 * vol).astype(np.int16)
        if self.channels > 1:
            a = np.repeat(a[:, None], self.channels, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(a))

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()

    def play_song(self, name):
        """Loop the named song; keeps going without a restart if it's already on."""
        if self.sounds and self.current != name:
            self.current = name
            self.music_ch.play(self.songs[name], loops=-1)

    def stop_song(self):
        if self.sounds:
            self.current = None
            self.music_ch.stop()

    def sweep(self, f0, f1, dur):
        n = int(self.rate * dur)
        phase = 2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / self.rate
        return np.sign(np.sin(phase)) * np.linspace(1, 0, n)

    def noise(self, dur, decay, smooth=1):
        n = np.random.uniform(-1, 1, int(self.rate * dur))
        if smooth > 1:  # crude low-pass for a deeper rumble
            n = np.convolve(n, np.ones(smooth) / smooth, mode="same") * math.sqrt(smooth)
        return n * np.exp(-decay * np.linspace(0, 1, len(n)))

    def song(self, spec):
        """Render a SONGS entry: square bass, pulse-wave arpeggio, kick, snare and hats."""
        step = int(self.rate * 60 / spec["bpm"] / 4)  # samples per 16th note
        chords = spec["chords"]
        t = np.arange(step) / self.rate
        env = np.exp(-np.linspace(0, 5, step))
        kick_f = 150 * np.exp(-t * 30) + 40
        kick = np.sin(2 * np.pi * np.cumsum(kick_f) / self.rate) * np.exp(-t * 20)
        snare = (0.7 * np.random.uniform(-1, 1, step) + 0.3 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 25)
        hat = np.random.uniform(-1, 1, step) * np.exp(-t * 200)
        out = np.zeros(step * 16 * len(chords) * 2)
        for rep in range(2):
            for b, chord in enumerate(chords):
                tones = chord + tuple(n + 12 for n in chord)
                for i in range(16):
                    pos = ((rep * len(chords) + b) * 16 + i) * step
                    seg = out[pos:pos + step]
                    if spec["bass"][i] is not None:
                        bass = chord[0] - 24 + spec["bass"][i]
                        seg += 0.35 * np.sign(np.sin(2 * np.pi * midi(bass) * t)) * env ** 0.3
                    if spec["arp"][i] is not None:
                        lead = tones[spec["arp"][i]] + 12 * rep
                        seg += 0.15 * (((t * midi(lead)) % 1 < spec["duty"]) * 2 - 1) * env
                    if i in spec["hat"]:
                        seg += 0.08 * hat
                    if i in spec["snare"]:
                        seg += 0.3 * snare
                    if i in spec["kick"]:
                        seg += 0.6 * kick
        return out / np.abs(out).max()


class Player:
    def __init__(self):
        self.x, self.y = PLAYER_START
        self.lives = PLAYER_LIVES
        self.bombs = START_BOMBS
        self.weapon = START_WEAPON
        self.shield = 0
        self.cool = 0
        self.invuln = INVULN_FRAMES
        self.dead = 0  # frames left until respawn
        self.god = False

    def hitbox(self):
        return pygame.Rect(self.x - 2, self.y - 2, 4, 4)


class Enemy:
    def __init__(self, kind, x, y, stage):
        self.kind, self.x, self.y, self.base_y = kind, x, y, y
        self.stage = stage
        self.hp = ENEMY_HP[kind] + stage // 3
        self.t = self.flash = 0
        self.vy = 0.0

    def rect(self):
        w, h = ENEMY_SIZE[self.kind]
        return pygame.Rect(self.x - w / 2, self.y - h / 2, w, h)

    def update(self, game):
        self.t += 1
        self.flash = max(0, self.flash - 1)
        speed = 1 + 0.15 * self.stage
        if self.kind == "drone":
            self.x -= 1.2 * speed
            self.y = self.base_y + math.sin(self.t * 0.07) * 22
            if self.stage >= 2 and random.random() < 0.004:
                game.fire_at(self.x, self.y, ENEMY_BULLET_SPEED)
        elif self.kind == "dart":
            if self.t < DART_AIM_FRAMES:
                self.x -= 0.6
            else:
                if self.t == DART_AIM_FRAMES:  # lock on, then charge
                    self.vy = clamp((game.player.y - self.y) / 60, -1.5, 1.5)
                    game.sfx.play("dart")
                self.x -= 3.2 * speed
                self.y += self.vy
        elif self.kind == "mine":  # slow drifter; bursts into a bullet ring when shot (see Game.kill)
            self.x -= 0.4 * speed
            self.y = self.base_y + math.sin(self.t * 0.04) * 4
        elif self.kind == "weaver":  # steers towards the player's height, overshooting into a weave
            self.x -= 1.3 * speed
            if self.x > game.player.x:
                self.vy += WEAVER_TURN if game.player.y > self.y else -WEAVER_TURN
                self.vy = clamp(self.vy, -WEAVER_MAX_VY, WEAVER_MAX_VY)
            self.y += self.vy
        elif self.kind == "gunship":  # parks on the right tracking the player, then breaks off
            if self.t < GUNSHIP_STAY:
                self.x = max(GUNSHIP_X, self.x - 1)
                self.y += clamp(game.player.y - self.y, -0.5, 0.5)
                if self.t % GUNSHIP_FIRE_INTERVAL == 0 and self.x < W - 8:
                    game.fire_at(self.x - 10, self.y, ENEMY_BULLET_SPEED * speed, count=3, spread=0.25)
            else:
                self.x -= 1.5 * speed
        else:  # turret
            self.x -= 0.5
            if self.t % max(40, 100 - self.stage * 10) == 0 and self.x < W - 8:
                game.fire_at(self.x, self.y, ENEMY_BULLET_SPEED * speed)
        return self.x > -20


class Boss:
    def __init__(self, stage):
        self.x, self.y = W + 40, H / 2
        self.hp = self.max_hp = BOSS_BASE_HP + BOSS_HP_PER_STAGE * (stage - 1)
        self.stage = stage
        self.idx = (stage - 1) % len(BOSSES)
        self.kind = BOSSES[self.idx]
        self.t = self.flash = self.dying = 0

    def rect(self):
        w, h = self.kind["size"]
        return pygame.Rect(self.x - w / 2, self.y - h / 2, w, h)

    def at(self, offset):
        return self.x + offset[0], self.y + offset[1]

    def pattern(self):
        pats = self.kind["patterns"]
        return pats[(self.t // BOSS_PATTERN_FRAMES) % len(pats)]

    def laser_state(self):
        """'charge', 'fire' or None; the beam runs from the first gun to the left edge."""
        if self.dying or not self.ready() or self.pattern() != "laser":
            return None
        c = self.t % LASER_CYCLE
        return "charge" if c < LASER_CHARGE else "fire" if c < LASER_END else None

    def ready(self):
        return self.t > 0 and not self.dying  # t starts ticking once the entrance is done

    def update(self, game):
        self.flash = max(0, self.flash - 1)
        if self.t == 0 and self.x > BOSS_X:  # entrance; afterwards the drift may cross BOSS_X
            self.x -= 1
            return
        self.t += 1
        swing_y, swing_x = self.kind["swing"]
        self.y = H / 2 + math.sin(self.t * 0.02) * swing_y
        self.x = BOSS_X + math.sin(self.t * 0.011) * swing_x
        rage = 2 if self.hp < self.max_hp * 0.3 else 1
        speed = 1.6 + 0.2 * self.stage
        pattern, core, gun = self.pattern(), self.at(self.kind["core"]), self.at(self.kind["guns"][0])
        if pattern == "fan" and self.t % (40 // rage) == 0:  # aimed fan from every cannon
            for g in self.kind["guns"]:
                game.fire_at(*self.at(g), speed, count=3, spread=0.3)
        elif pattern == "fan5" and self.t % (50 // rage) == 0:
            game.fire_at(*gun, speed, count=5, spread=0.22)
        elif pattern.startswith("spiral") and self.t % (6 // rage) == 0:
            arms = 4 if pattern == "spiral4" else 2
            for k in range(arms):
                game.fire_dir(*core, self.t * 0.17 + k * math.tau / arms, speed * 0.8)
        elif pattern == "ring" and self.t % (60 // rage) == 0:
            for i in range(16):
                game.fire_dir(*core, i * math.tau / 16 + self.t, speed * 0.7)
        elif pattern == "stream" and (self.t // 40) % 2 == 0 and self.t % (8 // rage) == 0:  # machine gun bursts
            game.fire_at(*gun, speed * 1.2)
        elif pattern == "launch" and self.t % (90 // rage) == 0 and len(game.enemies) < BOSS_MAX_ESCORTS:
            game.enemies.append(Enemy("drone", *core, self.stage))
        elif pattern == "minelay" and self.t % (80 // rage) == 0 and len(game.enemies) < BOSS_MAX_ESCORTS:
            game.enemies.append(Enemy("mine", *core, self.stage))
        elif pattern == "sweep" and self.t % (6 // rage) == 0:  # hose swinging up and down
            game.fire_dir(*gun, math.pi + math.sin(self.t * 0.05) * 0.7, speed)
        elif pattern == "scatter" and self.t % (5 // rage) == 0:  # random spray at uneven speeds
            game.fire_dir(*gun, math.pi + random.uniform(-0.7, 0.7), speed * random.uniform(0.5, 1.0))
        elif pattern == "laser" and self.t % LASER_CYCLE == LASER_CHARGE:
            game.sfx.play("laser")


class Game:
    def __init__(self):
        pygame.init()
        self.fullscreen = False
        self.set_display()
        pygame.display.set_caption("NEON STRIKER '96")
        self.screen = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 15)
        self.mid_font = pygame.font.Font(None, 24)
        self.sfx = Sfx()
        self.spr = {"player": make_sprite(PLAYER_ART), "drone": make_sprite(DRONE_ART),
                    "dart": make_sprite(DART_ART), "weaver": make_sprite(WEAVER_ART),
                    "gunship": make_sprite(GUNSHIP_ART)}
        self.spr.update({f"boss{i}": b["draw"]() for i, b in enumerate(BOSSES)})
        self.flash_spr = {k: white_silhouette(v) for k, v in self.spr.items()}
        for k, v in self.flash_spr.items():  # boss gets hit constantly, so flash it softer
            v.set_alpha(FLASH_ALPHA_BOSS if k.startswith("boss") else FLASH_ALPHA)
        self.mini_ship = pygame.transform.scale(self.spr["player"], (8, 5))
        self.logo = self.make_logo()
        self.hiscore = self.load_hiscore()
        self.stars = [[random.uniform(0, W), random.uniform(HUD_TOP, 62), random.choice((0.2, 0.5, 1.0))]
                      for _ in range(70)]
        self.frame = self.scroll = self.shake = self.bomb_flash = 0
        self.autopilot = self.demo = self.paused = False
        self.stage = 1
        self.set_theme(0)
        self.to_title()

    # --- setup ---------------------------------------------------------------
    def set_display(self):
        """(Re)create the window and the scanline overlay for the current scale."""
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((W * SCALE, H * SCALE))
        pygame.mouse.set_visible(not self.fullscreen)
        ww, wh = self.window.get_size()
        self.scale = max(1, min(ww // W, wh // H))  # integer scale keeps pixels square
        self.offset = ((ww - W * self.scale) // 2, (wh - H * self.scale) // 2)  # letterbox
        self.scanlines = pygame.Surface((W * self.scale, H * self.scale), pygame.SRCALPHA)
        for y in range(self.scale - 1, H * self.scale, self.scale):
            pygame.draw.line(self.scanlines, (0, 0, 0, SCANLINE_ALPHA), (0, y), (W * self.scale, y))

    def load_hiscore(self):
        try:
            return int(HISCORE_FILE.read_text())
        except (OSError, ValueError):
            return HISCORE_DEFAULT

    def make_logo(self):
        font = pygame.font.Font(None, 44)
        txt = font.render("NEON STRIKER", False, WHITE).convert_alpha()
        w, h = txt.get_size()
        grad = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):  # chrome: cool sky on top, hot sunset below the "horizon"
            t = y / h
            c = lerp((120, 240, 255), WHITE, t * 2) if t < 0.5 else lerp((255, 60, 180), (255, 200, 40), t * 2 - 1)
            pygame.draw.line(grad, c, (0, y), (w, y))
        grad.blit(txt, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        out = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
        edge = font.render("NEON STRIKER", False, (40, 0, 60))
        for ox, oy in ((0, 0), (4, 4), (0, 4), (4, 0), (2, 0), (0, 2), (4, 2), (2, 4)):
            out.blit(edge, (ox, oy))
        out.blit(grad, (2, 2))
        return out

    def set_theme(self, i):
        th = THEMES[i % len(THEMES)]
        self.grid_color = th["grid"]
        self.bg = pygame.Surface((W, H))
        for y in range(GROUND_Y):
            pygame.draw.line(self.bg, lerp(*th["sky"], y / GROUND_Y), (0, y), (W, y))
        cx, cy, r = int(W * 0.7), GROUND_Y - 32, 38
        for dy in range(-r, r):  # striped retro sun, gaps widen toward the horizon
            if dy > 0 and dy % 7 < dy / 6:
                continue
            half = math.sqrt(r * r - dy * dy)
            pygame.draw.line(self.bg, lerp(*th["sun"], (dy + r) / (2 * r)), (cx - half, cy + dy), (cx + half, cy + dy))
        self.bg.fill(th["floor"], (0, GROUND_Y, W, H - GROUND_Y))
        self.mountains = [(self.make_mountains(th["far"], 30, 0.25), 0.25),
                          (self.make_mountains(th["near"], 22, 0.6), 0.6)]

    def make_mountains(self, color, amp, seed):
        rnd = random.Random(seed)
        waves = [(rnd.randint(1, 3) * k, rnd.uniform(0, math.tau), amp / k) for k in (1, 2, 5, 11)]
        s = pygame.Surface((W, GROUND_Y), pygame.SRCALPHA)
        top = lerp(color, WHITE, 0.25)
        for x in range(W):  # integer frequencies => the layer tiles seamlessly
            h = amp * 0.6 + sum(a * math.sin(math.tau * f * x / W + p) for f, p, a in waves) * 0.5
            y = int(GROUND_Y - max(4, h))
            pygame.draw.line(s, color, (x, y), (x, GROUND_Y))
            s.set_at((x, y), top)
        return s

    # --- state changes ---------------------------------------------------------
    def to_title(self):
        self.state, self.state_t = "title", 0
        self.autopilot = self.demo = self.paused = False
        self.sfx.play_song(STAGE_SONGS[0])

    def start(self, demo=False):
        self.demo = self.autopilot = demo
        self.player = Player()
        self.score = 0
        self.credits = START_CREDITS
        self.stage = START_STAGE
        self.begin_stage()
        self.state, self.state_t = "play", 0

    def begin_stage(self):
        self.set_theme(self.stage - 1)
        self.sfx.play_song(STAGE_SONGS[(self.stage - 1) % len(STAGE_SONGS)])
        self.enemies, self.pbullets, self.ebullets, self.pickups = [], [], [], []
        self.particles, self.rings, self.popups = [], [], []
        self.boss = None
        self.stage_t = self.warning = self.clear_t = 0
        self.wave_t = FPS
        self.player.x, self.player.y = PLAYER_START
        self.player.invuln = INVULN_FRAMES

    def game_over(self):
        if self.demo:
            self.to_title()
            return
        self.new_record = self.score > self.hiscore
        if self.new_record:
            self.hiscore = self.score
            HISCORE_FILE.write_text(str(self.score))
        self.state, self.state_t = "gameover", 0

    def continue_game(self):
        p = self.player
        p.lives, p.bombs, p.dead = PLAYER_LIVES, START_BOMBS, 0
        p.x, p.y = PLAYER_START
        p.invuln = INVULN_FRAMES
        self.score = 0  # arcade rules: continuing resets your score
        self.credits -= 1
        self.state, self.state_t = "play", 0

    # --- input -------------------------------------------------------------------
    def on_key(self, key):
        start_keys = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_z)
        if key == pygame.K_F11:
            self.fullscreen = not self.fullscreen
            self.set_display()
        elif self.state == "title":
            if key in start_keys:
                self.start()
            self.state_t = 0
        elif self.state == "play" and self.demo:
            self.to_title()
        elif self.state == "play":
            if key in (pygame.K_x, pygame.K_k) and not self.paused:
                self.bomb()
            elif key == pygame.K_p:
                self.paused = not self.paused
        elif self.state == "gameover" and key in start_keys and self.state_t > FPS // 2:
            if self.credits:
                self.continue_game()
            else:
                self.to_title()

    def read_controls(self):
        if self.autopilot:
            return self.autopilot_input()
        k = pygame.key.get_pressed()
        dx = (k[pygame.K_RIGHT] or k[pygame.K_d]) - (k[pygame.K_LEFT] or k[pygame.K_a])
        dy = (k[pygame.K_DOWN] or k[pygame.K_s]) - (k[pygame.K_UP] or k[pygame.K_w])
        return dx, dy, k[pygame.K_z] or k[pygame.K_SPACE] or k[pygame.K_j]

    def autopilot_input(self):
        """Attract-mode pilot: line up with the closest target, sidestep close bullets."""
        p = self.player
        targets = self.enemies + ([self.boss] if self.boss else [])
        ty = min(targets, key=lambda e: abs(e.x - p.x)).y if targets else H / 2
        if self.boss and self.boss.laser_state():
            by = self.boss.at(self.boss.kind["guns"][0])[1]
            if abs(p.y - by) < 30:
                ty = by - 40 if by > H / 2 else by + 40
        for b in self.ebullets:
            if 0 < b[0] - p.x < 35 and abs(b[1] - p.y) < 10:
                ty = p.y + (14 if b[1] < p.y else -14)
                break
        dy = 0 if abs(ty - p.y) < 2 else (1 if ty > p.y else -1)
        dx = 0 if abs(60 - p.x) < 2 else (1 if p.x < 60 else -1)
        if p.bombs and len(self.ebullets) > 25 and not p.invuln:
            self.bomb()
        return dx, dy, True

    # --- gameplay ----------------------------------------------------------------
    def fire_at(self, x, y, speed, count=1, spread=0.0):
        base = math.atan2(self.player.y - y, self.player.x - x)
        for i in range(count):
            self.fire_dir(x, y, base + (i - (count - 1) / 2) * spread, speed)

    def fire_dir(self, x, y, angle, speed):
        self.ebullets.append([x, y, math.cos(angle) * speed, math.sin(angle) * speed])

    def shoot(self):
        p = self.player
        p.cool = FIRE_COOLDOWN
        shots = [(0, 0)] if p.weapon == 1 else [(-3, 0), (3, 0)]
        if p.weapon >= 3:
            shots += [(-3, -1.2), (3, 1.2)]
        for oy, vy in shots:  # bullets remember the weapon level for damage and looks
            self.pbullets.append([p.x + 8, p.y + oy, PLAYER_BULLET_SPEED, vy, p.weapon])
        self.sfx.play("zap" if p.weapon >= LASER_LEVEL else "shoot")

    def bomb(self):
        p = self.player
        if p.bombs <= 0 or p.dead:
            return
        p.bombs -= 1
        self.bomb_flash, self.shake = BOMB_FLASH_FRAMES, 12
        self.ebullets.clear()
        self.rings.append([p.x, p.y, 4, W])
        for e in self.enemies:
            e.hp -= BOMB_DAMAGE
        if self.boss and self.boss.ready():
            self.boss.hp -= BOMB_BOSS_DAMAGE
            self.boss.flash = HIT_FLASH_FRAMES * 4
        self.sfx.play("bomb")

    def explode(self, x, y, n=20, speed=2.5, ring=12):
        for _ in range(n):
            a, s = random.uniform(0, math.tau), random.uniform(0.3, speed)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, random.randint(15, 35), random.choice(FIRE)])
        if ring:
            self.rings.append([x, y, 2, ring])

    def add_score(self, pts, x, y):
        self.score += pts
        self.popups.append([x, y, str(pts), 40])

    def kill(self, e):
        self.add_score(ENEMY_SCORE[e.kind], e.x, e.y)
        self.explode(e.x, e.y, 25 if e.kind in ("turret", "gunship") else 14)
        if e.kind == "mine" and not self.bomb_flash:  # bombs defuse mines
            for i in range(MINE_BURST):
                self.fire_dir(e.x, e.y, i * math.tau / MINE_BURST, ENEMY_BULLET_SPEED)
        self.shake = max(self.shake, 3)
        self.sfx.play("boom")
        if random.random() < DROP_CHANCE:
            kind = random.choices("PBS1", weights=(6, 3, 2, 1))[0]
            self.pickups.append([e.x, e.y, kind, 0])

    def player_hit(self):
        p = self.player
        if p.shield:  # the bubble pops instead of the ship
            p.shield -= 1
            p.invuln = SHIELD_HIT_INVULN
            self.rings.append([p.x, p.y, SHIELD_RADIUS, SHIELD_RADIUS * 3])
            self.shake = max(self.shake, 4)
            self.sfx.play("shieldhit")
            return
        p.lives -= 1
        p.dead = RESPAWN_FRAMES
        p.weapon = max(1, p.weapon - 1)
        self.explode(p.x, p.y, 50, 3.5, 30)
        self.shake = 15
        self.ebullets.clear()  # a little mercy
        self.sfx.play("die")

    def update(self):
        self.frame += 1
        self.state_t += 1
        if not self.paused:
            self.scroll += SCROLL_SPEED
            for s in self.stars:
                s[0] = (s[0] - s[2]) % W
        self.shake = max(0, self.shake - 1)
        self.bomb_flash = max(0, self.bomb_flash - 1)
        if self.state == "title" and self.state_t > ATTRACT_DELAY:
            self.start(demo=True)
        elif self.state == "play" and not self.paused:
            if self.demo and self.state_t > DEMO_FRAMES:
                self.to_title()
                return
            self.update_play()
            self.update_fx()
        elif self.state == "gameover":
            self.update_fx()
            if self.state_t > ((CONTINUE_SECONDS + 1) * FPS if self.credits else NO_CREDITS_FRAMES):
                self.to_title()

    def update_play(self):
        p = self.player
        dx, dy, fire = self.read_controls()
        if p.dead:
            p.dead -= 1
            if p.dead == 0:
                if p.lives <= 0:
                    self.game_over()
                    return
                p.x, p.y = PLAYER_START
                p.invuln = INVULN_FRAMES
        else:
            norm = math.sqrt(0.5) if dx and dy else 1
            p.x = clamp(p.x + dx * PLAYER_SPEED * norm, 8, W - 8)
            p.y = clamp(p.y + dy * PLAYER_SPEED * norm, HUD_TOP + 6, H - 6)
            p.invuln = max(0, p.invuln - 1)
            p.cool = max(0, p.cool - 1)
            if fire and p.cool == 0:
                self.shoot()

        self.update_spawning()
        self.enemies = [e for e in self.enemies if e.update(self)]
        self.update_boss()
        for b in self.pbullets + self.ebullets:
            b[0] += b[2]
            b[1] += b[3]
        self.pbullets = [b for b in self.pbullets if b[0] < W + 8 and -4 < b[1] < H + 4]
        self.ebullets = [b for b in self.ebullets if -6 < b[0] < W + 6 and -6 < b[1] < H + 6]
        for pk in self.pickups:
            pk[3] += 1
            pk[0] -= 0.6
            pk[1] += math.sin(pk[3] * 0.1) * 0.5
        self.pickups = [pk for pk in self.pickups if pk[0] > -10]
        self.collide()

    def update_spawning(self):
        if self.clear_t:
            self.clear_t -= 1
            if self.clear_t == 0:
                self.stage += 1
                self.begin_stage()
            return
        self.stage_t += 1
        if self.stage_t < STAGE_FRAMES:
            self.wave_t -= 1
            if self.wave_t <= 0:
                self.spawn_wave()
                self.wave_t = max(WAVE_INTERVAL_MIN, WAVE_INTERVAL - self.stage * WAVE_SPEEDUP)
        elif self.warning:
            self.warning -= 1
            if self.warning == 0:
                self.boss = Boss(self.stage)
                self.sfx.play_song(BOSS_SONG)
        elif self.boss is None and not self.enemies:
            self.warning = WARNING_FRAMES
            self.sfx.stop_song()  # the alarm gets the stage to itself
            self.sfx.play("alarm")

    def spawn_wave(self):
        kinds = ["drones", "drones", "darts", "turrets", "mines"] + (["mixed"] * 2 if self.stage > 1 else [])
        if self.stage >= WEAVER_FIRST_STAGE:
            kinds.append("weavers")
        if self.stage >= GUNSHIP_FIRST_STAGE:
            kinds.append("gunship")
        kind = random.choice(kinds)
        y = random.uniform(HUD_TOP + 30, H - 30)
        if kind in ("drones", "mixed"):
            self.enemies += [Enemy("drone", W + 10 + i * 18, y, self.stage) for i in range(5)]
        if kind == "darts":
            self.enemies += [Enemy("dart", W + 10 + i * 25, random.uniform(HUD_TOP + 10, H - 10), self.stage)
                             for i in range(3)]
        if kind in ("turrets", "mixed"):
            self.enemies += [Enemy("turret", W + 10 + i * 40, random.uniform(HUD_TOP + 20, H - 20), self.stage)
                             for i in range(2 if kind == "turrets" else 1)]
        if kind == "mines":
            self.enemies += [Enemy("mine", W + 10 + i * 30, random.uniform(HUD_TOP + 15, H - 15), self.stage)
                             for i in range(2)]
        if kind == "weavers":  # alternate between entering high and low
            self.enemies += [Enemy("weaver", W + 10 + i * 20, HUD_TOP + 10 if i % 2 else H - 10, self.stage)
                             for i in range(3)]
        if kind == "gunship":
            self.enemies.append(Enemy("gunship", W + 15, y, self.stage))

    def update_boss(self):
        b = self.boss
        if not b:
            return
        if not b.dying:
            b.update(self)
            if b.hp <= 0:
                b.dying = BOSS_DEATH_FRAMES
                self.ebullets.clear()
            return
        b.dying -= 1
        if b.dying % 6 == 0:  # chain of explosions across the hull
            r = b.rect()
            self.explode(random.uniform(r.left, r.right), random.uniform(r.top, r.bottom), 15, 2, 10)
            self.shake = 6
            self.sfx.play("boom")
        if b.dying == 0:
            self.explode(b.x, b.y, 150, 5, 80)
            self.add_score(BOSS_BONUS * self.stage, b.x, b.y)
            self.shake = 25
            self.sfx.play("bigboom")
            self.boss = None
            self.clear_t = CLEAR_FRAMES

    def collide(self):
        p = self.player
        targets = list(self.enemies)
        if self.boss and self.boss.ready():
            targets.append(self.boss)
        kept = []
        for b in self.pbullets:
            hit = next((e for e in targets if e.hp > 0 and e.rect().collidepoint(b[0], b[1])), None)
            if hit:
                hit.hp -= WEAPON_DAMAGE[b[4] - 1]
                hit.flash = HIT_FLASH_FRAMES
                self.particles.append([b[0], b[1], -1, random.uniform(-1, 1), 6, WHITE])
                self.sfx.play("hit")
            else:
                kept.append(b)
        self.pbullets = kept
        for e in self.enemies:
            if e.hp <= 0:
                self.kill(e)
        self.enemies = [e for e in self.enemies if e.hp > 0]
        if p.dead:
            return
        grab = pygame.Rect(p.x - 8, p.y - 5, 16, 10)
        for pk in [pk for pk in self.pickups if grab.collidepoint(pk[0], pk[1])]:
            self.pickups.remove(pk)
            if pk[2] == "P" and p.weapon < MAX_WEAPON:
                p.weapon += 1
            elif pk[2] == "P":
                self.add_score(1000, pk[0], pk[1])
            elif pk[2] == "S" and p.shield < MAX_SHIELD:
                p.shield += 1
            elif pk[2] == "S":
                self.add_score(1000, pk[0], pk[1])
            elif pk[2] == "B" and p.bombs < MAX_BOMBS:
                p.bombs += 1
            elif pk[2] == "1" and p.lives < MAX_LIVES:
                p.lives += 1
            else:
                self.add_score(1000, pk[0], pk[1])
            self.sfx.play("powerup")
        if p.invuln or p.god:
            return
        hb = p.hitbox()
        beam_hit = False
        if self.boss and self.boss.laser_state() == "fire":
            bx, by = self.boss.at(self.boss.kind["guns"][0])
            beam_hit = p.x < bx and abs(p.y - by) < LASER_HALF_WIDTH + 2
        if beam_hit or any(hb.colliderect(e.rect()) for e in targets) or \
                any(hb.inflate(2, 2).collidepoint(b[0], b[1]) for b in self.ebullets):
            self.player_hit()

    def update_fx(self):
        for pt in self.particles:
            pt[0] += pt[2]
            pt[1] += pt[3]
            pt[2] *= 0.95
            pt[3] *= 0.95
            pt[4] -= 1
        self.particles = [pt for pt in self.particles if pt[4] > 0]
        for r in self.rings:
            r[2] += max(1.0, r[3] / 20)
        self.rings = [r for r in self.rings if r[2] < r[3]]
        for pu in self.popups:
            pu[1] -= 0.4
            pu[3] -= 1
        self.popups = [pu for pu in self.popups if pu[3] > 0]

    # --- drawing -----------------------------------------------------------------
    def text(self, msg, x, y, color=WHITE, font=None, align="left"):
        font = font or self.font
        img = font.render(msg, False, color)
        x -= {"left": 0, "center": img.get_width() // 2, "right": img.get_width()}[align]
        self.screen.blit(font.render(msg, False, BLACK), (x + 1, y + 1))
        self.screen.blit(img, (x, y))

    def blink(self, period=40):
        return self.frame % period < period // 2

    def draw_background(self):
        s = self.screen
        s.blit(self.bg, (0, 0))
        for x, y, layer in self.stars:
            s.fill(lerp((60, 60, 100), WHITE, layer), (int(x), int(y), 1, 1))
        for surf, speed in self.mountains:
            off = -(self.scroll * speed) % W
            s.blit(surf, (off - W, 0))
            s.blit(surf, (off, 0))
        c, dim = self.grid_color, lerp(self.grid_color, BLACK, 0.5)
        rows = 7
        for i in range(1, rows + 1):  # perspective-spaced horizontal lines
            y = GROUND_Y + int((H - GROUND_Y) * (i / rows) ** 2)
            pygame.draw.line(s, dim if i < 3 else c, (0, y), (W, y))
        spacing = 40
        off = -(self.scroll * 2) % spacing
        for k in range(-12, 13):  # vertical lines converge on the vanishing point
            xb = W / 2 + k * spacing + off
            pygame.draw.line(s, c, (W / 2 + (xb - W / 2) * 0.3, GROUND_Y), (xb, H))
        pygame.draw.line(s, lerp(c, WHITE, 0.5), (0, GROUND_Y), (W, GROUND_Y))

    def blit_center(self, key, x, y, flash=False):
        img = self.spr[key]
        pos = (int(x - img.get_width() / 2), int(y - img.get_height() / 2))
        self.screen.blit(img, pos)
        if flash:
            self.screen.blit(self.flash_spr[key], pos)

    def draw_world(self):
        s, p = self.screen, self.player
        for pk in self.pickups:
            col = {"P": (255, 60, 60), "B": (60, 120, 255), "S": (0, 190, 190), "1": (60, 220, 60)}[pk[2]]
            r = pygame.Rect(pk[0] - 5, pk[1] - 4, 11, 9)
            pygame.draw.rect(s, WHITE if self.blink(12) else col, r, border_radius=3)
            pygame.draw.rect(s, col, r.inflate(-2, -2), border_radius=2)
            self.text(pk[2], pk[0], pk[1] - 4, WHITE, align="center")
        for e in self.enemies:
            if e.kind == "turret":
                col = WHITE if e.flash else (255, 140, 0)
                pygame.draw.circle(s, col, (e.x, e.y), 5)
                for k in range(4):  # spinning spokes
                    a = e.t * 0.1 + k * math.pi / 2
                    pygame.draw.line(s, col, (e.x, e.y), (e.x + math.cos(a) * 7, e.y + math.sin(a) * 7), 2)
                pygame.draw.circle(s, (120, 0, 0), (e.x, e.y), 3)
                pygame.draw.circle(s, (255, 40, 60), (e.x - 1, e.y), 1)
            elif e.kind == "mine":
                col = WHITE if e.flash else (150, 150, 170)
                for k in range(4):  # spikes
                    a = k * math.pi / 4
                    dx, dy = math.cos(a) * 6, math.sin(a) * 6
                    pygame.draw.line(s, col, (e.x - dx, e.y - dy), (e.x + dx, e.y + dy))
                pygame.draw.circle(s, col, (e.x, e.y), 4)
                pygame.draw.circle(s, (255, 40, 60) if self.blink(20) else (100, 0, 0), (e.x, e.y), 2)
            else:
                self.blit_center(e.kind, e.x, e.y, e.flash > 0)
        if self.boss:
            b = self.boss
            if not (b.dying and self.blink(4)):
                self.blit_center(f"boss{b.idx}", b.x, b.y, b.flash > 0)
                pulse = (math.sin(self.frame * 0.2) + 1) / 2
                cx, cy = b.at(b.kind["core"])
                pygame.draw.circle(s, lerp((255, 40, 40), YELLOW, pulse), (cx, cy), 5)
                pygame.draw.circle(s, WHITE, (cx - 1, cy - 1), 2)
            laser = b.laser_state()
            bx, by = b.at(b.kind["guns"][0])
            if laser == "charge" and self.blink(4):  # telegraph where the beam will hit
                pygame.draw.line(s, (255, 120, 60), (0, by), (bx, by))
            elif laser == "fire":
                hw = LASER_HALF_WIDTH + random.randint(-1, 1)
                s.fill((255, 80, 30), (0, by - hw, bx, hw * 2))
                s.fill(YELLOW, (0, by - hw // 2, bx, hw))
                s.fill(WHITE, (0, by - 1, bx, 2))
        if not p.dead and p.lives > 0 and not (p.invuln and self.blink(6)):
            flame = random.randint(2, 6)
            s.fill(random.choice(FIRE[:3]), (p.x - 8 - flame, p.y - 1, flame, 3))
            self.blit_center("player", p.x, p.y)
        if p.shield and not p.dead and p.lives > 0:  # bubble: ring thickness = shield level
            r = SHIELD_RADIUS + int(math.sin(self.frame * 0.15) * 1.5)
            col = SHIELD_COLORS[p.shield - 1]
            bubble = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(bubble, (*col, 50), (r, r), r)
            pygame.draw.circle(bubble, (*col, 220), (r, r), r, p.shield)
            bubble.fill(WHITE, (r // 2, r // 2, 2, 2))  # glint
            s.blit(bubble, (p.x - r, p.y - r))
        for b in self.pbullets:
            if b[4] >= LASER_LEVEL:  # laser bolt: a streak along its flight path, thicker per level
                tail = (b[0] - b[2] * 2, b[1] - b[3] * 2)
                width = b[4] - LASER_LEVEL + 2
                pygame.draw.line(s, PINK if b[4] > LASER_LEVEL else CYAN, tail, (b[0], b[1]), width)
                pygame.draw.line(s, WHITE, tail, (b[0], b[1]))
            else:
                s.fill(YELLOW, (b[0] - 3, b[1] - 1, 6, 2))
                s.fill(WHITE, (b[0] + 1, b[1] - 1, 2, 2))
        for b in self.ebullets:
            pygame.draw.circle(s, PINK if self.blink(8) else (255, 140, 60), (b[0], b[1]), 2)
            s.fill(WHITE, (b[0], b[1], 1, 1))
        for pt in self.particles:
            size = 2 if pt[4] > 10 else 1
            s.fill(pt[5], (pt[0], pt[1], size, size))
        for r in self.rings:
            pygame.draw.circle(s, lerp(YELLOW, (255, 60, 30), r[2] / r[3]), (r[0], r[1]), int(r[2]), 1)
        for pu in self.popups:
            self.text(pu[2], pu[0], pu[1], YELLOW, align="center")
        if self.bomb_flash:
            flash = pygame.Surface((W, H))
            flash.fill(WHITE)
            flash.set_alpha(self.bomb_flash * 20)
            s.blit(flash, (0, 0))

    def draw_hud(self):
        p, s = self.player, self.screen
        self.text(f"1UP {self.score:07d}", 4, 2, CYAN)
        self.text(f"HI {max(self.hiscore, self.score):07d}", W // 2, 2, YELLOW, align="center")
        self.text(f"STAGE {self.stage}", W - 4, 2, PINK, align="right")
        s.blit(self.mini_ship, (4, H - 9))
        self.text(f"x{max(0, p.lives)}", 14, H - 12)
        pygame.draw.circle(s, (255, 140, 0), (40, H - 6), 3)
        self.text(f"x{p.bombs}", 46, H - 12)
        self.text("PWR " + "|" * p.weapon, 70, H - 12, (255, 90, 90))
        if p.shield:
            self.text("SHD " + "|" * p.shield, 124, H - 12, SHIELD_COLORS[p.shield - 1])
        if self.boss and not self.boss.dying:
            b = self.boss
            bar = pygame.Rect(W - 124, H - 8, 120, 4)
            pygame.draw.rect(s, (60, 0, 0), bar)
            pygame.draw.rect(s, (255, 40, 60), (bar.x, bar.y, bar.w * max(0, b.hp) / b.max_hp, bar.h))
            pygame.draw.rect(s, WHITE, bar.inflate(2, 2), 1)

    def draw(self):
        self.draw_background()
        if self.state == "title":
            self.draw_title()
            return
        self.draw_world()
        self.draw_hud()
        cx = W // 2
        if self.warning and self.blink(30):
            self.screen.fill((180, 0, 0), (0, 64, W, 30))
            self.text("WARNING!", cx, 66, WHITE, self.mid_font, "center")
            name = BOSSES[(self.stage - 1) % len(BOSSES)]["name"]
            self.text(f"{name} APPROACHING", cx, 82, YELLOW, align="center")
        if self.clear_t:
            self.text(f"STAGE {self.stage} CLEAR!", cx, 60, YELLOW, self.mid_font, "center")
            self.text(f"BOSS BONUS {BOSS_BONUS * self.stage}", cx, 82, CYAN, align="center")
        if self.demo:
            if self.blink():
                self.text("DEMO PLAY", cx, 40, WHITE, self.mid_font, "center")
            self.text("PRESS ENTER", cx, 60, YELLOW, align="center")
        if self.paused:
            self.text("PAUSED", cx, 70, WHITE, self.mid_font, "center")
        if self.state == "gameover":
            self.text("GAME OVER", cx, 50, (255, 60, 60), self.mid_font, "center")
            if self.new_record and self.blink(20):
                self.text("NEW HIGH SCORE!", cx, 72, YELLOW, align="center")
            if self.credits:
                left = max(0, CONTINUE_SECONDS - self.state_t // FPS)
                self.text(f"CONTINUE? {left}", cx, 88, WHITE, self.mid_font, "center")
                self.text(f"PRESS ENTER   CREDITS {self.credits}", cx, 108, CYAN, align="center")
            else:
                self.text("NO CREDITS LEFT", cx, 88, WHITE, self.mid_font, "center")

    def draw_title(self):
        cx = W // 2
        lx = cx - self.logo.get_width() // 2
        self.screen.blit(self.logo, (lx, 28 + int(math.sin(self.frame * 0.05) * 3)))
        self.text("'96", lx + self.logo.get_width() - 10, 58, YELLOW, self.mid_font)
        self.text(f"HI-SCORE {self.hiscore:07d}", cx, 84, CYAN, align="center")
        if self.blink():
            self.text("INSERT COIN - PRESS ENTER", cx, 100, WHITE, align="center")
        self.text("ARROWS MOVE   Z FIRE   X BOMB   P PAUSE", cx, 138, (200, 200, 255), align="center")
        self.text("F11 FULLSCREEN", cx, 150, (200, 200, 255), align="center")

    def present(self):
        ox, oy = self.offset
        if self.shake:
            ox, oy = (o + random.randint(-self.shake, self.shake) * self.scale // 3 for o in self.offset)
        self.window.fill(BLACK)
        self.window.blit(pygame.transform.scale(self.screen, (W * self.scale, H * self.scale)), (ox, oy))
        self.window.blit(self.scanlines, self.offset)
        pygame.display.flip()

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    return
                if e.type == pygame.KEYDOWN:
                    self.on_key(e.key)
            self.update()
            self.draw()
            self.present()
            self.clock.tick(FPS)


def selftest():
    """Invincible autopilot must beat all eight bosses without crashing."""
    random.seed(0)  # deterministic run
    g = Game()
    g.start()
    for left in range(START_CREDITS, 0, -1):  # each continue spends one credit
        g.game_over()
        g.state_t = FPS
        g.on_key(pygame.K_RETURN)
        assert g.state == "play" and g.credits == left - 1, "continue should spend a credit"
    g.game_over()
    g.state_t = FPS
    g.on_key(pygame.K_RETURN)
    assert g.state == "title", "with no credits left, Enter goes back to the title"
    g.start(demo=True)
    g.demo = False  # keep autopilot but skip the demo timeout
    g.player.shield = 1
    g.player_hit()
    assert g.player.shield == 0 and g.player.lives == PLAYER_LIVES, "shield should absorb the hit"
    g.kill(Enemy("mine", W / 2, H / 2, g.stage))
    assert len(g.ebullets) == MINE_BURST, "a shot-down mine should burst into a bullet ring"
    g.ebullets.clear()
    g.player.lives, g.player.bombs = MAX_LIVES, MAX_BOMBS
    g.pickups = [[g.player.x, g.player.y, kind, 0] for kind in "1B"]
    g.collide()
    assert (g.player.lives, g.player.bombs) == (MAX_LIVES, MAX_BOMBS) and not g.pickups, \
        "a 1UP or B at max should only score"
    g.player.lives, g.player.bombs = PLAYER_LIVES, START_BOMBS
    g.player.god = True
    for _ in range(SELFTEST_FRAMES):
        g.update()
        g.draw()
        g.present()
        if g.stage > len(BOSSES):  # all bosses beaten
            break
    assert g.state == "play" and g.stage > len(BOSSES), f"stuck in {g.state} on stage {g.stage}"
    print(f"selftest ok: stage {g.stage}, score {g.score}")


def parse_args():
    """Command-line options; the defaults are the constants above."""
    def in_range(low, high=None):
        def check(text):
            value = int(text)
            if value < low:
                raise argparse.ArgumentTypeError(f"must be at least {low}")
            if high is not None and value > high:
                raise argparse.ArgumentTypeError(f"must be at most {high}")
            return value
        return check

    parser = argparse.ArgumentParser(description="NEON STRIKER '96")
    parser.add_argument("--selftest", action="store_true", help="headless autopilot run")
    parser.add_argument("--lives", type=in_range(1, MAX_LIVES), default=PLAYER_LIVES,
                        help=f"lives per credit (default {PLAYER_LIVES})")
    parser.add_argument("--credits", type=in_range(0, MAX_CREDITS), default=START_CREDITS,
                        help=f"continues per game (default {START_CREDITS})")
    parser.add_argument("--start-weapon-level", type=int, default=START_WEAPON,
                        choices=range(1, MAX_WEAPON + 1), metavar=f"1-{MAX_WEAPON}",
                        help=f"weapon level at game start (default {START_WEAPON})")
    parser.add_argument("--start-level", type=in_range(1), default=START_STAGE,
                        help=f"stage a new game begins on (default {START_STAGE})")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # override the module defaults; everything reads them at runtime
    PLAYER_LIVES, START_CREDITS, START_WEAPON = args.lives, args.credits, args.start_weapon_level
    START_STAGE = args.start_level
    if args.selftest:
        selftest()
    else:
        Game().run()
    pygame.quit()
