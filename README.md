# Typerunner

A terminal typing race game. You are a runner on a track; every letter you type
correctly is a stride. Clear words cleanly and you leap the hurdles. Fumble one
and you go down in a heap, and you have to back up and fix it before you can run
on. Two rivals race you down the lower lanes.

```
 Timoteo      WPM  66   Acc  99%   Time   38.9s   Lv 2   Score  4140
╔══════════════════════════════════════════════════════════════════╗
║ against where know new availability projects more care general   ║
║ mount united grant range authors usually below transfer logo     ║
╚══════════════════════════════════════════════════════════════════╝

                                      .@@.
                                     =@@@@=
                                      =@@=
            ||      ||      ||        @  /%    ||      ||        ┋
            ||      ||      ||       @%        ||      ||        ┋
 YOU  ============================================================
```

## Install

```sh
brew tap tim-lgi/tap
brew trust tim-lgi/tap
brew install typerunner
```

Homebrew asks you to trust any tap outside its own — `brew trust` is how you
say this one is fine.

Or, with any Python 3.9+:

```sh
pipx install typerunner
```

Then run it:

```sh
typerunner
```

## Playing

Type the highlighted word. Every correct letter moves your runner forward.

- **Hurdle words** are shown in gold. Type one cleanly and you jump it, for
  triple points.
- **A mistake stops you dead.** Backspace to the error and correct it — you
  cannot skip ahead with the space bar.
- **The last letter of the last word** ends the race. No trailing space needed.

The race ends when *you* cross the line, not when the computer does. If a rival
beats you there it waits at the finish while you run it out.

### Keys

| | |
|---|---|
| `↑` `↓` | choose a player |
| `Enter` | race |
| `S` | that player's stats and progress |
| `N` | new player |
| `D` | delete a player (press twice) |
| `Esc` | leave a race |
| `Q` | quit |

## Players and progress

Everyone racing on a machine gets their own profile, so a family can pass the
keyboard around. Every race is recorded — words per minute, accuracy, time,
score, finishing place — in `~/.hurdle_rush.db`.

The progress screen charts your recent races: green bars for speed, a gold line
for accuracy, on one scale reaching 100 so the two read together. Bars are
shaded by level.

**The pacer learns you.** Once you have raced a level, the PACE runner is set to
your own average for *that level*, minus a handicap that narrows as you climb —
10% at level one, 7.5% at two, 5% at three. It is always just catchable, and it
gets harder as you get faster.

## Levels

Words are drawn from about 9,300 English words ranked by how often they occur in
real writing, so a word's rank *is* its difficulty. Higher levels reach deeper
into the list, where words are rarer and longer. No word repeats within a race.

| Level | Drawn from | Average word |
|---|---|---|
| 1 | the 1,000 commonest words | 5.7 letters |
| 3 | ranks 150–3,500 | 6.7 letters |
| 6 | ranks 1,800–9,999 | 7.5 letters |

## Requirements

Python 3.9 or newer and a terminal at least 64×28. Nothing else — no third-party
packages. Works on macOS and Linux.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).

The bundled word list is derived from the
[Monkeytype](https://github.com/monkeytypegame/monkeytype) English word lists,
which are GPL-3.0.
