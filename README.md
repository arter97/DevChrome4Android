# Chromium for Android with docked DevTools

Builds `chrome_public_apk` (package `com.arter97.devchrome`, arm64) from the
official Chromium source tarball, with patches that add a docked DevTools
(right / bottom / left, including the device mode toolbar) to the app menu.
This works best on a tablet. Functionality on phones is not tested and not
recommended.

![DevTools docked left with the device toolbar emulating an iPad Pro; the
dock side menu offers left / bottom / right only, and "Developer tools" is in
the app menu](docs/screenshot.jpg)

## Download

Prebuilt APKs are available on the
[releases page](https://github.com/arter97/DevChrome4Android/releases).

## Layout

| Path | Tracked | Purpose |
| --- | --- | --- |
| `args/common.gn`, `args/<variant>.gn` | yes | GN args; `scripts/build.sh` writes their concatenation to `src/out/<Variant>/args.gn` |
| `patches/series`, `patches/**.patch` | yes | quilt patch series (DEP-3 headers) |
| `quiltrc` | yes | quilt settings (`-p ab`, no timestamps) |
| `scripts/` | yes | fetch / deps / build helpers |
| `.gclient` | yes | lets depot_tools find `src/`; never used for `gclient sync` |
| `src/` | no | extracted tarball + Android deps, patched by quilt (`src/patches -> ../patches`) |
| `dl/` | no | downloaded tarballs |
| `depot_tools/` | no | shallow depot_tools checkout (`DEPOT_TOOLS_UPDATE=0`) |

## Fresh checkout / version bump

```sh
mv src src.old                         # if updating
scripts/fetch-source.sh 148.0.7778.96  # tarball -> src/, Android deps, quilt push -a
scripts/build.sh                       # gn gen + autoninja chrome_public_apk
scripts/build-watch.sh                 # same, detached; returns at the first failure or exit
```

## Build variants

`VARIANT=<name> scripts/build.sh` (or `build-watch.sh`); `GEN_ONLY=1` stops
after `gn gen`.

| Variant | Output | What |
| --- | --- | --- |
| `official` (default) | `src/out/Official` | `is_official_build`: ThinLTO, PGO, orderfile, resource allowlist. Slow links. |
| `release` | `src/out/Release` | Plain release build; fast incremental rebuilds for working on patches. |

## Editing patches

```sh
scripts/quilt top                     # current patch
scripts/quilt pop / push              # move in the stack
scripts/quilt add path/to/file        # BEFORE editing a file
scripts/quilt new android-devtools/0005-foo.patch
scripts/quilt refresh                 # write changes into the top patch
scripts/quilt header -e               # edit the DEP-3 description
```

## Patches

| Patch | What |
| --- | --- |
| 0001 | Enable upstream `AndroidDevToolsFrontend` (menu item gating, Ctrl+Shift+I, "Inspect") |
| 0002 | Dockable `DevToolsWindow` on Android; `DevToolsDock` JNI bridge; `noUndock` URL flag |
| 0003 | DevTools frontend: drop "Undock into separate window" when `noUndock` is set |
| 0004 | Draw DevTools behind the tab (`StaticTabSceneLayer`), resize/offset the tab to the inspected-page bounds reported by the frontend, route input (`DockedDevToolsHost`) |
| 0005 | Show "Developer tools" as a top-level app menu item |
| 0006 | Backport of upstream `EventForwarder.setContainerViewOriginInCompositorSurface()` (touch input transferred to Viz) |
| 0007 | Pass the docked DevTools view origin to that API (fixes DevTools touch offsets on Android 16+) |
| branding/0001 | Rename the app (launcher label, widget titles) to DevChrome |

Dock sides and the device toolbar are laid out by the DevTools frontend itself
(like on desktop); the browser only places the inspected page at the bounds the
frontend reports through `SetInspectedPageBounds()`.

## Installing

```sh
adb install -r src/out/Official/apks/ChromePublic.apk   # or out/Release
```

## Signing

APKs are signed with Chromium's debug key
(`src/build/android/chromium-debug.keystore`).

To use your own key, set `android_keystore_path`, `android_keystore_name`
and `android_keystore_password` in `args/common.gn` (keep the keystore itself
out of git). Android refuses updates signed with a different key, so
switching keys requires uninstalling the app (and losing its data) once.
