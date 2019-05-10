# -*- coding: utf-8 -*-

"""
This file contains modified pyqtgraph Widgets/Items for Qudi to display scan images.

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

from pyqtgraph import PlotWidget, ImageItem, ViewBox, InfiniteLine, ROI
from qtpy import QtCore
from core.util.filters import scan_blink_correction
from gui.colordefs import ColorScaleInferno

__all__ = ['ScanImageItem', 'ScanPlotWidget', 'ScanViewBox']


class ScanImageItem(ImageItem):
    """
    Extension of pg.ImageItem to display scanning microscopy images.
    Adds the signal sigMouseClicked to tap into mouse click events and receive the real world data
    coordinate of the click.
    Adds blink correction functionality capable of filtering out single pixel wide artifacts along
    a single image dimension. This is done by applying a non-linear 1D min-max-filter along a
    single image dimension.
    """
    sigMouseClicked = QtCore.Signal(object, QtCore.QPointF)

    def __init__(self, *args, **kwargs):
        self.use_blink_correction = False
        self.blink_correction_axis = 0
        self.orig_image = None
        super().__init__(*args, **kwargs)
        # Change default colorscale
        self.setLookupTable(ColorScaleInferno().lut)
        return

    def set_image_extent(self, extent):
        if len(extent) != 2:
            raise TypeError('Image extent must be iterable of length 2.')
        if len(extent[0]) != 2 or len(extent[1]) != 2:
            raise TypeError('Image extent for each axis must be iterable of length 2.')
        x_min, x_max = sorted(extent[0])
        y_min, y_max = sorted(extent[1])
        self.setRect(QtCore.QRectF(x_min, y_min, x_max - x_min, y_max - y_min))
        return

    def activate_blink_correction(self, set_active, axis=0):
        """
        De-/Activates the blink correction filter.
        Can filter out single pixel wide artifacts along a single image dimension.

        @param bool set_active: activate (True) or deactivate (False) the filter
        @param int axis: Array dimension to apply the filter on (0 or 1)
        """
        set_active = bool(set_active)
        axis = int(axis)
        if self.use_blink_correction != set_active:
            self.blink_correction_axis = axis
            self.use_blink_correction = set_active
            if set_active:
                self.setImage(self.image, autoLevels=False)
            else:
                self.setImage(self.orig_image, autoLevels=False)
        elif axis != self.blink_correction_axis:
            self.blink_correction_axis = axis
            if self.use_blink_correction:
                self.setImage(self.orig_image, autoLevels=False)
        return

    def setImage(self, image=None, autoLevels=None, **kwargs):
        """
        pg.ImageItem method override to apply optional filter when setting image data.
        """
        if self.use_blink_correction:
            self.orig_image = image
            image = scan_blink_correction(image=image, axis=self.blink_correction_axis)
        retval = super().setImage(image=image, autoLevels=autoLevels, **kwargs)
        return retval

    def mouseClickEvent(self, ev):
        if not ev.double():
            pos = self.getViewBox().mapSceneToView(ev.scenePos())
            self.sigMouseClicked.emit(ev.button(), pos)
        return super().mouseClickEvent(ev)


class ScanPlotWidget(PlotWidget):
    """
    Extend the PlotWidget Class with more functionality used for qudi scan images.
    Supported features:
     - draggable/static crosshair with optional range and size constraints.
     - zoom feature by rubberband selection
     - rubberband area selection

    This class depends on the ScanViewBox class defined further below.
    This class can be promoted in the Qt designer.
    """
    sigMouseAreaSelected = QtCore.Signal(QtCore.QRectF)  # mapped rectangle mouse cursor selection

    def __init__(self, *args, **kwargs):
        kwargs['viewBox'] = ScanViewBox()  # Use custom pg.ViewBox subclass
        super().__init__(*args, **kwargs)
        self.getViewBox().sigMouseAreaSelected.connect(self.sigMouseAreaSelected)
        # self.getViewBox().sigRangeChanged.connect(self._constraint_crosshair_size)
        self.crosshairs = list()

    @property
    def selection_enabled(self):
        return bool(self.getViewBox().rectangle_selection)

    @property
    def zoom_by_selection_enabled(self):
        return bool(self.getViewBox().zoom_by_selection)

    def toggle_selection(self, enable):
        """
        De-/Activate the rectangular rubber band selection tool.
        If active you can select a rectangular region within the ViewBox by dragging the mouse
        with the left button. Each selection rectangle in real-world data coordinates will be
        emitted by sigMouseAreaSelected.
        By using toggle_zoom_by_selection you can optionally de-/activate zooming in on the
        selection.

        @param bool enable: Toggle selection on (True) or off (False)
        """
        return self.getViewBox().toggle_selection(enable)

    def toggle_zoom_by_selection(self, enable):
        """
        De-/Activate automatic zooming into a selection.
        See also: toggle_selection

        @param bool enable: Toggle zoom upon selection on (True) or off (False)
        """
        return self.getViewBox().toggle_zoom_by_selection(enable)

    def add_crosshair(self, *args, **kwargs):
        """
        Add a crosshair to this ScanPlotWidget.
        You can pass all optional parameters you can pass to ScanCrosshair.__init__
        The stacking of crosshairs will be in order of insertion (last added crosshair is on top).
        Keep stacking in mind when you want to have a draggable crosshair.
        """
        # Create new ScanCrosshair instance and add to crosshairs list
        self.crosshairs.append(ScanCrosshair(self.getViewBox(), *args, **kwargs))
        # Add crosshair to ViewBox
        self.crosshairs[-1].add_to_view()
        return

    def remove_crosshair(self, index=-1):
        """
        Remove the crosshair at position <index> or the last one added (default) from this
        ScanPlotWidget.
        """
        crosshair = self.crosshairs.pop(index)
        # Remove crosshair from ViewBox
        crosshair.remove_from_view()
        return

    def hide_crosshair(self, index):
        crosshair = self.crosshairs[index]
        crosshair.remove_from_view()
        return

    def show_crosshair(self, index):
        crosshair = self.crosshairs[index]
        crosshair.add_to_view()
        return

    def bring_crosshair_on_top(self, index):
        """

        @param index:
        """
        crosshair = self.crosshairs[index]
        crosshair.vline.setZValue(10)
        crosshair.hline.setZValue(10)
        crosshair.crosshair.setZValue(11)
        return


class ScanViewBox(ViewBox):
    """
    Extension for pg.ViewBox to be used with ScanPlotWidget.

    Implements optional rectangular rubber band area selection and optional corresponding zooming.
    """

    sigMouseAreaSelected = QtCore.Signal(QtCore.QRectF)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zoom_by_selection = False
        self.rectangle_selection = False
        return

    def toggle_selection(self, enable):
        """
        De-/Activate the rectangular rubber band selection tool.
        If active you can select a rectangular region within the ViewBox by dragging the mouse
        with the left button. Each selection rectangle in real-world data coordinates will be
        emitted by sigMouseAreaSelected.
        By using toggle_zoom_by_selection you can optionally de-/activate zooming in on the
        selection.

        @param bool enable: Toggle selection on (True) or off (False)
        """
        self.rectangle_selection = bool(enable)
        return

    def toggle_zoom_by_selection(self, enable):
        """
        De-/Activate automatic zooming into a selection.
        See also: toggle_selection

        @param bool enable: Toggle zoom upon selection on (True) or off (False)
        """
        self.zoom_by_selection = bool(enable)
        return

    def mouseDragEvent(self, ev, axis=None):
        """
        Additional mouse drag event handling to implement rubber band selection and zooming.
        """
        if self.rectangle_selection and ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            self.updateScaleBox(ev.buttonDownPos(), ev.pos())
            if ev.isFinish():
                self.rbScaleBox.hide()
                start = self.mapToView(ev.buttonDownPos())
                stop = self.mapToView(ev.pos())
                rect = QtCore.QRectF(start, stop)
                if self.zoom_by_selection:
                    # AutoRange needs to be disabled by hand because of a pyqtgraph bug.
                    if self.autoRangeEnabled():
                        self.disableAutoRange()
                    self.setRange(rect=rect, padding=0)
                self.sigMouseAreaSelected.emit(rect)
            return
        else:
            return super().mouseDragEvent(ev, axis)


class ScanCrosshair(QtCore.QObject):
    """
    Represents a crosshair (two perpendicular infinite lines and optionally a rectangle around the
    intersection) to be used in ScanPlotWidget.

    @param QPointF|float[2] position:
    @param QSizeF|float[2] size:
    @param float min_size_factor:
    @param float[2] allowed_range:
    @param bool movable:
    @param QPen pen:
    @param QPen hover_pen:
    """

    _default_pen = {'color': '#00ff00', 'width': 1}
    _default_hover_pen = {'color': '#ffff00', 'width': 1}

    sigPosChanged = QtCore.Signal(float, float)
    sigDraggedPosChanged = QtCore.Signal(float, float)
    sigDragStarted = QtCore.Signal()
    sigDragStopped = QtCore.Signal()

    def __init__(self, viewbox, position=None, size=None, min_size_factor=None, allowed_range=None,
                 movable=None, pen=None, hover_pen=None):
        super().__init__()
        self._viewbox = viewbox
        self._min_size_factor = 0.02
        self._size = (0, 0)
        self._allowed_range = None
        self.__is_dragged = False

        self.crosshair = ROI((0, 0),
                             (0, 0),
                             pen=self._default_pen if pen is None else pen)
        self.hline = InfiniteLine(pos=0,
                                  angle=0,
                                  movable=False,
                                  pen=self._default_pen,
                                  hoverPen=self._default_hover_pen)
        self.vline = InfiniteLine(pos=0,
                                  angle=90,
                                  movable=False,
                                  pen=self._default_pen,
                                  hoverPen=self._default_hover_pen)

        if pen is not None:
            self.set_pen(pen)
        if hover_pen is not None:
            self.set_hover_pen(hover_pen)
        if position is not None:
            self.set_position(position)
        if size is not None:
            self.set_size(size)
        if min_size_factor is not None:
            self.set_min_size_factor(min_size_factor)
        if allowed_range is not None:
            self.set_allowed_range(allowed_range)
        if movable is not None:
            self.set_movable(movable)

        self._viewbox.sigRangeChanged.connect(self._constraint_size)
        self.vline.sigDragged.connect(self._update_pos_from_line)
        self.vline.sigPositionChangeFinished.connect(self._finish_drag)
        self.hline.sigDragged.connect(self._update_pos_from_line)
        self.hline.sigPositionChangeFinished.connect(self._finish_drag)
        self.crosshair.sigRegionChanged.connect(self._update_pos_from_roi)
        self.crosshair.sigRegionChangeFinished.connect(self._finish_drag)
        self.sigDraggedPosChanged.connect(self.sigPosChanged)

    @property
    def movable(self):
        return bool(self.crosshair.translatable)

    @property
    def position(self):
        pos = self.vline.pos()
        pos[1] = self.hline.pos()[1]
        return tuple(pos)

    @property
    def size(self):
        return tuple(self._size)

    @property
    def min_size_factor(self):
        return float(self._min_size_factor)

    @property
    def allowed_range(self):
        if self._allowed_range is None:
            return None
        return tuple(self._allowed_range)

    def _update_pos_from_line(self, obj=None):
        """
        Called each time the position of the InfiniteLines has been changed by a user drag.
        Causes the crosshair rectangle to follow the lines.
        """
        pos = self.vline.pos()
        pos[1] = self.hline.pos()[1]
        size = self.crosshair.size()
        if not self.__is_dragged:
            self.__is_dragged = True
            self.sigDragStarted.emit()
        self.crosshair.blockSignals(True)
        self.crosshair.setPos((pos[0] - size[0] / 2, pos[1] - size[1] / 2))
        self.crosshair.blockSignals(False)
        self.sigDraggedPosChanged.emit(*pos)
        return

    def _update_pos_from_roi(self, obj=None):
        """
        Called each time the position of the rectangular ROI has been changed by a user drag.
        Causes the InfiniteLines to follow the ROI.
        """
        pos = self.crosshair.pos()
        size = self.crosshair.size()
        pos[0] += size[0] / 2
        pos[1] += size[1] / 2
        if not self.__is_dragged:
            self.__is_dragged = True
            self.sigDragStarted.emit()
        self.vline.setPos(pos[0])
        self.hline.setPos(pos[1])
        self.sigDraggedPosChanged.emit(*pos)
        return

    def _finish_drag(self):
        if self.__is_dragged:
            self.__is_dragged = False
            self.sigDragStopped.emit()
        return

    def _constraint_size(self):
        if self._min_size_factor == 0:
            return
        if self._size[0] == 0 or self._size[1] == 0:
            return
        corr_size = self._get_corrected_size(self._size)
        if corr_size != tuple(self.crosshair.size()):
            self.set_size(corr_size, set_as_default=False)
        return

    def _get_corrected_size(self, size):
        try:
            size = tuple(size)
        except TypeError:
            size = (size.width(), size.height())

        min_size = min(size)
        if min_size == 0:
            return size
        vb_size = self._viewbox.viewRect().size()
        short_index = int(vb_size.width() > vb_size.height())
        min_vb_size = vb_size.width() if short_index == 0 else vb_size.height()
        min_vb_size *= self._min_size_factor

        if min_size < min_vb_size:
            scale_factor = min_vb_size / min_size
            size = (size[0] * scale_factor, size[1] * scale_factor)
        return size

    def add_to_view(self):
        self._viewbox.addItem(self.vline)
        self._viewbox.addItem(self.hline)
        self._viewbox.addItem(self.crosshair)

    def remove_from_view(self):
        self._viewbox.removeItem(self.vline)
        self._viewbox.removeItem(self.hline)
        self._viewbox.removeItem(self.crosshair)

    def set_movable(self, movable):
        """
        (Un-)Set the crosshair movable (draggable by mouse cursor).

        @param bool movable: Set the crosshair movable (True) or not (False)
        """
        self.crosshair.translatable = bool(movable)
        self.vline.setMovable(movable)
        self.hline.setMovable(movable)
        return

    def set_position(self, pos):
        """
        Set the crosshair center to the given coordinates.

        @param QPointF|float[2] pos: (x,y) position of the crosshair
        """
        try:
            pos = tuple(pos)
        except TypeError:
            pos = (pos.x(), pos.y())
        size = self.crosshair.size()

        self.crosshair.blockSignals(True)
        self.vline.blockSignals(True)
        self.hline.blockSignals(True)
        self.crosshair.setPos(pos[0] - size[0] / 2, pos[1] - size[1] / 2)
        self.vline.setPos(pos[0])
        self.hline.setPos(pos[1])
        self.crosshair.blockSignals(False)
        self.vline.blockSignals(False)
        self.hline.blockSignals(False)
        self.sigPosChanged.emit(*pos)
        return

    def set_size(self, size, set_as_default=True):
        """
        Set the (optionally default) size of the crosshair rectangle (x, y) and update the display.

        @param QSize|float[2] size: the (x,y) size of the crosshair rectangle
        @param bool set_as_default: Set default crosshair size and enforce minimal size (True).
                                    Enforce displayed crosshair size while keeping default size
                                    untouched (False).
        """
        try:
            size = tuple(size)
        except TypeError:
            size = (size.width(), size.height())

        if set_as_default:
            if size[0] <= 0 and size[1] <= 0:
                self._size = (0, 0)
            else:
                self._size = size
                # Check if actually displayed size needs to be adjusted due to minimal size
                size = self._get_corrected_size(size)

        pos = self.vline.pos()
        pos[1] = self.hline.pos()[1] - size[1] / 2
        pos[0] -= size[0] / 2

        if self._allowed_range:
            crange = self._allowed_range
            self.crosshair.maxBounds = QtCore.QRectF(crange[0][0] - size[0] / 2,
                                                     crange[1][0] - size[1] / 2,
                                                     crange[0][1] - crange[0][0] + size[0],
                                                     crange[1][1] - crange[1][0] + size[1])
        self.crosshair.blockSignals(True)
        self.crosshair.setSize(size)
        self.crosshair.setPos(pos)
        self.crosshair.blockSignals(False)
        return

    def set_min_size_factor(self, factor):
        """
        Sets the minimum crosshair size factor. This will determine the minimum size of the
        smallest edge of the crosshair center rectangle.
        This minimum size is calculated by taking the smallest visible axis of the ViewBox and
        multiplying it with the scale factor set by this method.
        The crosshair rectangle will be then scaled accordingly if the set crosshair size is
        smaller than this minimal size.

        @param float factor: The scale factor to set. If <= 0 no minimal crosshair size enforced.
        """
        if factor <= 0:
            self._min_size_factor = 0
        elif factor <= 1:
            self._min_size_factor = float(factor)
        else:
            raise ValueError('Crosshair min size factor must be a value <= 1.')
        return

    def set_allowed_range(self, new_range):
        """
        Sets a range boundary for the crosshair position.

        @param float[2][2] new_range: two min-max range value tuples (for x and y axis).
                                      If None set unlimited ranges.
        """
        if new_range is None:
            self.vline.setBounds([None, None])
            self.hline.setBounds([None, None])
            self.crosshair.maxBounds = None
        else:
            self.vline.setBounds(new_range[0])
            self.hline.setBounds(new_range[1])
            size = self.crosshair.size()
            pos = self.position
            self.crosshair.maxBounds = QtCore.QRectF(new_range[0][0] - size[0] / 2,
                                                     new_range[1][0] - size[1] / 2,
                                                     new_range[0][1] - new_range[0][0] + size[0],
                                                     new_range[1][1] - new_range[1][0] + size[1])
            self.crosshair.setPos(pos[0] - size[0] / 2, pos[1] - size[1] / 2)
        self._allowed_range = new_range
        return

    def set_pen(self, pen):
        """
        Sets the pen to be used for drawing the crosshair lines.
        Given parameter must be compatible with pyqtgraph.mkPen()

        @param pen: pyqtgraph compatible pen to use
        """
        self.crosshair.setPen(pen)
        self.vline.setPen(pen)
        self.hline.setPen(pen)
        return

    def set_hover_pen(self, pen):
        """
        Sets the pen to be used for drawing the crosshair lines when the mouse cursor is hovering
        over them.
        Given parameter must be compatible with pyqtgraph.mkPen()

        @param pen: pyqtgraph compatible pen to use
        """
        # self.crosshair.setPen(pen)
        self.vline.setHoverPen(pen)
        self.hline.setHoverPen(pen)
        return
