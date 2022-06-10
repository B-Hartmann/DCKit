# -----------------------------------------------------------------------------
# Copyright (c) 2019, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License with exception
# for distributing bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
# -----------------------------------------------------------------------------

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Data files
datas = collect_data_files("dckit", include_py_files=True)
datas += collect_data_files("dckit", subdir="img")

# This is excluded by the PIL-hook and not included automatically
hiddenimports = ["PyQt5"]

