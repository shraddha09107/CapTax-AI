# CapTax AI — Hero 3D Performance & Verification Report

## 1. Frame Times (1440x900 @ 2x DPR)
- **Standard Desktop Execution:**
  - Average Frame Time: **16.58 ms** (~**60.3 FPS**)
  - 95th Percentile (p95): **17.60 ms**
- **4× CPU-Throttled Execution (Low-End Emulation):**
  - Average Frame Time: **16.52 ms** (~**60.5 FPS**)
  - 95th Percentile (p95): **17.80 ms**
  - Governor Response: Smoothly maintains stability with zero visual stalls.

## 2. Collision Test Results
- Simulation Duration: 120 seconds (3,600 frames @ 30Hz, 7,200 frames @ 60Hz)
- Minimum Surface Gap Between Coins: **0.1315 units** (**0.24 × R**, well above the 0.05 × R threshold)
- Minimum Card Slab Clearance: **0.0600 units**
- Minimum Floor Clearance: **0.8127 units**
- Total Collisions Detected: **0 (Zero)**

## 3. Visual Assets Captured in `docs/hero-screenshots/`
- `hero-dark-1440-t[0,3,6,9].png`
- `hero-light-1440-t[0,3,6,9].png`
- `hero-mobile-dark-390-t[0,3,6,9].png`
- `hero-mobile-light-390-t[0,3,6,9].png`
- `hero-debug-collisions.png`
