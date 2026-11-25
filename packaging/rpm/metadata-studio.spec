Name:           metadata-studio
Version:        0.1.0
Release:        1%{?dist}
Summary:        Inspect and strip metadata from images, audio and documents
License:        MIT
URL:            https://github.com/VanguardArts/metadata-studio
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
Requires:       python3
Requires:       python3-pillow
Requires:       python3-mutagen
Requires:       python3-pypdf
Requires:       python3-pyside6

%description
Metadata Studio is a unified GUI (and CLI) for inspecting and removing
identifying metadata — EXIF, ID3, C2PA provenance, and PDF/document properties
— from images, audio and document files. Detect hidden metadata and embedded
thumbnails, compare files before/after sanitization, and batch process or
monitor entire folders.

Free basic version with an optional Pro tier (€9-19) via vanguardarts.vip.

%prep
%autosetup

%build
# pure Python

%install
LIBDIR=%{buildroot}%{_prefix}/lib/metadata-studio
mkdir -p "$LIBDIR" %{buildroot}%{_bindir} \
         %{buildroot}%{_datadir}/applications \
         %{buildroot}%{_datadir}/icons/hicolor/scalable/apps

cp -r src/metadata_studio "$LIBDIR/metadata_studio"
cp packaging/cli_main.py packaging/gui_main.py "$LIBDIR/"

printf '#!/bin/sh\nexec python3 %{_prefix}/lib/metadata-studio/cli_main.py "$@"\n' \
    > %{buildroot}%{_bindir}/metadata-studio
printf '#!/bin/sh\nexec python3 %{_prefix}/lib/metadata-studio/gui_main.py "$@"\n' \
    > %{buildroot}%{_bindir}/metadata-studio-gui
chmod 755 %{buildroot}%{_bindir}/metadata-studio %{buildroot}%{_bindir}/metadata-studio-gui

install -m 644 packaging/metadata-studio.desktop \
    %{buildroot}%{_datadir}/applications/metadata-studio.desktop
install -m 644 packaging/metadata-studio.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/metadata-studio.svg
for sz in 16 24 32 48 64 96 128 256 512; do
  install -Dm 644 "packaging/icons/hicolor/${sz}x${sz}/apps/metadata-studio.png" \
      "%{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps/metadata-studio.png"
done

%files
%{_bindir}/metadata-studio
%{_bindir}/metadata-studio-gui
%{_prefix}/lib/metadata-studio/
%{_datadir}/applications/metadata-studio.desktop
%{_datadir}/icons/hicolor/scalable/apps/metadata-studio.svg
%{_datadir}/icons/hicolor/16x16/apps/metadata-studio.png
%{_datadir}/icons/hicolor/24x24/apps/metadata-studio.png
%{_datadir}/icons/hicolor/32x32/apps/metadata-studio.png
%{_datadir}/icons/hicolor/48x48/apps/metadata-studio.png
%{_datadir}/icons/hicolor/64x64/apps/metadata-studio.png
%{_datadir}/icons/hicolor/96x96/apps/metadata-studio.png
%{_datadir}/icons/hicolor/128x128/apps/metadata-studio.png
%{_datadir}/icons/hicolor/256x256/apps/metadata-studio.png
%{_datadir}/icons/hicolor/512x512/apps/metadata-studio.png

%changelog
* Tue Nov 25 2026 Vanguard Arts SRL <https://vanguardarts.vip/> - 0.1.0-1
- Initial release.
