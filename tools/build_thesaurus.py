"""Builds sitewright/library/thesaurus.json.gz from the WordNet 3 database files.
Run once:  python3 tools/build_thesaurus.py /path/to/wordnet/dict
WordNet 3.0 (c) Princeton University - licence in sitewright/library/LICENSE-wordnet.txt"""
import gzip
import json
import os
import sys

POS = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"}
MAX_SENSES, MAX_SYNS = 5, 12


def synsets(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("  "):
                continue
            head, _, gloss = line.partition("|")
            parts = head.split()
            offset, n = parts[0], int(parts[3], 16)
            words = [parts[4 + 2 * i].replace("_", " ") for i in range(n)]
            rest = parts[4 + 2 * n:]
            similar = []
            try:
                for k in range(int(rest[0])):
                    sym, off = rest[1 + 4 * k], rest[2 + 4 * k]
                    if sym == "&":                       # adjectives: "similar to"
                        similar.append(off)
            except (IndexError, ValueError):
                pass
            out[offset] = (words, gloss.strip().split(";")[0][:70], similar)
    return out


def main(src, dest):
    thes = {}
    for letter, name in (("n", "noun"), ("v", "verb"), ("a", "adj"), ("r", "adv")):
        sets = synsets(os.path.join(src, "data." + name))
        with open(os.path.join(src, "index." + name), encoding="utf-8") as f:
            for line in f:
                if line.startswith("  "):
                    continue
                p = line.split()
                lemma, cnt = p[0].replace("_", " "), int(p[2])
                offsets = p[-cnt:]
                senses = []
                for off in offsets[:MAX_SENSES]:
                    words, gloss, similar = sets.get(off, ([], "", []))
                    near = [w for o2 in similar for w in sets.get(o2, ([],))[0]]
                    syn = []
                    for w in words + near:
                        if w.lower() != lemma.lower() and w not in syn:
                            syn.append(w)
                    syn = syn[:MAX_SYNS]
                    if syn:
                        senses.append([gloss, syn])
                if senses:
                    thes.setdefault(lemma, {})[letter] = senses
    raw = json.dumps(thes, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    with gzip.open(dest, "wb", 9) as f:
        f.write(raw)
    print(len(thes), "words,", round(len(raw) / 1e6, 1), "MB raw,", round(os.path.getsize(dest) / 1e6, 1), "MB gzipped")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else
         os.path.join(os.path.dirname(__file__), "..", "sitewright", "library", "thesaurus.json.gz"))
