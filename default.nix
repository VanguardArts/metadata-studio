# Nix package for Metadata Studio.
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
  pname = "metadata-studio";
  version = "0.1.0";

  src = ./.;

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    install -dm755 "$out/lib/metadata-studio"
    cp -r src/metadata_studio "$out/lib/metadata-studio/metadata_studio"
    cp packaging/cli_main.py packaging/gui_main.py "$out/lib/metadata-studio/"

    makeWrapper "${py}/bin/python3" "$out/bin/metadata-studio" \
      --add-flags "$out/lib/metadata-studio/cli_main.py"
    makeWrapper "${py}/bin/python3" "$out/bin/metadata-studio-gui" \
      --add-flags "$out/lib/metadata-studio/gui_main.py"

    install -Dm644 packaging/metadata-studio.desktop \
      "$out/share/applications/metadata-studio.desktop"
    install -Dm644 packaging/metadata-studio.svg \
      "$out/share/icons/hicolor/scalable/apps/metadata-studio.svg"
    for sz in 16 24 32 48 64 96 128 256 512; do
      install -Dm644 packaging/icons/hicolor/''${sz}x''${sz}/apps/metadata-studio.png \
        "$out/share/icons/hicolor/''${sz}x''${sz}/apps/metadata-studio.png"
    done
    runHook postInstall
  '';

  meta = with lib; {
    description = "Inspect and strip metadata from images, audio and documents (CLI + GUI)";
    homepage = "https://github.com/VanguardArts/metadata-studio";
    license = licenses.mit;
    mainProgram = "metadata-studio";
    platforms = platforms.linux;
  };
}
