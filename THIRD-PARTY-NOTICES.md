# Third-party notices

The portable application includes CPython (PSF), Qt/PySide6/Shiboken6 (LGPLv3 and applicable component licenses), psutil (BSD-3-Clause), pyodbc (MIT), SQLite (public domain) and the PyInstaller bootloader (GPLv2 with application-bundling exception). License texts are in `LICENSES`. Qt remains in replaceable shared libraries in the portable folder. The application source and build scripts are public; reverse engineering to debug modified LGPL components is permitted.

The single-file Windows executable embeds these same runtime libraries and extracts them to a temporary directory at launch. The accompanying portable ZIP and public build scripts support replacing compatible LGPL libraries and rebuilding. No Python installation is needed for either Windows format. PyInstaller is a packaging tool; its bundling exception does not impose GPL licensing on application code.

The Python wheel contains project Python source and notices, with no bundled native libraries or third-party runtime dependencies. `gui`, `sql` and `telemetry` extras resolve their separately licensed dependencies through pip. The Android package, when execution-verified, contains CPython 3.14, SQLite and [Chaquopy 17.2](https://github.com/chaquo/chaquopy) (MIT), with applicable license texts included as Android assets. It does not contain Qt, CUDA, SQL Server, psutil or model weights. Android SDK, Gradle and JDK are build tools, not additional application kernels.

Bundled Python runtime components also include OpenSSL (Apache-2.0 for the included modern releases), libffi (MIT), zlib (zlib license), bzip2 and XZ/liblzma (applicable permissive notices). Their notices are included in `LICENSES` and in Android assets. These components provide standard-library support, not new entity mathematics.

Upstream sources and notices: [CPython](https://www.python.org/downloads/source/), [Qt/PySide](https://code.qt.io/cgit/pyside/pyside-setup.git/), [Qt licenses](https://doc.qt.io/qtforpython-6/licenses.html), [psutil](https://github.com/giampaolo/psutil), [pyodbc](https://github.com/mkleehammer/pyodbc), [SQLite](https://sqlite.org/copyright.html), [PyInstaller](https://pyinstaller.org/en/stable/license.html).

CUDA, NVIDIA drivers, cuDNN, PyTorch, SQL Server, Microsoft ODBC drivers, Ollama and Qwen model weights are external integrations and are not bundled. No code or model files were copied from another ATOMVERSE application. Generic license texts were reused from existing local copies. The project's own license decision is recorded separately.
