import numpy as np
import pyqtgraph as pg
from copy import deepcopy

from QtWrapper import QtCore, QtGui

import spikestats
from QtWrapper import QtCore
from raster_bounds_dlg import RasterBoundsDialog
from viewbox import SpikeyViewBox

STIM_HEIGHT = 0.05

# Switch to using white background and black foreground
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOptions(useWeave=False)

class BasePlot(pg.PlotWidget):
    """Abstract class meant to be subclassed by other plot types.

    Handles some common user interaction to be the same across plots
    """
    def __init__(self, parent=None):
        super(BasePlot, self).__init__(parent, viewBox=SpikeyViewBox())

        # print 'scene', self.scene().contextMenu[0].text()
        # # self.scene().contextMenu = []
        # print '-'*20
        # for act in self.getPlotItem().vb.menu.actions():
        #     if act.text() != 'View All':
        #         print 'removing', act.text()
        #         self.getPlotItem().vb.menu.removeAction(act)
        # print '-'*20

        for act in self.getPlotItem().ctrlMenu.actions():
            # print act.text()
            if act.text() != 'Grid':
                self.getPlotItem().ctrlMenu.removeAction(act)

        self.setMouseEnabled(x=False, y=True)

    def setXlim(self, lim):
        """Sets the visible x-axis bounds to *lim*

        :param lim: (min, max) for x-axis
        :type lim: (float, float)
        """
        self.setXRange(*lim, padding=0)

    def setYlim(self, lim):
        """Sets the visible y-axis bounds to *lim*

        :param lim: (min, max) for y-axis
        :type lim: (float, float)
        """
        self.setYRange(*lim)

    def setTitle(self, title):
        """Sets a title for the plot

        :param title: Title for top of plot
        :type title: str
        """
        self.getPlotItem().setTitle(title)

    def getTitle(self):
        return str(self.getPlotItem().titleLabel.text)

    def getLabel(self, key):
        """Gets the label assigned to an axes

        :param key:???
        :type key: str
        """
        axisItem = self.getPlotItem().axes[key]['item']
        return axisItem.label.toPlainText()

