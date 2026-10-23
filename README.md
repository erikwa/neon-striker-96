# NEON STRIKER '96

A 90s-style side-scrolling arcade shooter in a single Python file. All graphics,
sound effects and chiptune music are generated at startup, no asset files needed.

## Install

Requires Python 3 (tested with 3.14).

```sh
python3 -m venv .venv
.venv/bin/pip install pygame-ce numpy
```

Or with [uv](https://docs.astral.sh/uv/):

```sh
uv venv .venv
uv pip install --python .venv/bin/python pygame-ce numpy
```

## Run

```sh
.venv/bin/python neon_striker.py
```

Options (see `--help`):

| Option                     | Default | Meaning                    |
|----------------------------|---------|----------------------------|
| `--lives=N`                | 3       | Lives per credit (1-99)    |
| `--credits=N`              | 3       | Continues per game (0-99)  |
| `--start-weapon-level=N`   | 1       | Weapon level (1-5) at start |
| `--start-level=N`          | 1       | Stage a new game begins on |

## Controls

| Key              | Action                     |
|------------------|----------------------------|
| Arrows / WASD    | Move                       |
| Z / Space (hold) | Fire                       |
| X                | Bomb (clears bullets)      |
| P                | Pause                      |
| F11              | Toggle fullscreen          |
| Enter            | Start / continue           |
| Esc              | Quit                       |

Leave the title screen idle for a few seconds to watch the attract-mode demo.
Power-ups: **P** weapon level (5 levels), **B** extra bomb, **S** shield bubble
(up to 3 levels, each absorbs one hit), **1** extra life.
You get 3 credits per game: when your lives run out, press Enter during the
countdown to continue where you died (score resets). With no credits left it's
back to stage 1.
The high score is saved to `hiscore.txt` next to the script.
