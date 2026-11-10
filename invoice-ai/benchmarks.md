# OCR Benchmarks

| Date | Stage | Samples | Vendor found | Total found | Avg conf |
|---|---|---|---|---|---|
| 2026-08-08 | milestone-3 raw | n=19 | vendor 89% | total 100% | conf 94% |
| 2026-08-08 | milestone-4 preprocessed | n=19 | vendor 89% | total 89% | conf 94% |


> M4 decision: preprocessing OFF by default — ablation showed every step neutral-to-harmful (PP-OCRv4 handles normalization internally). Pipeline kept as opt-in for degraded client scans.| 2026-08-08 | milestone-5 rules | n=19 | vendor 68% | date 63% | total 37% |
| 2026-08-08 | milestone-5 rules | n=19 | vendor 68% | date 63% | total 58% |
| 2026-08-08 | milestone-5 rules | n=19 | vendor 68% | date 95% | total 68% |
| 2026-08-11 | milestone-5 hybrid | n=19 | vendor 68% | date 95% | total 100% |
