# -*- coding: utf-8 -*-

"""
This file contains a custom Colorbar Widget to be used with pyqtgraph.ImageItem or qudi
ScanImageItem.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import numpy as np
from pyqtgraph import mkPen, mkBrush, GraphicsObject, getConfigOption, PlotWidget
from qtpy import QtCore, QtGui, QtWidgets
from qtwidgets.scientific_spinbox import ScienDSpinBox
from core.util.filters import scan_blink_correction
from gui.colordefs import ColorScaleInferno

__all__ = ['ColorBarWidget']


class ColorBarItem(GraphicsObject):
    def __init__(self, min_val=0, max_val=1, cmap=None, pen=None):
        """
        Graphics object to draw a colorbar inside a pyqtgraph PlotWidget
        """
        super().__init__()
        self._min_val = float(min_val)
        self._max_val = float(max_val)
        self._cmap = ColorScaleInferno().cmap_normed if cmap is None else cmap
        self._pen = mkPen('k') if pen is None else mkPen(pen)
        self._brush = None
        self._shape = None
        self.picture = None
        self._set_brush()
        self.update()
        self.informViewBoundsChanged()

    def _set_brush(self):
        grad = QtGui.QLinearGradient(0, self._min_val, 0, self._max_val)
        for stop, color in zip(*self._cmap.getStops('float')):
            grad.setColorAt(1.0 - stop, QtGui.QColor(*[255 * c for c in color]))
        self._brush = mkBrush(QtGui.QBrush(grad))
        return

    def set_range(self, min_val, max_val):
        self._min_val = float(min_val)
        self._max_val = float(max_val)
        self._set_brush()
        self.draw_picture()
        self.informViewBoundsChanged()

    def set_cmap(self, cmap=None):
        self._cmap = ColorScaleInferno().cmap_normed if cmap is None else cmap
        self._set_brush()
        self.draw_picture()
        return

    def draw_picture(self):
        self.picture = QtGui.QPicture()
        self._shape = QtGui.QPainterPath()
        p = QtGui.QPainter(self.picture)
        p.setPen(self._pen)
        p.setBrush(self._brush)
        rect = QtCore.QRectF(0, self._min_val, 1.0, self._max_val - self._min_val)
        p.drawRect(rect)
        self._shape.addRect(rect)
        p.end()
        self.prepareGeometryChange()
        return

    def paint(self, p, *args):
        if self.picture is None:
            self.draw_picture()
        self.picture.play(p)

    def boundingRect(self):
        if self.picture is None:
            self.draw_picture()
        return QtCore.QRectF(self.picture.boundingRect())

    def shape(self):
        if self.picture is None:
            self.draw_picture()
        return self._shape


class ColorBarWidget(QtWidgets.QWidget):
    """
    """
    rangeChanged = QtCore.Signal(tuple)
    percentileChanged = QtCore.Signal(tuple)

    def __init__(self, parent=None, unit=None, label=None, image_item=None):
        super().__init__(parent)
        self._image_item = image_item

        self.min_spinbox = ScienDSpinBox()
        self.min_spinbox.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                       QtWidgets.QSizePolicy.Fixed)
        self.min_spinbox.setAlignment(QtCore.Qt.AlignRight)
        self.min_spinbox.setMinimumWidth(75)
        self.min_spinbox.setMinimum(0)
        self.max_spinbox = ScienDSpinBox()
        self.max_spinbox.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                       QtWidgets.QSizePolicy.Fixed)
        self.max_spinbox.setAlignment(QtCore.Qt.AlignRight)
        self.min_spinbox.setMinimumWidth(75)
        self.max_spinbox.setMinimum(0)
        self.low_percentile_spinbox = ScienDSpinBox()
        self.low_percentile_spinbox.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                                  QtWidgets.QSizePolicy.Fixed)
        self.low_percentile_spinbox.setAlignment(QtCore.Qt.AlignRight)
        self.low_percentile_spinbox.setMinimumWidth(75)
        self.low_percentile_spinbox.setRange(0, 100)
        self.low_percentile_spinbox.setSuffix('%')
        self.high_percentile_spinbox = ScienDSpinBox()
        self.high_percentile_spinbox.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                                   QtWidgets.QSizePolicy.Fixed)
        self.high_percentile_spinbox.setAlignment(QtCore.Qt.AlignRight)
        self.high_percentile_spinbox.setMinimumWidth(75)
        self.high_percentile_spinbox.setRange(0, 100)
        self.high_percentile_spinbox.setSuffix('%')
        if unit is not None:
            self.max_spinbox.setSuffix(unit)
            self.min_spinbox.setSuffix(unit)

        self.colorbar = ColorBarItem()
        self.cb_plot_widget = PlotWidget()
        self.cb_plot_widget.setMinimumWidth(75)
        self.cb_plot_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.cb_plot_widget.addItem(self.colorbar)
        self.cb_plot_widget.hideAxis('bottom')
        self.cb_plot_widget.setLabel('left', text=label, units=unit)
        self.cb_plot_widget.setMouseEnabled(x=False, y=False)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.max_spinbox)
        main_layout.addWidget(self.high_percentile_spinbox)
        main_layout.addWidget(self.cb_plot_widget)
        main_layout.addWidget(self.low_percentile_spinbox)
        main_layout.addWidget(self.min_spinbox)

        # main_layout.setSpacing(0)
        main_layout.setContentsMargins(1, 1, 1, 1)
        self.setLayout(main_layout)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

    def sizeHint(self):
        return QtCore.QSize(90, 100)

    def set_label(self, text, unit=None):
        self.cb_plot_widget.setLabel('left', text=text, units=unit)
        if unit is not None:
            self.max_spinbox.setSuffix(unit)
            self.min_spinbox.setSuffix(unit)
        return