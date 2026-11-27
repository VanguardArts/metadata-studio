# Nix package for Metascrub.
#
# Build with:  nix build
{ lib, stdenv, python3, makeWrapper }:

let
  py = python3.withPackages (ps: [
    ps.pillow
    ps.mutagen
    ps.pypdf
    ps.pyside6
  ]);
in
stdenv.mkDerivation rec {
  pname = "metascrub";
  version = "0.1.0";

  src = ./.;

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    install -dm755 "$out/lib/metascrub"
    cp -r src/metascrub "$out/lib/metascrub/metascrub"
    cp packaging/cli_main.py packaging/gui_main.py "$out/lib/metascrub/"

    makeWrapper "${py}/bin/python3" "$out/bin/metascrub" \
      --add-flags "$out/lib/metascrub/cli_main.py"
    makeWrapper "${py}/bin/python3" "$out/bin/metascrub-gui" \
      --add-flags "$out/lib/metascrub/gui_main.py"

    install -Dm644 packaging/metascrub.desktop \
      "$out/share/applications/metascrub.desktop"
    install -Dm644 packaging/metascrub.svg \
      "$out/share/icons/hicolor/scalable/apps/metascrub.svg"
    for sz in 16 24 32 48 64 96 128 256 512; do
      install -Dm644 packaging/icons/hicolor/''${sz}x''${sz}/apps/metascrub.png \
        "$out/share/icons/hicolor/''${sz}x''${sz}/apps/metascrub.png"
    done
    runHook postInstall
  '';

  meta = with lib; {
    description = "Inspect and strip metadata from images, audio and documents (CLI + GUI)";
    homepage = "https://github.com/VanguardArts/metascrub";
    license = licenses.mit;
    mainProgram = "metascrub";
    platforms = platforms.linux;
  };
}
