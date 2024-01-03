# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    The interactive map gives the ability to easily send a new
#                 position command to a crazyflie by clicking onto the map.
#                 Connected crazyflies are displayed on the map.
#
# --------------------- LICENSE -----------------------------------------------
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
# or write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
# -----------------------------------------------------------------------------

import os
import collections
import math

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtGui import QBrush, QPen
from PyQt5.QtCore import Qt


root = os.path.dirname(os.path.realpath(__file__))
(ViewIntMapClass,
 viewBaseClass) = (uic.loadUiType(os.path.join(root,'ui/graphicsview_intmap.ui')))

class InteractiveMap(QtWidgets.QGraphicsView, ViewIntMapClass):
    _addCfToSceneSignal = pyqtSignal(str)
    _updateSetPosMarkerSignal = pyqtSignal(str, object)
    _removeCfFromSceneSignal = pyqtSignal(str)
    _drawPathTailSignal = pyqtSignal(str, object)
    _removeDrawPathTailSignal = pyqtSignal(str)
    _scaleIntMapSignal = pyqtSignal()
    _addPointToPointCloudSignal = pyqtSignal(object, str)
    _clearPointCloudSignal = pyqtSignal()

    def __init__(self, config, com):
        super(InteractiveMap, self).__init__()
        self.setupUi(self)
        self._config = config
        self._com = com

        self.linkUrisList = []
        linkUrisConfig = self._config.readCategory("crazyflies")
        for link_uri, address in linkUrisConfig.items():
            self.linkUrisList.append(link_uri)

        self._currentSetting = self._config.readValue("interactiveMap", "setting")
        self._mapWidthMeter = self._config.readValue("interactiveMap", "width")
        self._mapDepthMeter = self._config.readValue("interactiveMap", "depth")

        self._obstacles = {}
        self._obstaclesSent  = False

        self._graphicsViewWidthPixel = self.frameGeometry().width()
        self._graphicsViewDepthPixel = self.frameGeometry().height()
        self._graphicsSceneWidthPixel = 0
        self._graphicsSceneDepthPixel = 0
        self._graphicsSceneMarginTopPixel = 0
        self._graphicsSceneMarginBottomPixel = 0
        self._graphicsSceneMarginLeftPixel = 0
        self._graphicsSceneMarginRightPixel = 0

        # Laboratory:          Default:
        #            |              ↑ y
        #     x      |              |
        #     ←------+------        |
        #            |              |        x
        #          y ↓              +--------→

        if self._currentSetting == "Laboratory":
            self._marginTopPixel = 0.05 * self._graphicsViewDepthPixel
            self._marginBottomPixel = 0.02 * self._graphicsViewDepthPixel
            self._marginLeftPixel = 0.02 * self._graphicsViewWidthPixel
            self._marginRightPixel = 0.05 * self._graphicsViewWidthPixel
            self.transformCoordPixelToMeter = self.transformCoordPixelToMeterLaboratorySetting
            # graphicsScene
            self.transformXCoordMeterToPixelScene = self.transformXCoordMeterToPixelLabSetting
            self.transformYCoordMeterToPixelScene = self.transformYCoordMeterToPixelLabSetting
            self.transformCoordMeterToPixelScene = self.transformCoordMeterToPixelLabSetting
        else:
            self._marginTopPixel = 0.02 * self._graphicsViewDepthPixel
            self._marginBottomPixel = 0.05 * self._graphicsViewDepthPixel
            self._marginLeftPixel = 0.05 * self._graphicsViewWidthPixel
            self._marginRightPixel = 0.02 * self._graphicsViewWidthPixel
            self.transformCoordPixelToMeter = self.transformCoordPixelToMeterDefaultSetting
            # graphicsScene
            self.transformXCoordMeterToPixelScene = self.transformXCoordMeterToPixelDefaultSetting
            self.transformYCoordMeterToPixelScene = self.transformYCoordMeterToPixelDefaultSetting
            self.transformCoordMeterToPixelScene = self.transformCoordMeterToPixelDefaultSetting
        self._cfPixmapRadiusPixel = 5

        self._intMapCfObjects = {}
        self._intMapCfObjectsPosMeter = {}
        self._intMapCfSetPosMarker = {}
        self._intMapCfSetPosMarkerPosMeter = {}
        self._intMapCfPathTailsPixel = {}
        self._intMapCfPathTailsMeter = {}
        self._intMapCfPathTailObjects = {}
        self._pointCloud = []
        self._cfColors = {}

        # Route ui manipulation through signal/slots
        self._addCfToSceneSignal.connect(self._populateScene)
        self._updateSetPosMarkerSignal.connect(self._updateSceneSetPos)
        self._removeCfFromSceneSignal.connect(self._removeFromScene)
        self._drawPathTailSignal.connect(self._drawPathTail)
        self._removeDrawPathTailSignal.connect(self._removeDrawPathTail)
        self._scaleIntMapSignal.connect(self._scaleIntMap)
        self._addPointToPointCloudSignal.connect(self._addPointToPointCloud)
        self._clearPointCloudSignal.connect(self._clearPointCloud)

        # Create publisher and subscriber
        self.pubUpdateSetPos = self._com.publisher("intMap/updatedSetPos")
        self._com.subscriber("cfControl/connected", self._addCfToScene)
        self._com.subscriber("cfControl/disconnected", self._removeCfFromScene)
        self._com.subscriber("cfControl/disconnected", self.removeDrawPathTail)
        self._com.subscriber("cfControl/updatedPosition", self._updateCfPosScene)
        self._com.subscriber("cfControl/updatedPosition", self._drawCfPathTail)
        self._com.subscriber("cfControl/rrtGoalPos", self._updateCfSetPosMarkerScene)
        self._com.subscriber("flightCommander/updatedSetPos", self._updateCfSetPosMarkerScene)

        # Colors for drawing on the interactive map
        self.colorList = [Qt.green, Qt.blue, Qt.cyan, Qt.red,
                            Qt.darkRed, Qt.magenta, Qt.darkGreen, Qt.gray]

        for link_uri, i in zip(self.linkUrisList, range(8)):
            self._cfColors[link_uri] = self.colorList[i]

        # Process coordinates when clicking on the interactive map
        self.mousePressEvent = self._getPixel

    def updateGraphicsViewGeometry(self):
        self._graphicsViewWidthPixel = self.frameGeometry().width()
        self._graphicsViewDepthPixel = self.frameGeometry().height()
        if self._currentSetting == "Laboratory":
            self._marginTopPixel = 0.05 * self._graphicsViewDepthPixel
            self._marginBottomPixel = 0.02 * self._graphicsViewDepthPixel
            self._marginLeftPixel = 0.02 * self._graphicsViewWidthPixel
            self._marginRightPixel = 0.05 * self._graphicsViewWidthPixel
        else:
            self._marginTopPixel = 0.02 * self._graphicsViewDepthPixel
            self._marginBottomPixel = 0.05 * self._graphicsViewDepthPixel
            self._marginLeftPixel = 0.05 * self._graphicsViewWidthPixel
            self._marginRightPixel = 0.02 * self._graphicsViewWidthPixel

    def _getPixel(self, event):
        xPixel = event.pos().x()
        yPixel = event.pos().y()
        intMapCoords = self.transformCoordPixelToMeter(xPixel, yPixel)
        print(f"Clicked position: {intMapCoords[0], intMapCoords[1]}")
        checkedUris = self._com.readDataBase("selectedCfsLinkUriList")
        if checkedUris is None:
            return
        for link_uri in checkedUris:
            self.pubUpdateSetPos.publish(link_uri, intMapCoords)

    ########### Transformations graphicsView ###########

    # -- Transform coordinates: Pixel [px] to Meter [m] --

    def transformCoordPixelToMeterDefaultSetting(self, xPixel, yPixel):
        xMeter = (self._mapWidthMeter / (self._graphicsViewWidthPixel-(self._marginLeftPixel+self._marginRightPixel))) * (xPixel-self._marginLeftPixel)
        # coordinate origin in an image is the top left corner
        # we need the coordinate origin to be in the bottom left corner
        yMeter = self._mapDepthMeter - ( (self._mapDepthMeter / (self._graphicsViewDepthPixel-(self._marginBottomPixel+self._marginTopPixel))) * (yPixel-self._marginTopPixel) )
        newPosition = [xMeter, yMeter]
        return newPosition

    def transformCoordPixelToMeterLaboratorySetting(self, xPixel, yPixel):
        # coordinate origin in an image is the top left corner
        # we need the coordinate origin to be in the top right corner
        xMeter = self._mapWidthMeter/2 - (self._mapWidthMeter / self._graphicsViewWidthPixel) * xPixel
        yMeter = ( self._mapDepthMeter / self._graphicsViewDepthPixel ) * yPixel - self._mapDepthMeter/2 
        # yMeter = (self._mapDepthMeter / (self._graphicsViewDepthPixel-(self._marginBottomPixel+self._marginTopPixel))) * (yPixel-self._marginTopPixel)
        newPosition = [xMeter, yMeter]
        return newPosition

    # -- Transform coordinates: Meter [m] to Pixel [px] --

    # Default setting

    def transformCoordMeterToPixelDefaultSetting(self, xMeter, yMeter):
        # coordinate origin in an image is the top left corner
        # we need the coordinate origin to be in the bottom left corner
        xPixel = self.transformXCoordMeterToPixelDefaultSetting(xMeter)
        yPixel = self.transformYCoordMeterToPixelDefaultSetting(yMeter)
        return [xPixel, yPixel]

    def transformXCoordMeterToPixelDefaultSetting(self, xMeter):
        xScaledPixel = ( (self._graphicsViewWidthPixel-(self._marginLeftPixel+self._marginRightPixel)) / self._mapWidthMeter ) * xMeter
        return xScaledPixel + self._marginLeftPixel

    def transformYCoordMeterToPixelDefaultSetting(self, yMeter):
        yScaledPixel = ( (self._graphicsViewDepthPixel-(self._marginBottomPixel+self._marginTopPixel)) / self._mapDepthMeter ) * yMeter
        return (self._graphicsViewDepthPixel - self._marginBottomPixel) - yScaledPixel

    # Laboratory setting

    def transformCoordMeterToPixelLabSetting(self, xMeter, yMeter):
        # coordinate origin in an image is the top left corner
        # we need the coordinate origin to be in the top right corner
        xPixel = self.transformXCoordMeterToPixelLabSetting(xMeter)
        yPixel = self.transformYCoordMeterToPixelLabSetting(yMeter)
        return [xPixel, yPixel]

    def transformXCoordMeterToPixelLabSetting(self, xMeter):
        return ( self._graphicsViewWidthPixel / 2 ) - ( ( self._graphicsViewWidthPixel / self._mapWidthMeter ) * xMeter )

    def transformYCoordMeterToPixelLabSetting(self, yMeter):
        return ( self._graphicsViewDepthPixel / 2 ) + ( ( self._graphicsViewDepthPixel / self._mapDepthMeter ) * yMeter )

    ########### GraphicsScene operations ###########

    def _addCfToScene(self, link_uri):
        self._addCfToSceneSignal.emit(link_uri)

    def _removeCfFromScene(self, link_uri):
        self._removeCfFromSceneSignal.emit(link_uri)

    def calcNewPosScene(self, newPosListMeter):
        # calculate x-pos and check for boundaries
        xPos = self.transformXCoordMeterToPixelScene(newPosListMeter[0])
        xPos -= self._cfPixmapRadiusPixel # subtract the radius of the displayed cycle
        if xPos <= 0:
            xPos = 0
        elif xPos >= (self._graphicsViewWidthPixel - 2*self._cfPixmapRadiusPixel):
            xPos = (self._graphicsViewWidthPixel - 2*self._cfPixmapRadiusPixel)
        # calculate y-pos and check for boundaries:
        yPos = self.transformYCoordMeterToPixelScene(newPosListMeter[1])
        yPos -= self._cfPixmapRadiusPixel
        if yPos >= (self._graphicsViewDepthPixel - 2*self._cfPixmapRadiusPixel):
            yPos = (self._graphicsViewDepthPixel - 2*self._cfPixmapRadiusPixel)
        elif yPos <= 0:
            yPos = 0
        return [xPos, yPos]

    def _updateCfPosScene(self, link_uri, newPosListMeter):
        newPosPixel = self.calcNewPosScene(newPosListMeter)
        self._intMapCfObjectsPosMeter[link_uri] = newPosListMeter
        self._updateSceneCurrentPos(link_uri, newPosPixel)

    def _updateCfSetPosMarkerScene(self, link_uri, newPosListMeter):
        newPosPixel = self.calcNewPosScene(newPosListMeter)
        self._intMapCfSetPosMarkerPosMeter[link_uri] = self.transformCoordPixelToMeter(newPosPixel[0], newPosPixel[1])
        self._updateSetPosMarkerSignal.emit(link_uri, newPosPixel)

    def _drawCfPathTail(self, link_uri, currentPosMeter):
        self._drawPathTailSignal.emit(link_uri, currentPosMeter)

    def removeDrawPathTail(self, link_uri):
        self._removeDrawPathTailSignal.emit(link_uri)

    ########## UI operations ##########

    def createIntMap(self):
        self.updateGraphicsViewGeometry()
        # create QGraphicsScene object
        self.graphicsSceneIntMap = QGraphicsScene()
        # connect the QGraphicsScene to the QGraphicsView object created in the designer
        self.setScene(self.graphicsSceneIntMap)
        self.rectangle = self.graphicsSceneIntMap.addRect(0, 0, self._graphicsViewWidthPixel, self._graphicsViewDepthPixel, QPen(Qt.black), QBrush(Qt.white))

        if self._currentSetting == "Laboratory":
            self._drawCoordinateSystemIntMapLabSetting()
            self._graphicsSceneMarginTopPixel = 0.05 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginBottomPixel = 0.02 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginLeftPixel = 0.02 * self._graphicsViewWidthPixel
            self._graphicsSceneMarginRightPixel = 0.05 * self._graphicsViewWidthPixel
        else:
            self._drawCoordinateSystemIntMapDefaultSetting()
            self._graphicsSceneMarginTopPixel = 0.02 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginBottomPixel = 0.05 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginLeftPixel = 0.05 * self._graphicsViewWidthPixel
            self._graphicsSceneMarginRightPixel = 0.02 * self._graphicsViewWidthPixel

        self._graphicsSceneWidthPixel = self._graphicsViewWidthPixel
        self._graphicsSceneDepthPixel = self._graphicsViewDepthPixel

    def _recreateIntMap(self):
        if self._currentSetting == "Laboratory":
            self._drawCoordinateSystemIntMapLabSetting()
            self._graphicsSceneMarginTopPixel = 0.05 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginBottomPixel = 0.02 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginLeftPixel = 0.02 * self._graphicsViewWidthPixel
            self._graphicsSceneMarginRightPixel = 0.05 * self._graphicsViewWidthPixel
        else:
            self._drawCoordinateSystemIntMapDefaultSetting()
            self._graphicsSceneMarginTopPixel = 0.02 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginBottomPixel = 0.05 * self._graphicsViewDepthPixel
            self._graphicsSceneMarginLeftPixel = 0.05 * self._graphicsViewWidthPixel
            self._graphicsSceneMarginRightPixel = 0.02 * self._graphicsViewWidthPixel
        self._graphicsSceneWidthPixel = self._graphicsViewWidthPixel
        self._graphicsSceneDepthPixel = self._graphicsViewDepthPixel

    def scaleIntMap(self):
        self._scaleIntMapSignal.emit()

    def _scaleIntMap(self):
        self.updateGraphicsViewGeometry()
        self.graphicsSceneIntMap.clear()
        self._recreateIntMap()
        self._repopulateScene()
        self._redrawPathTails()

    def _populateScene(self, link_uri, xPos=0, yPos=0, xSetPos=0, ySetPos=0):
        colorBrushList = [QBrush(Qt.green),
                          QBrush(Qt.blue),
                          QBrush(Qt.cyan),
                          QBrush(Qt.red),
                          QBrush(Qt.darkRed),
                          QBrush(Qt.magenta),
                          QBrush(Qt.darkGreen),
                          QBrush(Qt.gray)]
        pen = QPen(Qt.black)

        self._intMapCfObjects[link_uri] = self.graphicsSceneIntMap.addEllipse(xPos, yPos, 10, 10, pen, colorBrushList[int(link_uri[-1:])-1])
        # self._intMapCfObjects[link_uri].setFlag(QGraphicsItem.ItemIsSelectable)
        self._intMapCfObjectsPosMeter[link_uri] = self.transformCoordPixelToMeter(xPos, yPos)

        self._intMapCfSetPosMarker[link_uri] = self.graphicsSceneIntMap.addRect(xSetPos, ySetPos, 10, 10, pen, colorBrushList[int(link_uri[-1:])-1])
        self._intMapCfSetPosMarkerPosMeter[link_uri] = self.transformCoordPixelToMeter(xSetPos, ySetPos)

    def _repopulateScene(self):
        for link_uri in self._intMapCfObjects:
            curPosMeter = self._intMapCfObjectsPosMeter[link_uri]
            setPosMeter = self._intMapCfSetPosMarkerPosMeter[link_uri]
            curPosPixel = self.transformCoordMeterToPixelScene(curPosMeter[0], curPosMeter[1])
            setPosPixel = self.transformCoordMeterToPixelScene(setPosMeter[0], setPosMeter[1])
            self._populateScene(link_uri, curPosPixel[0], curPosPixel[1], setPosPixel[0], setPosPixel[1])

    def _drawCoordinateSystemIntMapDefaultSetting(self):
        # the QGraphicsView is self._graphicsViewWidthPixel x self._graphicsViewDepthPixel px
        # coordinates (0, 0) of the QGraphicsScene is in the top left corner
        pen = QPen(Qt.black)
        # x and y axis
        self.graphicsSceneIntMap.addLine(0+self._marginLeftPixel, self._graphicsViewDepthPixel, 0+self._marginLeftPixel, 0, pen)
        self.graphicsSceneIntMap.addLine(0, self._graphicsViewDepthPixel-self._marginBottomPixel, self._graphicsViewWidthPixel, self._graphicsViewDepthPixel-self._marginBottomPixel, pen)
        # scaled grid - vertical lines and text labels every meter
        for xStep in range(self._mapWidthMeter):
            y0 = self._graphicsViewDepthPixel - self._marginBottomPixel
            y1 = 0
            x = (xStep+1) * ((self._graphicsViewWidthPixel-self._marginLeftPixel-self._marginRightPixel) / self._mapWidthMeter) + self._marginLeftPixel
            self.graphicsSceneIntMap.addLine(x, y0, x, y1, pen)
            self.graphicsSceneIntMap.addSimpleText(str(xStep+1)+"m").setPos(x-10, y0)
        # scaled grid - horizontal lines and text labels every meter
        for yStep in range(self._mapDepthMeter):
            x0 = self._marginLeftPixel
            x1 = self._graphicsViewWidthPixel
            y = (self._graphicsViewDepthPixel - self._marginBottomPixel) - (yStep+1) * ((self._graphicsViewDepthPixel-self._marginBottomPixel-self._marginTopPixel) / self._mapDepthMeter)
            self.graphicsSceneIntMap.addLine(x0, y, x1, y, pen)
            self.graphicsSceneIntMap.addSimpleText(str(yStep+1)+"m").setPos(x0-20, y-10)

    def _drawCoordinateSystemIntMapLabSetting(self):
        # the QGraphicsView is self._graphicsViewWidthPixel x self._graphicsViewDepthPixel px
        # coordinates (0, 0) of the QGraphicsScene is in the top left corner
        # offsetPixel = 20
        pen = QPen(Qt.black)
        penAxis = QPen(Qt.black)
        penAxis.setWidth(3)

        # x and y axis
        self.graphicsSceneIntMap.addLine(0, self._graphicsViewDepthPixel/2, self._graphicsViewWidthPixel, self._graphicsViewDepthPixel/2, penAxis)
        self.graphicsSceneIntMap.addLine(self._graphicsViewWidthPixel/2, 0, self._graphicsViewWidthPixel/2, self._graphicsViewDepthPixel, penAxis)
        self.graphicsSceneIntMap.addSimpleText("0m").setPos(self._graphicsViewWidthPixel/2+5, self._graphicsViewDepthPixel/2)
        # scaled grid - vertical lines and text labels every meter
        # positive area
        for xStep in range(int(math.floor(self._mapWidthMeter/2))):
            y0 = 0
            y1 = self._graphicsViewDepthPixel
            x = self.transformXCoordMeterToPixelLabSetting(xStep+1)
            self.graphicsSceneIntMap.addLine(x, y0, x, y1, pen)
            self.graphicsSceneIntMap.addSimpleText(str(xStep+1)+"m").setPos(x+5, self._graphicsViewDepthPixel/2)
        # positive area
        for xStep in range(int(math.floor(self._mapWidthMeter/2))):
            xStepNegative = -xStep
            y0 = 0
            y1 = self._graphicsViewDepthPixel
            x = self.transformXCoordMeterToPixelLabSetting(xStepNegative-1)
            self.graphicsSceneIntMap.addLine(x, y0, x, y1, pen)
            self.graphicsSceneIntMap.addSimpleText(str(xStepNegative-1)+"m").setPos(x+5, self._graphicsViewDepthPixel/2)
        # scaled grid - horizontal lines and text labels every meter
        # positive area
        for yStep in range(int(math.floor(self._mapDepthMeter/2))):
            x0 = 0
            x1 = self._graphicsViewWidthPixel
            y = self.transformYCoordMeterToPixelLabSetting(yStep+1)
            self.graphicsSceneIntMap.addLine(x0, y, x1, y, pen)
            self.graphicsSceneIntMap.addSimpleText(str(yStep+1)+"m").setPos((self._graphicsViewWidthPixel/2)+5, y-20)
        # negative area
        for yStep in range(int(math.floor(self._mapDepthMeter/2))):
            yStepNegative = -1 * yStep
            x0 = 0
            x1 = self._graphicsViewWidthPixel
            y = self.transformYCoordMeterToPixelLabSetting(yStepNegative-1)
            self.graphicsSceneIntMap.addLine(x0, y, x1, y, pen)
            self.graphicsSceneIntMap.addSimpleText(str(yStepNegative-1)+"m").setPos((self._graphicsViewWidthPixel/2)+5, y+5)

    def _updateSceneCurrentPos(self, link_uri, pos):
        colorBrushList = [QBrush(Qt.green),
                          QBrush(Qt.blue),
                          QBrush(Qt.cyan),
                          QBrush(Qt.red),
                          QBrush(Qt.darkRed),
                          QBrush(Qt.magenta),
                          QBrush(Qt.darkGreen),
                          QBrush(Qt.gray)]
        pen = QPen(Qt.black)

        self.graphicsSceneIntMap.removeItem(self._intMapCfObjects[link_uri])
        self._intMapCfObjects[link_uri] = self.graphicsSceneIntMap.addEllipse(pos[0], pos[1], 10, 10, pen, colorBrushList[int(link_uri[-1:])-1])

    def _updateSceneSetPos(self, link_uri, pos):
        colorBrushList = [QBrush(Qt.green),
                          QBrush(Qt.blue),
                          QBrush(Qt.cyan),
                          QBrush(Qt.red),
                          QBrush(Qt.darkRed),
                          QBrush(Qt.magenta),
                          QBrush(Qt.darkGreen),
                          QBrush(Qt.gray)]
        pen = QPen(Qt.black)
        if link_uri in self._intMapCfSetPosMarker:
            self.graphicsSceneIntMap.removeItem(self._intMapCfSetPosMarker[link_uri])
            self._intMapCfSetPosMarker[link_uri] = self.graphicsSceneIntMap.addRect(pos[0], pos[1], 10, 10, pen, colorBrushList[int(link_uri[-1:])-1])
            self._intMapCfSetPosMarkerPosMeter[link_uri] = self.transformCoordPixelToMeter(pos[0], pos[1])
            # self._intMapCfSetPosMarker[link_uri].setPos(pos[0], pos[1])

    def _removeFromScene(self, link_uri):
        self.graphicsSceneIntMap.removeItem(self._intMapCfObjects[link_uri])
        self.graphicsSceneIntMap.removeItem(self._intMapCfSetPosMarker[link_uri])

