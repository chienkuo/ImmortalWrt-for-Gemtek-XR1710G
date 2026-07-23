# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) fork customized for the **Gemtek XR1710G** (Brightspeed XR1710G) router — an Airoha AN7581GT SoC (ARM64 Cortex-A53, 4-core 1.3GHz, 8-core NPU) with 2GB RAM, 512MB SPI NAND flash, MT7996AV Wi-Fi 7, and 2×10G + 2×1G Ethernet ports.

## Git Remotes

| Remote | URL | Purpose |
|--------|-----|---------|
| `immortalwrt` | `immortalwrt/immortalwrt` | ImmortalWrt upstream (periodically merged) |
| `origin` | `chienkuo/ImmortalWrt-for-Gemtek-XR1710G` | Personal development repository |
| `upstream` | `naoki66/ImmortalWrt-for-Gemtek-XR1710G` | Original project fork |

Branch: `master` (the only active branch). Workflow: merge `immortalwrt/master` periodically (`git merge immortalwrt/master`), rebase custom patches, commit fixes on top.

## Build

```bash
# Prerequisites: GNU/Linux (Debian 11+), 4GB+ RAM, 25GB+ disk
./scripts/feeds update -a
./scripts/feeds install -a
cp config.seed .config
make defconfig
make -j$(nproc)    # parallel build; on failure, retry with V=sc for readable errors

# Output: bin/targets/airoha/an7581/immortalwrt-airoha-an7581-gemtek_xr1710g-ubi-squashfs-sysupgrade.itb
```

`config.seed` (328KB) is the full kernel/package config. The CI (`build-firmware.yml`) copies it to `.config` and runs `make defconfig` before building.

For exposing actual compile errors, use `make -j1 V=sc` — the CI already does this as a fallback when parallel build fails.

## Architecture

### OpenWrt Buildroot Structure

This is a standard OpenWrt buildroot with a single target addition:

- **`target/linux/airoha/`** — The entire Airoha target. ImmortalWrt upstream has this, but this repo adds the XR1710G device support plus custom kernel patches.
  - `dts/an7581-xr1710g-ubi.dts` — Device tree (387 lines, standalone — does NOT include any common dtsi beyond `an7581.dtsi` and `an7581-npu-mt7996.dtsi`). Defines flash partitions (UBI layout), GPIO LEDs/keys, PCIe x2 for MT7996, MDIO PHYs (C45 RTL8261BE at addresses 5 and 8), internal MT7530 switch ports, UART, I2C (NCT7802 fan controller).
  - `patches-6.18/` — Kernel 6.18 patches. ~100 patches total; the custom ones are:
    - `303-01/02` — MediaTek PHY calibration fixes
    - `634` — PPE hardware init at tc block bind for bridge mode
    - `675-01~04` — nft_flow_offload bridge/VLAN/WDMA support
    - `910-02` — USB/PCIe clock fix
    - `910-04` — NPU MBQ timeout fix (eagle ser)
    - `911-913` — PCIe x2 mode support (PERST separation, x2 link, PERST deassert)
    - `920` — cpufreq pm domain attach fix (-EPERM)
    - `990-01` — Bridge FDB roaming invalidation for nf_flow_table
    - `0401/0403` — pmdomain fallback to PLL registers when BL31 GET_FREQ fails
    - The remaining numbered patches are upstream kernel backports.
  - `image/an7581.mk` — Image build recipe. Defines `Device/gemtek_xr1710g-ubi` with UBI layout (128K blocksize, 2048 pagesize, UBOOTENV_IN_UBI, KERNEL_IN_UBI), output format (FIT + gzip → sysupgrade.itb), and required packages.
  - `an7581/base-files/` — Board init scripts: `01_leds` (LED config), `02_network` (lan2/lan3/lan4 → wan interface mapping), `airoha_fan` (NCT7802 fan curve matching vendor firmware), `platform.sh` (upgrade via `fit_do_upgrade`).
  - `an7581/config-6.18` — Kernel config for this subtarget.
  - `an7581/target.mk` — ARCH=aarch64, CPU_TYPE=cortex-a53, KERNELNAME=Image dtbs.

- **`package/`** — Custom LuCI apps and packages:
  - `luci-app-airoha-npu` — SoC status monitoring + overclocking
  - `luci-app-airoha-fancontrol` — Fan speed/temperature control (NCT7802)
  - `luci-app-airoha-flowsense` — PPE hardware offload monitoring
  - `luci-app-lucky` — Lucky (DDNS/reverse proxy/port forwarding)

- **`config.seed`** — Full `.config` with `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_xr1710g-ubi=y` and all package selections. Do not hand-edit; regenerate with `make defconfig` then `./scripts/diffconfig.sh > config.seed`.

### Key Design Decisions

1. **Standalone DTS**: The XR1710G DTS does not share a common dtsi with other Gemtek devices (W1700K has its own). Changes to one should not affect the other.

2. **UBI flash layout**: vendor (6MB) → chainloader (1MB) → ubi (439MB, containing ubootenv/ubootenv2/fit/factory volumes) → reserved_bmt (66MB). The BMT (Bad Block Table) reservation at the end of flash is critical — the vendor bootloader depends on it.

3. **Kernel patches are versioned by source**: Patches numbered `xxx-` come from upstream kernel; unnumbered patches (like `303-`, `634-`, `675-`, `910-`, `920-`, `990-`) are custom. When adding/modifying patches, regenerate with `git format-patch` and ensure hunk header line counts match the actual kernel source.

4. **MAC address assignment**: `lan_mac` at factory offset 0x6000 is a `mac-base` with `#nvmem-cell-cells = <1>`. Increment values: +0 = cpu/lan2, +1 = 2.4GHz WiFi, +2 = 5GHz WiFi, +3 = 6GHz WiFi. `wan_mac` at offset 0x5000 is separate.

5. **Two remote PHYs via USXGMII**: The 10G ports use RTL8261BE PHYs on C45 MDIO bus (addresses 5 and 8) with inverted TX/RX polarity. These are not part of the internal MT7530 switch.

## Patch Management

When modifying kernel patches:

- Patches live in `target/linux/airoha/patches-6.18/` and apply to the kernel source during build
- Each patch's hunk headers (`@@ -line,count +line,count @@`) must match the actual line numbers in the target kernel source
- After editing a patch, test with a full build; malformed patches cause silent failures or build errors
- Use `git format-patch` style numbering: `NNN-category-description.patch`
- Custom patches that may conflict with upstream backports should be applied last (higher numbers)

## CI

- **build-firmware.yml**: Manual trigger (`workflow_dispatch`) with release type selector (none/release/prerelease). Builds on `ubuntu-latest`, creates artifacts, optionally creates GitHub Release with tag `YYYYMMDD-<sha>`.
- **sync-upstream.yml**: Auto-runs every 3 days + manual trigger. Fetches `immortalwrt/master`, merges (no-ff), pushes to origin. If merge conflicts, fails with error listing conflicted files.
