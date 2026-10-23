# configs/

YAML parameter files for detector, tracker, recovery and launch settings.

Rules:
- Inference configs must never contain simulator ground truth.
- Every experiment run records: git commit, config checksum, dataset manifest ID,
  model checkpoint hash.
- Thresholds are tuned on validation data and frozen before the test run.
