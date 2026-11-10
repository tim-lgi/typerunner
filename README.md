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
| `C` | switch between standard and the teaching course |
| `M` | switch between racing and practice |
| `[` `]` | pick a teaching stage |
| `S` | that player's stats and progress |
| `N` | new player |
| `D` | delete a player (press twice) |
| `Esc` | leave a race |
| `Q` | quit |

## Teaching course

Standard mode throws the whole language at you. The teaching course builds you
up to it, one finger movement at a time, and says plainly what each stage is
teaching.

| Stage | Adds | What you are learning |
|---|---|---|
| 1 | `a s d f j k l ;` | home position — no finger leaves its own key |
| 2 | `g h` | index finger reaches inward |
| 3 | `e i` | middle finger reaches up |
| 4 | `r t u y` | index finger reaches up |
| 5 | `w o` | ring finger reaches up |
| 6 | `v b n m` | index finger reaches down |
| 7 | `c x , .` | middle and ring fingers reach down |
| 8 | `q p z /` | pinky — the longest reaches of all |

Stage 8's keys are the whole alphabet, so finishing the course puts you exactly
where standard mode begins. You can start at any stage — press `[` and `]` to
pick one.

The home row can only spell eleven real English words, so the early stages are
mostly finger drills. A real word still lands every second or third go, because
unbroken drill is mind-numbing and the word is what makes it worth doing.

### Practice, or race

Press `M` to choose.

**Race** is the standard game: pacers in the lower lanes, a clock, words per
minute.

**Practice** removes all of it. No rivals, no clock. Instead a keyboard appears
and the next key you need is shown inverted, so you never hunt. Keys your stage
has not unlocked stay dim, so you can see your territory growing. Each key is
coloured by which finger presses it, the same colour on both hands — the point
is to learn that `A` and `;` are both pinky keys.

What you are scored on is accuracy and your longest clean streak, so there is
something to beat without a clock on you.

Teaching results are recorded separately and never mix into your standard
averages or your pacer's speed.

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
