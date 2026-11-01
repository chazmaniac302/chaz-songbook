"""Builds chaz_songbook/data/words.json.gz from CMUdict + wordfreq (offline, at dev time).

Each entry: word -> [syllables, perfect_rhyme_key, vowel_key]
"""
import gzip, json, re, sys
from pathlib import Path
import cmudict
from wordfreq import top_n_list

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
d = cmudict.dict()
common = top_n_list("en", N)
EXTRA = """drip whip flip trap stack racks bands opps goat vibe vibes slime lit fam bae
drill plug bando splash ice icy chain chains benz coupe cash bag bands hustle grind shine
flex finesse savage glock choppa dough guap henny lean molly rollie wrist pistol hood block
gang squad bounce trunk thunder lightning love heart pain rain night light flame shame""".split()
words = list(dict.fromkeys([w for w in common if re.fullmatch(r"[a-z']+", w)] + EXTRA))

def keys(phones):
    vowels = [i for i, p in enumerate(phones) if p[-1].isdigit()]
    if not vowels:
        return 0, "", ""
    stressed = [i for i in vowels if phones[i][-1] in "12"]
    start = stressed[-1] if stressed else vowels[-1]
    perfect = " ".join(re.sub(r"\d", "", p) for p in phones[start:])
    vowel = re.sub(r"\d", "", phones[vowels[-1]])
    return len(vowels), perfect, vowel

out = {}
for w in words:
    if w in d:
        syl, perfect, vowel = keys(d[w][0])
        if syl:
            out[w] = [syl, perfect, vowel]
dest = Path(__file__).resolve().parents[1] / "chaz_songbook" / "data" / "words.json.gz"
with gzip.open(dest, "wt", encoding="utf-8") as f:
    json.dump(out, f, separators=(",", ":"))
print(len(out), "words ->", dest, dest.stat().st_size, "bytes")