class TraceWidget(BasePlot):
    """Main plot object for experimental data

    Includes : recording electrode trace
               stimulus signal
               spike raster
    """
    nreps = 20
    rasterTop = 0.9 # top of raster plot (proportion)
    rasterBottom = 0.5 # bottom of raster plot
    # this will be set automatically
    rasterYslots = None
    thresholdUpdated = QtCore.Signal(float, str)
    polarityInverted = QtCore.Signal(int, str)
    rasterBoundsUpdated = QtCore.Signal(tuple, str)
    absUpdated = QtCore.Signal(bool, str)
    _polarity = 1
    _ampScalar = None
    _abs = True

    def __init__(self, parent=None):
        super(TraceWidget, self).__init__(parent)

        self.tracePlot = self.plot(pen='k')
        self.rasterPlot = self.plot(pen=None, symbol='s', symbolPen=None, symbolSize=4, symbolBrush='k')
        self.stimPlot = self.plot(pen='b')
        self.stimPlot.curve.setToolTip("Stimulus Signal")
        self.tracePlot.curve.setToolTip("Spike Trace")

        self.sigRangeChanged.connect(self.rangeChange)

        self.disableAutoRange()

        self.threshLine = pg.InfiniteLine(pos=0.5, angle=0, pen='r', movable=True)

        invertAction = QtGui.QAction('Invert response polarity', None)
        invertAction.setCheckable(True)
        self.scene().contextMenu.append(invertAction) #should use function for this?
        invertAction.triggered.connect(self.invertPolarity)

        self.absAction = QtGui.QAction('Abs threshold', None)
        self.absAction.setCheckable(True)
        self.absAction.setChecked(self._abs)
        self.scene().contextMenu.append(self.absAction)
        self.absAction.triggered.connect(self.toggleAbs)

        self.addItem(self.threshLine)
        self.threshLine.sigPositionChangeFinished.connect(self.update_thresh)
        self.setLabel('left', '', units='V')
        self.setLabel('bottom', 'Time', units='s')

        self.hideButtons()  # hides the 'A' Auto-scale button
        self.updateRasterBounds()
        self.trace_stash = []
        self.legend_names = []

    def updateData(self, axeskey, x, y):
        """Replaces the currently displayed data

        :param axeskey: name of data plot to update. Valid options are 'stim' or 'response'
        :type axeskey: str
        :param x: index values associated with y to plot
        :type x: numpy.ndarray
        :param y: values to plot at x
        :type y: numpy.ndarray
        """
        if axeskey == 'stim':
            self.stimPlot.setData(x, y)
            # call manually to ajust placement of signal
            ranges = self.viewRange()
            self.rangeChange(self, ranges)
        if axeskey == 'response':
            self.clearTraces()
            # No longer used due to removal of _traceUnit 'A'
            # if self._traceUnit == 'A':
            #     y = y * self._ampScalar
            # if self.zeroAction.isChecked():
            #     start_avg = np.mean(y[5:25])
            #     y = y - start_avg
            self.tracePlot.setData(x, y * self._polarity)

    def addTraces(self, x, ys):
        self.clearTraces()
        nreps = ys.shape[0]
        for irep in range(nreps):
            self.trace_stash.append(self.plot(x, ys[irep, :] * self._polarity, pen=(irep, nreps)))

    def addTracesABR(self, x, ys, intensity, trace_num):
        self.clearTraces()
        nreps = ys.shape[0]
        for irep in reversed(range(nreps)):
            self.trace_stash.append(self.plot(x, ys[irep, :], pen=(irep, nreps)))
            line = self.plot(pen=pg.intColor(irep, hues=nreps))
            self.legend.addItem(line, 'trace_' + str(trace_num[irep]) + ': ' + str(intensity[irep]) + ' dB')
            self.legend_names.append('trace_' + str(trace_num[irep]) + ': ' + str(intensity[irep]) + ' dB')

    def addTraceAverage(self, x, ys, label):
        nreps = ys.shape[0]
        for irep in reversed(range(nreps)):
            self.trace_stash.append(self.plot(x, ys[irep, :], pen=(irep, nreps)))
            line = self.plot(pen=pg.intColor(irep, hues=nreps))
            self.legend.addItem(line, label)
            self.legend_names.append(label)
        self.resetPen()

    def resetPen(self):
        temp = []
        temp2 = self.legend
        temp3 = []

        for name in self.legend_names:
            temp2.removeItem(name)

        self.clearTraces()

        nreps = len(self.trace_stash)
        for irep in range(nreps):
            temp.append(self.plot(self.trace_stash[irep].getData()[0], self.trace_stash[irep].getData()[1], pen=(irep, nreps)))
            line = self.plot(pen=pg.intColor(irep, hues=nreps))
            temp2.addItem(line, self.legend_names[irep])
            temp3.append(self.legend_names[irep])
        self.trace_stash = temp
        self.legend = temp2
        self.legend_names = temp3

    def clearTraces(self):
        for trace in self.trace_stash:
            self.removeItem(trace)
        for name in self.legend_names:
            self.legend.removeItem(name)

    def removeLegend(self):
        self.legend.scene().removeItem(self.legend)

    def appendData(self, axeskey, bins, ypoints):
        """Appends data to existing plotted data

        :param axeskey: name of data plot to update. Valid options are 'stim' or 'response'
        :type axeskey: str
        :param bins: bins to plot a point for
        :type bin: numpy.ndarray
        :param ypoints: iteration number of raster, *should* match bins dimension, but really takes the first value in array for iteration number and plot row at proper place for included bins
        :type ypoints: numpy.ndarray
        """
        if axeskey == 'raster' and len(bins) > 0:
            x, y = self.rasterPlot.getData()
            # don't plot overlapping points
            bins = np.unique(bins)
            # adjust repetition number to response scale
            ypoints = np.ones_like(bins)*self.rasterYslots[ypoints[0]]
            x = np.append(x, bins)
            y = np.append(y, ypoints)
            self.rasterPlot.setData(x, y)

    def clearData(self, axeskey):
        """Clears the raster plot"""
        self.rasterPlot.clear()

    def getThreshold(self):
        """Current Threshold value

        :returns: float -- y values of the threshold line
        """
        y = self.threshLine.value()
        return y

    def setThreshold(self, threshold):
        """Sets the current threshold

        :param threshold: the y value to set the threshold line at
        :type threshold: float
        """
        self.threshLine.setValue(threshold)

    def setNreps(self, nreps):
        """Sets the number of reps user by raster plot to determine where to
        place data points

        :param nreps: number of iterations before the raster will be cleared
        :type nreps: int
        """
        self.nreps = nreps
        self.updateRasterBounds()

    def setRasterBounds(self, lims):
        """Sets the raster plot y-axis bounds, where in the plot the raster will appear between

        :param lims: the (min, max) y-values for the raster plot to be placed between
        :type lims: (float, float)
        """
        self.rasterBottom = lims[0]
        self.rasterTop = lims[1]
        self.updateRasterBounds()

    def updateRasterBounds(self):
        """Updates the y-coordinate slots where the raster points
        are plotted, according to the current limits of the y-axis"""
        yrange = self.viewRange()[1]
        yrange_size = yrange[1] - yrange[0]
        rmax = self.rasterTop*yrange_size + yrange[0]
        rmin = self.rasterBottom*yrange_size + yrange[0]
        self.rasterYslots = np.linspace(rmin, rmax, self.nreps)
        self.rasterBoundsUpdated.emit((self.rasterBottom, self.rasterTop), self.getTitle())

    def askRasterBounds(self):
        """Prompts the user to provide the raster bounds with a dialog.
        Saves the bounds to be applied to the plot"""
        dlg = RasterBoundsDialog(bounds= (self.rasterBottom, self.rasterTop))
        if dlg.exec_():
            bounds = dlg.values()
            self.setRasterBounds(bounds)

    def getRasterBounds(self):
        """Current raster y-axis plot limits

        :returns: (float, float) -- (min, max) of raster plot bounds
        """
        return (self.rasterBottom, self.rasterTop)

    def toggleUnits(self):
        if self._traceUnit == 'V':
            self.setLabel('bottom', 'Current', units='A')
            self._traceUnit = 'A'
            self.unitsAction.setText("Plot Volts")
        else:
            self.setLabel('bottom', 'Potential', units='V')
            self._traceUnit = 'V'
            self.unitsAction.setText("Plot Amps")

    def rangeChange(self, pw, ranges):
        """Adjusts the stimulus signal to keep it at the top of a plot,
        after any ajustment to the axes ranges takes place.

        This is a slot for the undocumented pyqtgraph signal sigRangeChanged.
        From what I can tell the arguments are:

        :param pw: reference to the emitting object (plot widget in my case)
        :type pw: object
        :param ranges: I am only interested when this turns out to be a nested list of axis bounds
        :type ranges: object
        """
        if hasattr(ranges, '__iter__'):
            # adjust the stim signal so that it falls in the correct range
            yrange_size = ranges[1][1] - ranges[1][0]
            stim_x, stim_y = self.stimPlot.getData()
            if stim_y is not None:
                stim_height = yrange_size * STIM_HEIGHT
                # take it to 0
                stim_y = stim_y - np.amin(stim_y)
                # normalize
                if np.amax(stim_y) != 0:
                    stim_y = stim_y/np.amax(stim_y)
                # scale for new size
                stim_y = stim_y*stim_height
                # raise to right place in plot
                stim_y = stim_y + (ranges[1][1] - (stim_height*1.1 + (stim_height*0.2)))
                self.stimPlot.setData(stim_x, stim_y)
            # rmax = self.rasterTop * yrange_size + ranges[1][0]
            # rmin = self.rasterBottom * yrange_size + ranges[1][0]
            self.updateRasterBounds()

    def update_thresh(self):
        """Emits a Qt signal thresholdUpdated with the current threshold value"""
        thresh_val = self.threshLine.value()
        self.thresholdUpdated.emit(thresh_val, self.getTitle())

    def invertPolarity(self, inverted):
        if inverted:
            pol = -1
        else:
            pol = 1
        self._polarity = pol
        self.polarityInverted.emit(pol, self.getTitle())

    def setAbs(self, absval):
        self._abs = absval
        self.absAction.setChecked(absval)

    def toggleAbs(self, absval):
        self._abs = absval
        self.absUpdated.emit(self._abs, self.getTitle())

