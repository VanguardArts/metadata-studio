VERSION := 0.1.0

.PHONY: install uninstall icons deb rpm flatpak appimage cli-gui clean

install:
	PREFIX=$(PREFIX) bash install.sh

uninstall:
	PREFIX=$(PREFIX) bash uninstall.sh

icons:
	python3 scripts/make_icons.py

deb:
	bash scripts/build-deb.sh

rpm:
	bash scripts/build-rpm.sh

flatpak:
	bash scripts/build-flatpak.sh

appimage:
	bash scripts/build-appimage.sh

cli-gui:
	python -m pip install --upgrade pip pyinstaller
	pyinstaller --onefile --name metascrub packaging/cli_main.py
	pyinstaller --onefile --windowed --name metascrub-gui packaging/gui_main.py

clean:
	rm -rf build dist *.spec
