"""Lyric statistics and a fully offline rhyme helper (CMUdict-derived word list)."""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

from .paths import resource_path

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")


@lru_cache(maxsize=1)
def _words() -> dict[str, list]:
    p = Path(resource_path("data/words.json.gz"))
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


@lru_cache(maxsize=1)
def _indexes():
    words = _words()
    perfect: dict[str, list[str]] = {}
    vowel_tail: dict[str, list[str]] = {}
    for w, (_syl, pk, vk) in words.items():
        perfect.setdefault(pk, []).append(w)
        vowel_tail.setdefault(_assonance_key(pk), []).append(w)
    return perfect, vowel_tail


def _assonance_key(perfect_key: str) -> str:
    """Vowel skeleton of the rhyme part, e.g. 'AE P' -> 'AE', 'AE K S' -> 'AE'.
    Multi-syllable rhyme parts keep every vowel: 'AE T ER' -> 'AE ER'."""
    vowels = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
    return " ".join(p for p in perfect_key.split() if p in vowels)


def normalize(word: str) -> str:
    w = word.lower().strip("'")
    # common rap spellings: runnin' -> running, tryna -> stays
    if w.endswith("in") and w + "g" in _words() and w not in _words():
        w = w + "g"
    return w


def heuristic_syllables(word: str) -> int:
    w = word.lower().strip("'")
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    n = len(VOWEL_GROUP_RE.findall(w))
    return max(1, n)


def word_syllables(word: str) -> int:
    raw = word.lower()
    entry = _words().get(raw.strip("'")) or _words().get(normalize(raw))
    if entry:
        return int(entry[0])
    return heuristic_syllables(word)


def words_in(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def line_syllables(line: str) -> int:
    return sum(word_syllables(w) for w in words_in(line))


def count_words(text: str) -> int:
    return len(words_in(text))


def lyric_lines(text: str) -> list[str]:
    """Non-empty lines, ignoring [bracketed] stage notes and (ad-libs only) lines."""
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or (s.startswith("[") and s.endswith("]")):
            continue
        out.append(s)
    return out


def count_bars(text: str) -> int:
    """In rap writing one written line is (roughly) one bar."""
    return len(lyric_lines(text))


def stats(text: str) -> dict:
    lines = lyric_lines(text)
    syl = [line_syllables(l) for l in lines]
    return {
        "words": count_words(text),
        "bars": len(lines),
        "syllables": sum(syl),
        "avg_syllables": round(sum(syl) / len(syl), 1) if syl else 0.0,
    }


def last_word(line: str) -> str:
    ws = words_in(line)
    return ws[-1] if ws else ""


def _spelling_tail(word: str) -> str:
    w = word.lower()
    groups = list(VOWEL_GROUP_RE.finditer(w))
    if not groups:
        return w[-2:]
    return w[groups[-1].start():]


def rhymes(word: str, limit: int = 60) -> dict[str, list[str]]:
    """Return {'perfect': [...], 'near': [...]} ordered by word frequency."""
    w = normalize(word)
    if not w:
        return {"perfect": [], "near": []}
    words = _words()
    perfect_idx, vowel_idx = _indexes()
    entry = words.get(w)
    if entry:
        pk = entry[1]
        perfect = [x for x in perfect_idx.get(pk, []) if x != w and not _same_stem(x, w)]
        ak = _assonance_key(pk)
        pset = set(perfect)
        near = [x for x in vowel_idx.get(ak, []) if x != w and x not in pset and not _same_stem(x, w)]
        # also allow assonance on the final vowel only for multi-syllable keys (slant rhymes)
        if len(near) < limit and " " in ak:
            last_v = ak.split()[-1]
            for x in vowel_idx.get(last_v, []):
                if len(near) >= limit:
                    break
                if x != w and x not in pset and x not in near:
                    near.append(x)
    else:
        tail = _spelling_tail(w)
        perfect = [x for x in words if x != w and x.endswith(tail)]
        near = [x for x in words if x != w and x not in perfect and x.endswith(tail[-2:])]
    qsyl = word_syllables(w)

    def rank(x):
        e = words.get(x)
        return min(abs((e[0] if e else qsyl) - qsyl), 2)

    perfect.sort(key=rank)  # stable: keeps frequency order inside each group
    return {"perfect": perfect[:limit], "near": near[:limit]}


def _same_stem(a: str, b: str) -> bool:
    return a.startswith(b) and len(a) - len(b) <= 2 and a[len(b):] in ("s", "es", "'s", "ed", "d")