class PSTHWidget(BasePlot):
    """Post Stimulus Time Histogram plot widget, for plotting spike counts"""
    _bins = np.arange(5)
    _counts = np.zeros((5,))
    _threshold = 0.1
    _polarity = 1

    def __init__(self, parent=None):
        super(PSTHWidget, self).__init__(parent)
        self.histo = pg.BarGraphItem(x=self._bins, height=self._counts, width=0.5)
        self.addItem(self.histo)
        self.setLabel('bottom', 'Time Bins', units='s')
        self.setLabel('left', 'Spike Counts')
        self.setXlim((0, 0.25))
        self.setYlim((0, 10))

        self.getPlotItem().vb.setZeroWheel()

    def setBins(self, bins):
        """Sets the bin centers (x values)

        :param bins: time bin centers
        :type bins: numpy.ndarray
        """
        self._bins = bins
        self._counts = np.zeros_like(self._bins)
        bar_width = bins[0]*1.5
        self.histo.setOpts(x=bins, height=self._counts, width=bar_width)
        self.setXlim((0, bins[-1]))

    def clearData(self):
        """Clears all histograms (keeps bins)"""
        self._counts = np.zeros_like(self._bins)
        self.histo.setOpts(height=self._counts)

    def appendData(self, bins, repnum=None):
        """Increases the values at bins (indexes)

        :param bins: bin center values to increment counts for, to increment a time bin more than once include multiple items in list with that bin center value
        :type bins: numpy.ndarray
        """
        # only if the last sample was above threshold, but last-1 one wasn't
        bins[bins >= len(self._counts)] = len(self._counts) -1
        bin_totals = np.bincount(bins)
        self._counts[:len(bin_totals)] += bin_totals
        self.histo.setOpts(height=np.array(self._counts))

    def getData(self):
        """Gets the heights of the histogram bars

        :returns: list<int> -- the count values for each bin
        """
        return self.histo.opts['height']

    def processData(self, times, response, test_num, trace_num, rep_num):
        """Calulate spike times from raw response data"""
        # invert polarity affects spike counting
        response = response * self._polarity

        if rep_num == 0:
            # reset
            self.spike_counts = []
            self.spike_latencies = []
            self.spike_rates = []

        fs = 1./(times[1] - times[0])

        # process response; calculate spike times
        spike_times = spikestats.spike_times(response, self._threshold, fs)
        self.spike_counts.append(len(spike_times))
        if len(spike_times) > 0:
            self.spike_latencies.append(spike_times[0])
        else:
            self.spike_latencies.append(np.nan)
        self.spike_rates.append(spikestats.firing_rate(spike_times, times))

        binsz = self._bins[1] - self._bins[0]
        response_bins = spikestats.bin_spikes(spike_times, binsz)
        # self.putnotify('spikes_found', (response_bins, rep_num))
        self.appendData(response_bins, rep_num)

    def setThreshold(self, thresh):
        self._threshold = thresh
        # reload data?
