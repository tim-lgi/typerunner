# Publishing checklist

Two repos, both public, under github.com/tim-lgi:

| Repo | Contents | Why |
|---|---|---|
| `typerunner` | this folder | the source people install |
| `homebrew-tap` | `~/homebrew-tap` | the formula `brew tap` reads |

The tap repo **must** be named `homebrew-tap` — Homebrew maps
`brew tap tim-lgi/tap` to `github.com/tim-lgi/homebrew-tap` by that convention.

---

## 1. Push the game

```sh
cd ~/typerunner
git init
git add -A
git commit -m "Typerunner 1.0.0"
git branch -M main
git remote add origin git@github.com:tim-lgi/typerunner.git
git push -u origin main
git tag v1.0.0
git push origin v1.0.0
```

## 2. Get the tag's checksum

GitHub builds a tarball for the tag. Hash the one GitHub serves, not a local
build — they are not byte-identical.

```sh
curl -sL https://github.com/tim-lgi/typerunner/archive/refs/tags/v1.0.0.tar.gz \
  | shasum -a 256
```

## 3. Put that checksum in the formula

Replace `PASTE_THE_SHA256_HERE` in `~/homebrew-tap/Formula/typerunner.rb`.

## 4. Push the tap

```sh
cd ~/homebrew-tap
git init
git add -A
git commit -m "typerunner 1.0.0"
git branch -M main
git remote add origin git@github.com:tim-lgi/homebrew-tap.git
git push -u origin main
```

## 5. Anyone can now install it

```sh
brew tap tim-lgi/tap
brew install typerunner
typerunner
```

Test it yourself first with `brew install --build-from-source typerunner`
and `brew test typerunner`.

---

## Shipping a later version

```sh
# bump the version in BOTH pyproject.toml and src/typerunner/__init__.py
git commit -am "Typerunner 1.1.0" && git push
git tag v1.1.0 && git push origin v1.1.0
curl -sL https://github.com/tim-lgi/typerunner/archive/refs/tags/v1.1.0.tar.gz | shasum -a 256
# then update url + sha256 in the formula, commit, push
```

Users get it with `brew update && brew upgrade typerunner`.

---

## The coffee link

`COFFEE_URL` near the top of `src/typerunner/game.py` is empty, so the option is
hidden. Paste a Square payment link in and a gold `C   buy Tim a coffee` line
appears on the player screen; pressing `C` opens it in the browser.

```python
COFFEE_URL = "https://square.link/u/XXXXXXXX"
```

Make the link in Square Dashboard → Online Checkout → Payment links, as a
payment with a customer-set amount. Nothing else is needed — no API key, no
secret, nothing to leak in a public repo.

---

## Also on PyPI (optional)

Lets people `pipx install typerunner` without Homebrew. The tap does not depend
on this.

```sh
python3 -m build
python3 -m twine upload dist/*
```

---

## Moving to homebrew-core later

The formula format is identical, so it is the same file plus a pull request to
`Homebrew/homebrew-core`. They apply a notability bar — the project has to be
established and maintained, judged on stars, forks and watchers — so this is
worth revisiting once people are actually playing it, not now. Nothing you do
in the tap is wasted when that day comes; users move over automatically.
