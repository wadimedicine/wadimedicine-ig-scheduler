#!/usr/bin/env python3
"""Deciding whether two pieces of upload copy describe the SAME video.

WHY THIS EXISTS (30 Jul 2026, after V13 double-posted on Instagram)
-------------------------------------------------------------------
Every guard in this repo used to answer that question the same way:

    _norm(caption)[:60]  ->  does the live post's caption START with it?

That works only while a video's first 60 characters are unique to that video.
Two changes on 27 Jul broke both halves of the assumption at once:

  1. Captions were rewritten "ask-first" — the DOCTOR call-to-action moved to
     the FRONT. So every video now opens with the same ~92 characters:
     "Comment DOCTOR for a free 15-min call about studying medicine abroad.
      No pitch, no pressure."
     A 60-character prefix key is now IDENTICAL for every video we post.

  2. The GitHub fallback queue kept the OLD, body-first wording (the edit was
     never committed). So the fallback's copy of V13 and the copy Zernio had
     actually published described the same video with different opening words.

(2) made the guard say "not posted" about a video that WAS posted -> V13 went
out twice on 29 Jul. (1) means that simply re-syncing the wording would flip
the same guard to the opposite failure: it would match ANY recent post and
skip forever, silently retiring the fallback. Prefix matching cannot get both
right, so it is replaced here rather than patched.

THE APPROACH
------------
Compare the SET OF WORD SEQUENCES two texts share, not their opening
characters. Word order and position stop mattering, so moving the CTA from
the end to the front is invisible; and a shared CTA is only ~15 words out of
~70, far too little to make two different videos look alike.

Overlap is scored by CONTAINMENT — shared shingles over the size of the
SMALLER text — not the more usual Jaccard index, so a short text (a YouTube
title) can still match the long caption that contains it.

Measured on this account's real copy (see `python caption_match.py --selftest`,
which asserts these):
    same video, old body-first vs new ask-first wording   ~0.83
    two different videos that share only the DOCTOR CTA   ~0.13
THRESHOLD sits at 0.5, in the empty middle.
"""

SHINGLE_N = 8      # words per shingle
THRESHOLD = 0.5    # containment at or above this = same video

# Containment alone rates a FRAGMENT as a perfect match of any text that
# contains it: the 16-word DOCTOR call-to-action scores 1.00 against every
# caption on the account, because all of its shingles appear in all of them.
# That is the same "boilerplate identifies nothing" failure in a new form, so
# the two texts must also be of comparable length before a score is believed.
# 0.4 accepts ordinary editing drift between two versions of one caption and
# rejects a CTA-sized fragment standing in for a whole caption.
MIN_SIZE_RATIO = 0.4


# Characters that differ between the vault, PowerShell and what each platform
# hands back — the same text can come back with curly quotes or an en dash and
# must still compare equal.
_FOLD = (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
         ("—", "-"), ("–", "-"), (" ", " "))


def norm(s):
    """Collapse whitespace, fold typographic characters, lowercase. Instagram
    hands captions back with slightly different whitespace and punctuation than
    what was submitted, so this has to run before any comparison."""
    s = s or ""
    for a, b in _FOLD:
        s = s.replace(a, b)
    return " ".join(s.split()).lower()


def shingles(text, n=SHINGLE_N):
    """Every run of n consecutive words, as a set.

    n shrinks for short text so a headline or a YouTube title still produces
    something comparable instead of an empty set.
    """
    words = norm(text).split()
    if not words:
        return set()
    n = min(n, len(words))
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def containment(a, b):
    """0.0-1.0. Shared shingles as a fraction of the SMALLER text's shingles.

    Returns 0.0 when the two texts are too different in length to be two
    versions of the same copy — see MIN_SIZE_RATIO.
    """
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    small, large = min(len(sa), len(sb)), max(len(sa), len(sb))
    if small / large < MIN_SIZE_RATIO:
        return 0.0
    return len(sa & sb) / small


def matches(a, b, threshold=THRESHOLD):
    """True if these two texts are the same video's copy."""
    return containment(a, b) >= threshold


def best_match(text, candidates, threshold=THRESHOLD):
    """Pick the best-scoring key from {key: text, ...}, or None.

    `candidates` may map one key to several texts (a video has a caption per
    platform); pass a list and the strongest one counts. Used to answer "which
    video is this post?" — the old code took the FIRST candidate whose copy
    started with the same 40 characters, which after the ask-first rewrite was
    always the earliest-numbered video, i.e. always V11.
    """
    best, best_score = None, 0.0
    for key, texts in candidates.items():
        if isinstance(texts, str):
            texts = [texts]
        for t in texts:
            score = containment(text, t)
            if score > best_score:
                best, best_score = key, score
    return best if best_score >= threshold else None


def _selftest():
    """Real copy from this account, so the thresholds are checked against the
    strings that actually broke, not invented examples."""
    cta_new = ("Comment DOCTOR for a free 15-min call about studying medicine abroad. "
               "No pitch, no pressure. ")
    cta_old = (" Comment DOCTOR and I'll send you the free 15-minute call link. "
               "No pitch, no pressure.")
    v13 = ("What does a real week of second-year medicine in Bulgaria look like? Last "
           "semester my main finals were Anatomy, Biochemistry and Physiology, with other "
           "modules spread through the week. Tuesday to Thursday were long; the other days "
           "were shorter. Each module has one or two colloquium midterms per semester, and "
           "Bulgarian language class is part of every week.")
    v14 = ("How much does living in Pleven cost me as a medical student? My rent is EUR140 "
           "a month and my total monthly living costs are around EUR400, excluding tuition. "
           "Most of the rest goes on food; the city is walkable and everyday prices are "
           "lower than Ireland. Your total will depend on your accommodation and lifestyle.")

    v13_live = cta_new + v13          # what Zernio actually published
    v13_queue = v13 + cta_old         # what the stale fallback was holding
    v14_live = cta_new + v14

    # YouTube rows carry a title, and are only ever compared with the title the
    # vault expects for that video — never with a caption.
    yt_title = "My real timetable in 2nd year medicine"
    yt_other = "What living in Pleven actually costs"

    same = containment(v13_live, v13_queue)
    diff = containment(v13_live, v14_live)
    frag = containment(v13_live, cta_new)

    print(f"same video, reordered wording : {same:.2f}   (must be >= {THRESHOLD})")
    print(f"different videos, shared CTA  : {diff:.2f}   (must be <  {THRESHOLD})")
    print(f"whole caption vs the CTA alone: {frag:.2f}   (must be <  {THRESHOLD})")
    print(f"YouTube title vs same title   : {containment(yt_title, yt_title):.2f}")
    print(f"YouTube title vs other title  : {containment(yt_title, yt_other):.2f}")

    assert matches(v13_live, v13_queue), "FAIL: would have double-posted V13 again"
    assert not matches(v13_live, v14_live), "FAIL: would treat V14 as already posted"
    assert not matches(v13_live, cta_new), "FAIL: the CTA alone must not identify a video"
    assert not matches(v13_live, ""), "FAIL: empty text must never match"
    assert matches(yt_title, yt_title), "FAIL: a title must match itself"
    assert not matches(yt_title, yt_other), "FAIL: two titles must stay distinct"
    assert best_match(v13_live, {13: v13_queue, 14: v14_live}) == 13
    assert best_match(cta_new, {13: v13_queue, 14: v14_live}) is None, \
        "FAIL: boilerplate alone must not be attributed to a video"
    print("\nOK all self-tests passed")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        print(__doc__)
        print("run with --selftest to check the thresholds against real copy")
