import pathlib
import pkg_resources
import signal
import sys
import traceback

import dclab
from dclab.cli import get_job_info
import h5py
import numpy
from PyQt5 import uic, QtCore, QtWidgets
import shapeout

from . import history
from . import meta_tool
from ._version import version as __version__


class DCKit(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        path_ui = pkg_resources.resource_filename("dckit", "main.ui")
        uic.loadUi(path_ui, self)
        self.setWindowTitle("DCKit {}".format(__version__))
        # Disable native menubar (e.g. on Mac)
        self.menubar.setNativeMenuBar(False)
        # signals
        self.pushButton_sample.clicked.connect(self.on_change_sample_names)
        self.pushButton_tdms2rtdc.clicked.connect(self.on_tdms2rtdc)
        self.pushButton_join.clicked.connect(self.on_join)
        self.tableWidget.itemChanged.connect(self.on_table_text_changed)
        # File menu
        self.action_add.triggered.connect(self.on_add_measurements)
        self.action_add_folder.triggered.connect(self.on_add_folder)
        self.action_clear.triggered.connect(self.on_clear_measurements)
        # Help menu
        self.actionSoftware.triggered.connect(self.on_action_software)
        self.actionAbout.triggered.connect(self.on_action_about)
        #: contains all imported paths
        self.pathlist = []

    def append_paths(self, pathlist):
        """Append selected paths to table"""
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        datas = []
        # get meta data for all paths
        for path in pathlist:
            try:  # avoid any errors
                info = {"DCKit-id": (0, len(self.pathlist)),
                        "path": (1, path),
                        "sample": (2, meta_tool.get_sample_name(path)),
                        "run index": (3, meta_tool.get_run_index(path)),
                        "event count": (4, meta_tool.get_event_count(path)),
                        "flow rate": (5, meta_tool.get_flow_rate(path)),
                        }
            except BaseException:
                # stop doing anything
                continue
            self.pathlist.append(pathlib.Path(path))
            datas.append(info)
        # populate table widget
        for info in datas:
            row = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row)
            for key in info:
                col, val = info[key]
                item = QtWidgets.QTableWidgetItem("{}".format(val))
                if key == "sample":
                    # allow editing sample name
                    item.setFlags(QtCore.Qt.ItemIsEnabled
                                  | QtCore.Qt.ItemIsEditable)
                elif key == "path":
                    item.setText(pathlib.Path(val).name)
                    item.setToolTip(str(val))
                    item.setFlags(QtCore.Qt.ItemIsEnabled)
                elif key == "flow rate":
                    item.setText("{:.5f}".format(val))
                    item.setFlags(QtCore.Qt.ItemIsEnabled)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled)
                self.tableWidget.setItem(row, col, item)
        QtWidgets.QApplication.restoreOverrideCursor()

    def dragEnterEvent(self, e):
        """Whether files are accepted"""
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        """Add dropped files to view"""
        urls = e.mimeData().urls()
        pathlist = []
        for ff in urls:
            pp = pathlib.Path(ff.toLocalFile())
            if pp.is_dir():
                pathlist += meta_tool.find_data(pp)
            elif pp.suffix in [".rtdc", ".tdms"]:
                pathlist.append(pp)
        self.append_paths(pathlist)

    def on_action_about(self):
        about_text = "DCKit is a tool for managing RT-DC data.\n\n" \
            + "Author: Paul Müller\n" \
            + "Code: https://github.com/ZELLMECHANIK-DRESDEN/DCKit\n"
        QtWidgets.QMessageBox.about(self,
                                    "DCKit {}".format(__version__),
                                    about_text)

    def on_action_software(self):
        libs = [dclab,
                h5py,
                numpy,
                shapeout,
                ]
        sw_text = "DCKit {}\n\n".format(__version__)
        sw_text += "Python {}\n\n".format(sys.version)
        sw_text += "Modules:\n"
        for lib in libs:
            sw_text += "- {} {}\n".format(lib.__name__, lib.__version__)
        sw_text += "- PyQt5 {}\n".format(QtCore.QT_VERSION_STR)
        if hasattr(sys, 'frozen'):
            sw_text += "\nThis executable has been created using PyInstaller."
        QtWidgets.QMessageBox.information(self,
                                          "Software",
                                          sw_text)

    def on_add_folder(self):
        """Search folder for RT-DC data and add to table"""
        # show a dialog for selecting folder
        path = QtWidgets.QFileDialog.getExistingDirectory()
        if not path:
            return
        # find RT-DC data using shapeout
        pathlist = meta_tool.find_data(path)
        if not pathlist:
            raise ValueError("No RT-DC data found in {}!".format(path))
        # add to list
        self.append_paths(pathlist)

    def on_add_measurements(self):
        """Select .tdms and .rtdc files and add to table"""
        # show a dialog for adding multiple single files (.tdms and .rtdc)
        pathlist, _ = QtWidgets.QFileDialog.getOpenFileNames(
            None,
            'Select RT-DC data',
            '',
            'RT-DC data (*.tdms *.rtdc)')
        if pathlist:
            # add to list
            self.append_paths(pathlist)

    def on_change_sample_names(self):
        """Update the sample names of the datasets"""
        invalid = []
        details = []
        for row in range(self.tableWidget.rowCount()):
            path_index = int(self.tableWidget.item(row, 0).text())
            path = self.pathlist[path_index]
            newname = self.tableWidget.item(row, 2).text()
            oldname = meta_tool.get_sample_name(path)
            if isinstance(oldname, bytes):
                oldname = oldname.decode('utf_8')
            # compare sample names bytes-insensitive
            if newname != oldname:
                if path.suffix == ".tdms":
                    # not supported for tdms files
                    invalid.append(path)
                else:
                    # change sample name
                    with h5py.File(path, "a") as h5:
                        h5.attrs["experiment:sample"] = numpy.string_(
                            newname.encode("utf-8"))
                    # add entry to the log
                    task_dict = {
                        "name": "update attributes",
                        "old": {"experiment:sample": oldname},
                        "new": {"experiment:sample": newname},
                        }
                    append_execution_log(path, task_dict)
                    details.append("- {}: {} -> {}".format(path, oldname,
                                                           newname))
        if invalid:
            # Show an error dialog for the tdms files
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText("Renaming .tdms sample names not supported!")
            msg.setInformativeText(
                "Changing the sample name for .tdms files is "
                + "not supported! Please convert the files to "
                + "the .rtdc file format.")
            msg.setWindowTitle("Unsupported action")
            msg.setDetailedText("Affected files are:\n"
                                + "\n".join([str(p) for p in invalid]))
            msg.exec_()

        # finally, show the feedback dialog
        msg = QtWidgets.QMessageBox()
        if len(details):
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setText("Successfully renamed sample names!")
            msg.setWindowTitle("Success")
            msg.setDetailedText("\n".join(details))
        else:
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Nothing to do!")
            msg.setWindowTitle("Warning")
        msg.exec_()

    def on_clear_measurements(self):
        """Clear the table"""
        for _ in range(len(self.pathlist)):
            self.tableWidget.removeRow(0)
        self.pathlist = []

    def on_join(self):
        """Join multiple RT-DC measurements"""
        pass

    def on_table_text_changed(self):
        """Reset sample name if set to empty string"""
        curit = self.tableWidget.currentItem()
        if curit is not None and curit.text() == "":
            row = self.tableWidget.currentRow()
            path_index = int(self.tableWidget.item(row, 0).text())
            sample = meta_tool.get_sample_name(self.pathlist[path_index])
            self.tableWidget.item(row, 2).setText(sample)

    def on_tdms2rtdc(self):
        """Convert .tdms files to .rtdc files"""
        pass


