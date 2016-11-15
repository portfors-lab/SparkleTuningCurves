import operator
import os
import sys
import ctypes
import glob
import json

import h5py
import numpy as np
import scipy.stats as stats

import matplotlib
import numpy as np
import matplotlib.cm as cm
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt

from PyQt4 import QtCore, QtGui

from ui.tuning_curves_ui import Ui_Form_tuning_curves

from util.spikestats import get_spike_times


class MyForm(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_Form_tuning_curves()
        self.ui.setupUi(self)
        self.dialog = QtGui.QMainWindow

        self.filename = ''
        self.threshold = 0

        self.backup_dir = ''
        self.basefname = ''

        QtCore.QObject.connect(self.ui.pushButton_browse, QtCore.SIGNAL("clicked()"), self.browse)
        QtCore.QObject.connect(self.ui.comboBox_test_num, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.load_traces)
        QtCore.QObject.connect(self.ui.comboBox_test_num, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.load_channels)
        QtCore.QObject.connect(self.ui.comboBox_trace, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.load_stim_info)

        QtCore.QObject.connect(self.ui.pushButton_auto_threshold, QtCore.SIGNAL("clicked()"), self.auto_threshold)
        QtCore.QObject.connect(self.ui.doubleSpinBox_threshold, QtCore.SIGNAL("valueChanged(const QString&)"), self.update_thresh)

        QtCore.QObject.connect(self.ui.comboBox_channel, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.generate_view)
        QtCore.QObject.connect(self.ui.comboBox_trace, QtCore.SIGNAL("currentIndexChanged(const QString&)"), self.generate_view)

        self.ui.view.threshLine.sigPositionChangeFinished.connect(self.update_thresh2)

        QtCore.QObject.connect(self.ui.pushButtonGenerate, QtCore.SIGNAL("clicked()"), self.generate_tuning_curve)

    def browse(self):
        self.ui.comboBox_test_num.clear()
        self.ui.comboBox_channel.clear()
        self.ui.comboBox_trace.clear()

        self.ui.lineEdit_comments.setEnabled(False)
        self.ui.lineEdit_comments.setText('')
        self.ui.comboBox_test_num.setEnabled(False)
        self.ui.comboBox_channel.setEnabled(False)
        self.ui.comboBox_trace.setEnabled(False)

        file_dialog = QtGui.QFileDialog(self)
        self.filename = QtGui.QFileDialog.getOpenFileName(file_dialog, 'Open', '', "HDF5 files (*.hdf5)")

        self.ui.lineEdit_file_name.setText(self.filename)

        # If the filename is not blank, attempt to extract test numbers and place them into the combobox
        if self.filename != '':
            if '.hdf5' in self.filename:
                try:
                    h_file = h5py.File(unicode(self.filename), 'r')
                except IOError:
                    self.add_message('Error: I/O Error')
                    return

                tests = {}
                for key in h_file.keys():
                    if 'segment' in key:
                        for test in h_file[key].keys():
                            tests[test] = int(test.replace('test_', ''))

                sorted_tests = sorted(tests.items(), key=operator.itemgetter(1))

                for test in sorted_tests:
                    self.ui.comboBox_test_num.addItem(test[0])

                self.ui.lineEdit_comments.setEnabled(True)
                self.ui.comboBox_test_num.setEnabled(True)
                self.ui.comboBox_channel.setEnabled(True)
                self.ui.comboBox_trace.setEnabled(True)

                h_file.close()

                self.generate_view()

            else:
                self.add_message('Error: Must select a .hdf5 file.')
                return
        else:
            self.add_message('Error: Must select a file to open.')
            return

    def valid_filename(self):
        filename = self.ui.lineEdit_file_name.text()

        # Validate filename
        if filename != '':
            if '.hdf5' in filename:
                try:
                    temp_file = h5py.File(unicode(self.filename), 'r')
                    temp_file.close()
                except IOError:
                    self.add_message('Error: I/O Error')
                    return False
            else:
                self.add_message('Error: Must select a .hdf5 file.')
                return False
        else:
            self.add_message('Error: Must select a file to open.')
            return False

        return True

    def load_traces(self):
        self.ui.comboBox_trace.clear()
        self.ui.comboBox_trace.setEnabled(False)

        if self.valid_filename():
            h_file = h5py.File(unicode(self.filename), 'r')
            target_test = self.ui.comboBox_test_num.currentText()
        else:
            self.ui.comboBox_trace.setEnabled(False)
            return

        if self.ui.comboBox_test_num.count() == 0:
            self.ui.comboBox_trace.setEnabled(False)
            self.ui.comboBox_trace.clear()
            h_file.close()
            return

        target_seg = 0
        for key in h_file.keys():
            if 'segment' in key:
                for test in h_file[key].keys():
                    if target_test == test:
                        target_seg = key
                        target_test = test

        traces = h_file[target_seg][target_test].value.shape[0]

        for i in range(traces):
            self.ui.comboBox_trace.addItem('trace_' + str(i + 1))

        self.ui.comboBox_trace.setEnabled(True)

        comment = h_file[target_seg].attrs['comment']
        self.ui.lineEdit_comments.setText(comment)

        h_file.close()

        self.generate_view()

    def load_channels(self):
        self.ui.comboBox_channel.clear()
        self.ui.comboBox_channel.setEnabled(False)

        if self.valid_filename():
            h_file = h5py.File(unicode(self.filename), 'r')
            target_test = self.ui.comboBox_test_num.currentText()
        else:
            return

        if self.ui.comboBox_test_num.count() == 0:
            self.ui.comboBox_trace.setEnabled(False)
            self.ui.comboBox_trace.clear()
            h_file.close()
            return

        target_seg = 0
        for key in h_file.keys():
            if 'segment' in key:
                for test in h_file[key].keys():
                    if target_test == test:
                        target_seg = key
                        target_test = test

        if len(h_file[target_seg][target_test].value.shape) > 3:
            channels = h_file[target_seg][target_test].value.shape[2]
        else:
            channels = 1

        if channels == 1:
            self.ui.comboBox_channel.addItem('channel_1')
        else:
            for i in range(channels):
                self.ui.comboBox_channel.addItem('channel_' + str(i+1))

        if self.ui.comboBox_channel.count() < 2:
            self.ui.comboBox_channel.setEnabled(False)
        else:
            self.ui.comboBox_channel.setEnabled(True)

        h_file.close()

        self.generate_view()

    def load_stim_info(self):
        if self.valid_filename():
            h_file = h5py.File(unicode(self.filename), 'r')
            target_test = self.ui.comboBox_test_num.currentText()
        else:
            return

        target_seg = ''

        for key in h_file.keys():
            if 'segment' in key:
                for test in h_file[key].keys():
                    if target_test == test:
                        target_seg = key
                        target_test = test

        target_trace = 0

        if self.ui.comboBox_trace.currentText() != '':
            target_trace = int(self.ui.comboBox_trace.currentText().replace('trace_', '')) - 1

        stim_info = eval(h_file[target_seg][target_test].attrs['stim'])
        self.ui.label_stim_type.setText(stim_info[target_trace]['components'][0]['stim_type'])

        h_file.close()

    def generate_view(self):
        if self.valid_filename():
            h_file = h5py.File(unicode(self.filename), 'r')
            target_test = self.ui.comboBox_test_num.currentText()
        else:
            return

        target_seg = ''

        for key in h_file.keys():
            if 'segment' in key:
                for test in h_file[key].keys():
                    if target_test == test:
                        target_seg = key
                        target_test = test

        fs = h_file[target_seg].attrs['samplerate_ad']

        target_trace = []
        target_rep = []
        target_chan = []

        # Get the values from the combo boxes
        self.ui.comboBox_test_num.currentText()
        if self.ui.comboBox_trace.currentText() != '':
            target_trace = int(self.ui.comboBox_trace.currentText().replace('trace_', '')) - 1
        # if self.ui.comboBox_rep.currentText() != 'All' and self.ui.comboBox_rep.currentText() != '':
        #     target_rep = int(self.ui.comboBox_rep.currentText().replace('rep_', '')) - 1
        if self.ui.comboBox_channel.currentText() != '':
            target_chan = int(self.ui.comboBox_channel.currentText().replace('channel_', '')) - 1

        test_data = h_file[target_seg][target_test].value
        presentation = []

        # Get the presentation data depending on if there is a channel field or not
        if len(test_data.shape) == 4:
            presentation = test_data[target_trace, target_rep, target_chan, :]
        elif len(test_data.shape) == 3:
            presentation = test_data[target_trace, target_rep, :]

        len_presentation = len(presentation)

        # Get the length of the window and length of presentation depending on if all is selected or not
        if len_presentation != 0:
            window = len(presentation) / float(fs)
        else:
            if len(test_data.shape) == 4:
                window = len(test_data[0, 0, 0, :]) / float(fs)
                len_presentation = len(test_data[0, 0, 0, :])
            elif len(test_data.shape) == 3:
                window = len(test_data[0, 0, :]) / float(fs)
                len_presentation = len(test_data[0, 0, :])

        xlist = np.linspace(0, float(window), len_presentation)
        ylist = presentation

        # TODO Set window size
        if True:  # not self.ui.checkBox_custom_window.checkState():
            if len(presentation) > 0:
                ymin = min(presentation)
                ymax = max(presentation)
            else:
                ymin = 0
                ymax = 0
                if len(test_data.shape) == 3:
                    rep_len = test_data.shape[1]
                    for i in range(rep_len):
                        if not test_data[target_trace, i, :].any():
                            return
                        if min(test_data[target_trace, i, :]) < ymin:
                            ymin = min(test_data[target_trace, i, :])
                        if max(test_data[target_trace, i, :]) > ymax:
                            ymax = max(test_data[target_trace, i, :])
                else:
                    rep_len = test_data.shape[1]
                    for i in range(rep_len):
                        if not test_data[target_trace, i, target_chan, :].any():
                            return
                        if min(test_data[target_trace, i, target_chan, :]) < ymin:
                            ymin = min(test_data[target_trace, i, target_chan, :])
                        if max(test_data[target_trace, i, target_chan, :]) > ymax:
                            ymax = max(test_data[target_trace, i, target_chan, :])

            self.ui.view.setXRange(0, window, 0)
            self.ui.view.setYRange(ymin, ymax, 0.1)

        self.ui.view.tracePlot.clear()
        # Fix xlist to be the length of presentation
        if len(test_data.shape) == 3:
            self.ui.view.addTraces(xlist, test_data[target_trace, :, :])
        else:
            self.ui.view.addTraces(xlist, test_data[target_trace, :, target_chan, :])

        h_file.close()

    def generate_tuning_curve(self):
        if self.valid_filename():
            h_file = h5py.File(unicode(self.filename), 'r')
            target_test = self.ui.comboBox_test_num.currentText()
        else:
            return

        target_seg = []
        # Find target segment
        for segment in h_file.keys():
            for test in h_file[segment].keys():
                if target_test == test:
                    target_seg = segment
                    target_test = test

        trace_data = h_file[target_seg][target_test].value

        fs = h_file[target_seg].attrs['samplerate_ad']

        samples = trace_data.shape[-1]
        traces = trace_data.shape[0]
        reps = trace_data.shape[1]

        if len(h_file[target_seg][target_test].value.shape) > 3:
            channels = h_file[target_seg][target_test].value.shape[2]
        else:
            channels = 1

        stim_info = eval(h_file[target_seg][target_test].attrs['stim'])

        # Get the values from the combo boxes
        if self.ui.comboBox_trace.currentText() != '':
            target_trace = int(self.ui.comboBox_trace.currentText().replace('trace_', '')) - 1
        if self.ui.comboBox_channel.currentText() != '':
            target_chan = int(self.ui.comboBox_channel.currentText().replace('channel_', '')) - 1

        # Get the values from the spinbox
        thresh = self.ui.doubleSpinBox_threshold.value()

        # print 'test:', target_test
        # print 'trace:', target_trace
        # print 'chan:', target_chan
        # print ''

        frequency = []
        intensity = []
        spike_count = {}

        if len(trace_data.shape) == 4:
            for t in range(traces):
                # print 'trace:', t
                # print 'stim_type:', stim_info[t]['components'][0]['stim_type']
                # print 'intensity:', stim_info[t]['components'][0]['intensity']
                # if stim_info[t]['components'][0]['stim_type'] != 'silence':
                #     print 'frequency:', stim_info[t]['components'][0]['frequency']

                if stim_info[t]['components'][0]['stim_type'] != 'silence':
                    intensity.append(stim_info[t]['components'][0]['intensity'])
                    frequency.append(stim_info[t]['components'][0]['frequency']/1000)

                    spikes = 0
                    for r in range(reps):
                        trace = trace_data[t][r][target_chan]

                        spike_times = 1000 * np.array(get_spike_times(trace, thresh, fs))
                        spikes += len(spike_times)

                    spike_count[(stim_info[t]['components'][0]['frequency']/1000, stim_info[t]['components'][0]['intensity'])] = float(spikes)/float(reps)
                    # print 'spikes:', float(spikes)
                    # print 'avg_spikes:', float(spikes)/float(reps)

        # Get only the unique values
        frequency = sorted(list(set(frequency)))
        intensity = sorted(list(set(intensity)))

        # print 'freq', len(frequency), frequency
        # print 'inten', len(intensity), intensity

        xlist = np.linspace(min(frequency), max(frequency), len(frequency))
        ylist = np.linspace(min(intensity), max(intensity), len(intensity))

        # print 'xlist', len(xlist), xlist
        # print 'ylist', len(ylist), ylist

        # Initialize Z
        Z = np.empty([len(intensity), len(frequency)])

        X, Y = np.meshgrid(xlist, ylist)
        for y in range(len(intensity)):
            for x in range(len(frequency)):
                Z[y][x] = spike_count[(frequency[x], intensity[y])]
                # print '(y, x):', y, x
                # print 'freq:', frequency[x]
                # print 'inten:', intensity[y]


        plt.figure()
        cp = plt.contourf(X, Y, Z)
        plt.colorbar(cp, label='Mean Spikes Per Presentation')

        # print 'X:', X
        # print 'Y:', Y
        # print 'Z:', Z

        # plt.title('Tuning Curve')
        if channels == 1:
            plt.title(str.split(str(self.filename), '/')[-1].replace('.hdf5', '') + ' ' + str(
                self.ui.comboBox_test_num.currentText()).replace('test_', 'Test '))
        else:
            plt.title(str.split(str(self.filename), '/')[-1].replace('.hdf5', '') + ' ' + str(
                self.ui.comboBox_test_num.currentText()).replace('test_', 'Test ') + ' ' + str(
                self.ui.comboBox_channel.currentText()).replace('channel_', 'Channel '))
        plt.xlabel('Frequency (kHz)')
        # plt.xlabel('Frequency (Hz)')
        plt.ylabel('Intensity (dB)')

        # Idea to try interpolation, didn't work as intended
        # plt.imshow(Z, aspect='equal', interpolation=None, origin='lower')

        plt.show()

    def auto_threshold(self):
        thresh_fraction = 0.7

        if self.valid_filename():
            h_file = h5py.File(unicode(self.filename), 'r')
            target_test = self.ui.comboBox_test_num.currentText()
        else:
            return

        # Find target segment
        target_seg = []
        for segment in h_file.keys():
            for test in h_file[segment].keys():
                if target_test == test:
                    target_seg = segment
                    target_test = test

        trace_data = h_file[target_seg][target_test].value

        if len(trace_data.shape) == 4:
            target_chan = int(self.ui.comboBox_channel.currentText().replace('channel_', '')) - 1

            # Compute threshold from average maximum of traces
            max_trace = []
            for n in range(len(trace_data[1, :, target_chan, 0])):
                max_trace.append(np.max(np.abs(trace_data[1, n, target_chan, :])))
            average_max = np.array(max_trace).mean()
            thresh = thresh_fraction * average_max

            # self.add_message(trace_data.shape)

        elif len(trace_data.shape) == 3:
            # Compute threshold from average maximum of traces
            max_trace = []
            for n in range(len(trace_data[1, :, 0])):
                max_trace.append(np.max(np.abs(trace_data[1, n, :])))
            average_max = np.array(max_trace).mean()
            thresh = thresh_fraction * average_max

            # self.add_message(trace_data.shape)

        self.ui.doubleSpinBox_threshold.setValue(thresh)
        self.update_thresh()

        h_file.close()

    def update_thresh(self):
        self.ui.view.setThreshold(self.ui.doubleSpinBox_threshold.value())
        self.ui.view.update_thresh()

    def update_thresh2(self):
        self.ui.doubleSpinBox_threshold.setValue(self.ui.view.getThreshold())

    def add_message(self, message):
        self.message_num += 1
        self.ui.textEdit.append('[' + str(self.message_num) + ']: ' + message + '\n')

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    myApp = MyForm()
    myApp.setWindowIcon(QtGui.QIcon('images/horsey.ico'))
    myApp.show()
    sys.exit(app.exec_())

