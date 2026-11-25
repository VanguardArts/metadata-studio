# Metadata Studio

A unified GUI (and CLI) for inspecting and removing identifying metadata from
images, audio, and documents — combining the capabilities of
**[Metascrub](https://github.com/VanguardArts/metascrub)** (audio ID3/RIFF
hygiene) and **[Provenance Scrubber](https://github.com/VanguardArts/provenance-scrubber)**
(image C2PA/EXIF/XMP/IPTC + pixel transform ladder) with a **document metadata**
engine.

- **Inspect** EXIF, ID3, PDF and document metadata.
- **Batch-remove** identifying information (generator comments, origin URLs,
  C2PA manifests, encoder fingerprints, author/creator fields, company, …).
- **Detect hidden metadata** and embedded thumbnails / preview images.
- **Compare** files before and after sanitization.
- **Batch processing** and **folder monitoring**.

## What it detects / removes

| Domain | Formats | Detects | Removes |
|---|---|---|---|
| Images | PNG, JPEG, WebP, TIFF, BMP | C2PA (`caBX`/APP11), EXIF, XMP, IPTC, text chunks, tIME, SynthID/byte signatures | chunk/marker surgery (lossless) + pixel transform ladder (levels 0–3) |
| Audio | MP3 (ID3v2.4), WAV (RIFF) | comments, lyrics, origin URLs, C2PA (`GEOB`/`C2PA` chunk), encoder fingerprints, private/watermark frames, cover art | byte-safe frame/chunk removal + uniform credits |
| Documents | PDF, DOCX/XLSX/PPTX, ODT/ODS/ODP, EPUB, HTML, RTF, SVG | `/Info` keys, XMP streams, thumbnails, OOXML `core.xml`/`app.xml`, ODF `meta.xml`, OPF Dublin Core, HTML meta tags, RTF `\info`, SVG `dc:*` | in-place member/xml/text editing, content preserved |

## Install

### From source (pip)

```bash
pip install .          # CLI + core
pip install .[gui]     # + the PySide6 desktop GUI
```

Requires Python ≥ 3.9. Dependencies: Pillow, mutagen, pypdf, PySide6 (GUI).

### Linux distro packages

Native (noarch) packages for every major distro family:

| Distro family | Format | Install |
|---|---|---|
| Debian / Ubuntu / Mint | `.deb` | `sudo dpkg -i metadata-studio_0.1.0_all.deb` |
| Fedora / RHEL / Rocky / Alma | `.rpm` | `sudo dnf install metadata-studio-0.1.0-1.noarch.rpm` |
| openSUSE Leap / Tumbleweed | `.rpm` | `sudo zypper install metadata-studio-0.1.0-1.noarch.rpm` |
| Arch / Manjaro | `PKGBUILD` | `pacman -U metadata-studio-0.1.0-1-any.pkg.tar.zst` |
| NixOS / Nix | flake | `nix profile install github:VanguardArts/metadata-studio` |
| Any distro | Flatpak | `flatpak install com.vanguardarts.MetadataStudio` |
| Any distro (portable) | AppImage | download `metadata-studio-*.AppImage` |
| Any Linux (no root) | portable | `./install.sh` (installs to `~/.local`) |

Build them locally with `make deb`, `make rpm`, `make flatpak`, `make appimage`,
or `make icons` (see `Makefile`).

## CLI

```bash
# Inspect (read-only)
metadata-studio scan ./folder
metadata-studio scan photo.png --json

# Clean (dry run by default)
metadata-studio clean ./folder --artist "Example Artist" --year 2026 --album "[001] Release"
metadata-studio clean ./folder --apply               # actually write
metadata-studio clean ./folder --level 2 --apply     # image transform ladder (degrade watermark)

# Verify (exit 1 if provenance signatures remain — CI-friendly)
metadata-studio verify ./folder
```

The CLI recurses folders, dispatches each file to the right engine by type,
and never touches the sources on a dry run. `--level` follows the
Provenance Scrubber ladder: `0` = lossless metadata strip, `1` = clean
re-encode, `2` = q90 + resample ×0.97 + faint noise, `3` = micro-crop +
resample + color jitter + noise + q88.

## GUI

```bash
metadata-studio-gui
```

Four tabs:

- **Inspect** — recursively scan and show every finding in a colour-coded tree.
- **Clean (batch)** — level picker, dry-run toggle, progress bar, live results.
- **Compare** — side-by-side before/after for a single file.
- **Watch** — monitor a folder (polling) and re-scan on change, flagging new
  provenance findings.

## Monetization

Free basic version, €9–19 Pro tier.

| Free | Pro (€9–19) |
|---|---|
| Inspect EXIF / ID3 / PDF / document | Everything in Free |
| Detect hidden metadata & thumbnails | Transform ladder levels 2–3 |
| Metadata strip (levels 0–1) | Batch processing & folder monitoring |
| Audio / document clean | Before/after comparison & report export |
| | Custom credits & detector plugins |

Upgrade at **https://vanguardarts.vip/**.

## Responsible use

Metadata Studio is a privacy/hygiene tool: it removes personal info, service
fingerprints and junk from files you own. Some distributors and jurisdictions
require disclosure of AI-generated content; removing provenance metadata does
not change a work's copyright status. You are responsible for how you use it.

## License

MIT © 2026 Vanguard Arts SRL — **https://vanguardarts.vip/** · [contact](https://vanguardarts.vip/contact)