#################### Draw path #############################

    # -- Path the crazyflie drags along --

    def _initDrawPathTail(self, link_uri):
        self._intMapCfPathTailsPixel[link_uri] = collections.deque(maxlen=50)
        self._intMapCfPathTailsMeter[link_uri] = collections.deque(maxlen=50)
        self._intMapCfPathTailObjects[link_uri] = collections.deque(maxlen=50)

    def _drawPathTail(self, link_uri, newPosMeter):
        pen = QPen(self._cfColors[link_uri])
        newPosPixel = self.transformCoordMeterToPixelScene(newPosMeter[0], newPosMeter[1])

        if link_uri not in self._intMapCfPathTailObjects:
            self._initDrawPathTail(link_uri)
            lastPosIndex = -1 # last item in the list
        else:
            lastPosIndex = -2 # second item from the end in the list

        self._intMapCfPathTailsMeter[link_uri].append(newPosMeter)
        # Remove the first item of the list from the scene if deque reaches max length
        if len(self._intMapCfPathTailObjects[link_uri]) >= self._intMapCfPathTailObjects[link_uri].maxlen:
            self.graphicsSceneIntMap.removeItem(self._intMapCfPathTailObjects[link_uri][0])

        self._intMapCfPathTailsPixel[link_uri].append(newPosPixel)
        lastPosPixel = self._intMapCfPathTailsPixel[link_uri][lastPosIndex]
        self._intMapCfPathTailObjects[link_uri].append(self.graphicsSceneIntMap.addLine(lastPosPixel[0], lastPosPixel[1], 
                                                                                        newPosPixel[0], newPosPixel[1], pen))

    def _redrawPathTails(self):
        self._intMapCfPathTailsMeterCopy = self._intMapCfPathTailsMeter.copy()
        self._intMapCfPathTailObjects.clear()
        self._intMapCfPathTailsPixel.clear()

        for link_uri, positionList in self._intMapCfPathTailsMeterCopy.items():
            for posMeter in positionList:
                self._drawPathTail(link_uri, posMeter)

    def _removeDrawPathTail(self, link_uri):
        for pathLine in self._intMapCfPathTailObjects[link_uri]:
            self.graphicsSceneIntMap.removeItem(pathLine)
        self._intMapCfPathTailsPixel[link_uri].clear()
        self._intMapCfPathTailsMeter[link_uri].clear()
        self._intMapCfPathTailObjects[link_uri].clear()
        del self._intMapCfPathTailObjects[link_uri]

#################### Draw Multi Ranger Point Cloud #############################

    def addPointToPointCloud(self, pointCoords, sensor):
        self._addPointToPointCloudSignal.emit(pointCoords, sensor)

    def _addPointToPointCloud(self, pointCoords, sensor):
        color = "red"
        if sensor == "front":
            color = "red"
        elif sensor == "back":
            color = "green"
        elif sensor == "right":
            color = "blue"
        elif sensor == "left":
            color = "magenta"

        pen = QPen(getattr(Qt, color))
        brush = QBrush(getattr(Qt, color))
        height = 4
        width = 4
        pixelCoords = self.transformCoordMeterToPixelScene(pointCoords[0], pointCoords[1])

        self._pointCloud.append(self.graphicsSceneIntMap.addEllipse(pixelCoords[0]-2,
                                                                    pixelCoords[1]-2,
                                                                    height,
                                                                    width,
                                                                    pen,
                                                                    brush))

    def clearPointCloud(self):
        self._clearPointCloudSignal.emit()

    def _clearPointCloud(self):
        for point in self._pointCloud:
            self.graphicsSceneIntMap.removeItem(point)
        self._pointCloud.clear()
