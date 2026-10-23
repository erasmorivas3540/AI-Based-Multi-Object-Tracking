# How to fill the related-work matrix

Open `related_work_matrix.csv` in a spreadsheet. One row per paper. Add papers you
find through the reference lists of these seven, especially anything on
*re-identification after occlusion in aerial or moving-camera video*.

## Reading order

1. **ByteTrack first.** Your matched control C0 is essentially a cleaner version
   of its lost-track logic, so you need to know exactly what it already does.
   Read the code, not just the paper (`byte_tracker.py` — find where a
   track moves to the lost state and how it can be re-matched).
2. **BoT-SORT, TrackTrack.** Your main baselines.
3. **DroneMOT, DMTrack, DynUAV, JitTrack.** The closest overlap risks.

## The questions that matter for your claim

Your claim is narrow: *the decision to reattach a lost track to a new detection*.
For each paper, find that decision in the method section (and the code if it
exists) and answer:

- What information goes into it? Position only? IoU? Appearance? Confidence
  history? Camera-motion quality? Image quality?
- Is it a fixed rule, a tuned threshold, or a learned model?
- Is its output treated as a probability? Is that probability calibrated?
- Is there an explicit option to reject all candidates?
- Do the authors report recovery separately, or only aggregate metrics (HOTA,
  IDF1)?
- What do their ablations say actually mattered?

The `overlap_with_my_claim` column is the one your novelty note depends on.
Write a short phrase: *none*, *partial — uses X but not Y*, or *same mechanism*.

## Checks before citing

- Confirm each preprint's current status (published? revised? withdrawn?).
- Confirm the code link works and note the commit you looked at.
- Keep what the paper *reports* separate from what you *reproduce*.

## Time box

Aim for about 6–8 hours this week. Depth on the recovery mechanism beats breadth.
