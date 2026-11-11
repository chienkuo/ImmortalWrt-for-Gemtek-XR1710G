# Pinned MT7996 RF firmware (board-matched)

mt76 2026.10.28 replaced these blobs with
`t-neptune-main-7990-7992-7993-...MT7990_MT7988D_BE13500_MP5_2ADIE`, a
unified **2-die** build. On the Gemtek XR1710G (MT7990 single-die) it
degrades RF on all three bands (tx-failed storms, rate control collapse
to 6M/1M legacy, 6G unusable) while management frames still work.

These pinned copies are the known-good 2026.10.08 blobs
(`t-neptune-mp-7990-...MT7990_MP_ASIC1_0_ROM_RAM_REBB_6_0`) extracted
from the 20261106-68a71341 release, verified working on the device.

Drop this override when an mt76 release ships firmware whose WM strings
target MT7990 single-die again (check `strings mt7996_wm.bin`).