def append_execution_log(path, task_dict):
    info = get_job_info()
    info["libraries"]["shapeout"] = shapeout.__version__
    info["task"] = task_dict
    history.append_history(path, info)


def excepthook(etype, value, trace):
    """
    Handler for all unhandled exceptions.

    :param `etype`: the exception type (`SyntaxError`,
        `ZeroDivisionError`, etc...);
    :type `etype`: `Exception`
    :param string `value`: the exception error message;
    :param string `trace`: the traceback header, if any (otherwise, it
        prints the standard Python header: ``Traceback (most recent
        call last)``.
    """
    vinfo = "Unhandled exception in Shape-Out version {}:\n".format(
        __version__)
    tmp = traceback.format_exception(etype, value, trace)
    exception = "".join([vinfo]+tmp)

    errorbox = QtWidgets.QMessageBox()
    errorbox.addButton(QtWidgets.QPushButton('Close'),
                       QtWidgets.QMessageBox.YesRole)
    errorbox.addButton(QtWidgets.QPushButton(
        'Copy text && Close'), QtWidgets.QMessageBox.NoRole)
    errorbox.setText(exception)
    ret = errorbox.exec_()
    if ret == 1:
        cb = QtWidgets.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(exception)


# Make Ctr+C close the app
signal.signal(signal.SIGINT, signal.SIG_DFL)
# Display exception hook in separate dialog instead of crashing
sys.excepthook = excepthook
