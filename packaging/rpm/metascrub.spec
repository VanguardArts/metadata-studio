Name:           metascrub
Version:        0.1.0
Release:        1%{?dist}
Summary:        Inspect and strip metadata from images, audio and documents
License:        MIT
URL:            https://github.com/VanguardArts/metascrub
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
Requires:       python3
Requires:       python3-pillow
Requires:       python3-mutagen
Requires:       python3-pypdf
Requires:       python3-pyside6

%description
Metascrub is a unified GUI (and CLI) for inspecting and removing
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
LIBDIR=%{buildroot}%{_prefix}/lib/metascrub
mkdir -p "$LIBDIR" %{buildroot}%{_bindir} \
         %{buildroot}%{_datadir}/applications \
         %{buildroot}%{_datadir}/icons/hicolor/scalable/apps

cp -r src/metascrub "$LIBDIR/metascrub"
cp packaging/cli_main.py packaging/gui_main.py "$LIBDIR/"

printf '#!/bin/sh\nexec python3 %{_prefix}/lib/metascrub/cli_main.py "$@"\n' \
    > %{buildroot}%{_bindir}/metascrub
printf '#!/bin/sh\nexec python3 %{_prefix}/lib/metascrub/gui_main.py "$@"\n' \
    > %{buildroot}%{_bindir}/metascrub-gui
chmod 755 %{buildroot}%{_bindir}/metascrub %{buildroot}%{_bindir}/metascrub-gui

install -m 644 packaging/metascrub.desktop \
    %{buildroot}%{_datadir}/applications/metascrub.desktop
install -m 644 packaging/metascrub.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/metascrub.svg
for sz in 16 24 32 48 64 96 128 256 512; do
  install -Dm 644 "packaging/icons/hicolor/${sz}x${sz}/apps/metascrub.png" \
      "%{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps/metascrub.png"
done

%files
%{_bindir}/metascrub
%{_bindir}/metascrub-gui
%{_prefix}/lib/metascrub/
%{_datadir}/applications/metascrub.desktop
%{_datadir}/icons/hicolor/scalable/apps/metascrub.svg
%{_datadir}/icons/hicolor/16x16/apps/metascrub.png
%{_datadir}/icons/hicolor/24x24/apps/metascrub.png
%{_datadir}/icons/hicolor/32x32/apps/metascrub.png
%{_datadir}/icons/hicolor/48x48/apps/metascrub.png
%{_datadir}/icons/hicolor/64x64/apps/metascrub.png
%{_datadir}/icons/hicolor/96x96/apps/metascrub.png
%{_datadir}/icons/hicolor/128x128/apps/metascrub.png
%{_datadir}/icons/hicolor/256x256/apps/metascrub.png
%{_datadir}/icons/hicolor/512x512/apps/metascrub.png

%changelog
* Tue Nov 25 2026 Vanguard Arts SRL <https://vanguardarts.vip/> - 0.1.0-1
- Initial release.
