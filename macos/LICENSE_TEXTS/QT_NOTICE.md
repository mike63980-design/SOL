# Qt and Qt for Python notices

SOL.01 uses Qt 6.11.2, PySide6 6.11.2 and Shiboken6 6.11.2 from the
unmodified upstream macOS Python distributions. Qt provides the window,
controls and chart drawing; PySide6 and Shiboken6 provide the Python bindings.
Copyrights remain with The Qt Company Ltd. and the other upstream contributors.

The bundled applicable Qt and Qt for Python libraries are distributed under the
GNU Lesser General Public License version 3. The LGPL adds permissions to the
GNU GPL version 3, so both complete texts are included in
`THIRD_PARTY_LICENSES/LGPL-3.0.txt` and `THIRD_PARTY_LICENSES/GPL-3.0.txt`.
This notice concerns those dependencies; it does not assign a license to
SOL.01's own application code.

Qt also incorporates third-party components with their own licenses. Preserve
the dependency notices in `THIRD_PARTY_LICENSES` when redistributing the package.
The build collects the actual installed macOS distributions' notices and
metadata; `THIRD_PARTY_LICENSES/INDEX.json` identifies those distributions.
See [Qt licensing](https://doc.qt.io/qt-6/licensing.html) and
[Qt for Python](https://doc.qt.io/qtforpython-6/) for upstream details.

## Corresponding upstream sources

The matching source archives are available from Qt's official download service:

- [Qt 6.11.2 complete source ZIP](https://download.qt.io/archive/qt/6.11/6.11.2/single/qt-everywhere-src-6.11.2.zip)
  ([archive directory and checksums](https://download.qt.io/archive/qt/6.11/6.11.2/single/)).
- [PySide6 and Shiboken6 6.11.2 source ZIP](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.zip)
  ([archive directory](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/)).
- [Qt for Python build instructions](https://doc.qt.io/qtforpython-6/building_from_source/index.html).

`BUILD_PROVENANCE.json` records the installed dependency versions and build-input
hashes. SOL.01 includes no upstream Qt, PySide6 or Shiboken6 source changes.
PyInstaller adjusts Mach-O library load paths and signatures while packaging.

## Replacing the libraries

The macOS app loads Qt frameworks, dynamic libraries, plugins and Python
extension modules from `SOL.01.app/Contents/Frameworks` dynamically. PyInstaller
may cross-link package resources under `Contents/Resources`. Qt is not statically
linked into the `Contents/MacOS/SOL.01` executable, and the running application
does not verify Qt library hashes.

Keep a separate backup, close the application, and replace the relevant
`.framework`, `.dylib`, `.so` and plugin files with interface-compatible macOS
builds of the modified libraries. Preserve the selected architecture, Python
and Qt ABIs, the package layout and symlinks. A modified app requires an
appropriate local code signature after replacement; the existing signature,
any notarization ticket and the original download checksum no longer match.
Then launch `SOL.01.app` normally; restore the backup if the replacement is
incompatible. The supplied build kit can also package compatible modified
libraries from an appropriately configured native build environment.

The rights to modify these libraries and to reverse engineer the combined work
for debugging those modifications are governed by the included LGPL/GPL texts.
SOL.01 adds no restriction on exercising those library-license rights.

The license texts were copied verbatim from the
[GNU LGPL v3 text](https://www.gnu.org/licenses/lgpl-3.0.txt) and
[GNU GPL v3 text](https://www.gnu.org/licenses/gpl-3.0.txt), as included in the
original SOL.01 release.
