# Performance notes (raw, for report section 4d)

Scratch log of Model Lab runs on the deployed Space. Not part of the
deliverable — copy the averaged numbers into `REPORT.md` section d when done.

Format per run: `image | run type | Local vision | Remote text | Local text | notes`

## Image 1

(same image each run, only the Voice dropdown changes between runs)

- cold start | Local vision: 9.00s | Remote text: 0.28s | Local text: 10.86s
- run 2 (warm) | Local vision: 6.51s | Remote text: 0.50s | Local text: 7.59s
- run 3 (warm) | Local vision: 8.10s | Remote text: 0.35s | Local text: 6.49s
- run 4 (warm) | Local vision: 5.68s | Remote text: 0.54s | Local text: 6.63s

## Image 2

(same image each run, only the Voice dropdown changes between runs)

- cold start | Local vision: 9.87s | Remote text: 0.39s | Local text: 14.67s
- run 2 (warm) | Local vision: 8.61s | Remote text: 0.33s | Local text: 16.10s
- run 3 (warm) | Local vision: 5.84s | Remote text: 0.60s | Local text: 6.91s
- run 4 (warm) | Local vision: 5.74s | Remote text: 2.27s | Local text: 7.02s

## Image 3

(same image each run, only the Voice dropdown changes between runs)

- cold start | Local vision: 11.39s | Remote text: 0.27s | Local text: 10.28s
- run 2 (warm) | Local vision: 6.54s | Remote text: 0.40s | Local text: 6.44s
- run 3 (warm) | Local vision: 6.67s | Remote text: 0.41s | Local text: 7.07s
- run 4 (warm) | Local vision: 19.51s | Remote text: 0.34s | Local text: 16.96s | outlier — much slower than runs 2-3, maybe ZeroGPU re-allocated a fresh slice

## Summary (averages, copied into REPORT.md 4d)

Cold start (n=3, one per image):
- Vision: 10.09s
- Remote text: 0.31s
- Local text: 11.94s

Warm (n=9, all runs 2-4):
- Vision: 8.13s (6.71s excluding the image-3 outlier, n=8)
- Remote text: 0.64s
- Local text: 9.02s (8.03s excluding the image-3 outlier, n=8)

Report uses the outlier-excluded warm numbers. Qualitative: remote (gpt-oss-20b)
captions were consistently better/funnier than local (Qwen3-0.6B) — not tallied
into a usable/requested ratio yet.
