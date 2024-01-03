# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Base class for the main tab.
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

from threading import Timer
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal


class MainTab(QtWidgets.QWidget):

    setToolButtonStatusFrameSignal = pyqtSignal(str, bool, object)
    setToolButtonStatusSignal = pyqtSignal(str, bool, str)
    setColorGroupBoxSignal = pyqtSignal(str, str, str)

    def __init__(self, config, com, macp, swarm):
        super(MainTab, self).__init__()
        self.tabName = "mainTab"
        self._config = config
        self._com = com
        self._macp = macp
        self._swarm = swarm

        self.linkUrisDict = self._com.readDataBase("linkUrisDict")
        self.linkUriToId = self._com.readDataBase("linkUriToId")
        self.linkUriToIdStr = self._com.readDataBase("linkUriToIdStr")
        self.idToLinkUri = self._com.readDataBase("idToLinkUri")

        self.uiTimer = {}
        self.selectedCfsLinkUriList = []
        self.selectedCfsAddressList = []

        # Connect signals that change the ui
        self.setToolButtonStatusSignal.connect(self._setToolButtonStatus)
        self.setToolButtonStatusFrameSignal.connect(self._setToolButtonStatusFrame)
        self.setColorGroupBoxSignal.connect(self._setColorFrame)

        # Create subscribers
        self._com.subscriber("cfControl/connected", self.updateUiConnected)
        self._com.subscriber("cfControl/disconnected", self.updateUiDisconnected)
        self._com.subscriber("flightCommander/startedFlying", self.updateUiTakeoff)
        self._com.subscriber("flightCommander/stoppedFlying", self.updateUiLand)

    def getTabName(self):
        return self.tabName

    def _setTimerResetColorFrame(self, link_uri, tabName ,timeIntervalSec):
        if link_uri in self.uiTimer:
            self.uiTimer[link_uri].cancel()
            self.uiTimer.pop(link_uri)
        self.uiTimer[link_uri] = Timer(timeIntervalSec, self._setColorFrame, (link_uri, tabName, ''))
        self.uiTimer[link_uri].start()

    def _cancelTimer(self, link_uri):
        if link_uri in self.uiTimer:
            self.uiTimer[link_uri].cancel()
            self.uiTimer.pop(link_uri)

    def _setColorFrame(self, link_uri, tabName, color):
        ''' 
        The group box naming convention is
        "frame" + "name of the tab" + "Cf" + "crazyflieIdStr"
        e.g. "frameControlCf01"
        '''
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        frameName = "frame" + tabName + 'Cf' + crazyflieIdStr
        frame = getattr(self, frameName)
        # e.g. self.frameControlCf01.setStyleSheet('background-color: #7CFC00')
        frameSetStyleSheet = getattr(frame, 'setStyleSheet')
        self._cancelTimer(link_uri)
        if (color == 'green'):
            frameSetStyleSheet('background-color: #7CFC00')
        elif (color == 'blue'):
            frameSetStyleSheet('background-color: #0080ff')
        elif (color == 'orange'):
            frameSetStyleSheet('background-color: #ffa500')
            self._setTimerResetColorFrame(link_uri, tabName, 10)
        elif (color == 'red'):
            frameSetStyleSheet('background-color: #FF2222')
            self._setTimerResetColorFrame(link_uri, tabName, 15)
        else:   # reset to default
            frameSetStyleSheet('')

    def _setToolButtonStatus(self, enabled, buttonFuncStr, addonStr):
        ''' 
        The buttons naming convention is
        "toolButton" + "specific function" + "All, Selected or None"
        e.g. "toolButtonLandClientAll" or "toolButtonTakeoffSelected"
        or "toolButtonFlyTrajectory"
        '''
        buttonName = "toolButton" +buttonFuncStr+ addonStr
        button = getattr(self, buttonName)
        buttonSetEnabled = getattr(button, 'setEnabled')
        # e.g. self.toolButtonTakeoffSelected.setEnabled(True)
        buttonSetEnabled(enabled)

    def _setToolButtonStatusFrame(self, link_uri, enabled, buttonFuncStr):
        ''' 
        The buttons naming convention is
        "button" + "specific function" + "Cf" + "crazyflieIdStr"
        e.g. "buttonConnectCf01" or "buttonLandCf08"
        '''
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        frameButtonName = "button" +buttonFuncStr+ "Cf" + crazyflieIdStr
        frameButton = getattr(self, frameButtonName)
        frameButtonSetEnabled = getattr(frameButton, 'setEnabled')
        # e.g. self.buttonConnectCf01.setEnabled(True)
        frameButtonSetEnabled(enabled)

    def setColorFrame(self, link_uri, tabName, color=None):
        ''' 
        Set a color for the group boxes of type QGroupBox in the
        main tab. For colors blue and orange a timer gets started
        that will reset the color to default on finish.

        params:
        link_uri -> str: Radio identification of the Crazyflie and
                         therefore its associated group box
        tabName -> str: Assigned name of the tab, see self.tabName,
                        containing the group box
        color -> str: One of four colors (green, blue, orange, red)
                      If no/wrong color is provided, the default
                      color is applied.
        '''
        self.setColorGroupBoxSignal.emit(link_uri, tabName, color)

    def setToolButtonStatus(self, enabled, buttonFuncStr, addonStr=None):
        ''' 
        Enable or disable a button of type QToolButton that is not part
        of a group box associated to one specific Crazyflie.

        params:
        enabled -> bool: Enable the button when True or disable when False
        buttonFuncStr -> str: Describing the specific function when
                              clicking on the button
        addonStr -> str: Addon at the end of the button name describing
                         which Crazyflies are targeted (Selected, All)
        '''
        self.setToolButtonStatusSignal.emit(enabled, buttonFuncStr, addonStr)

    def setToolButtonStatusFrame(self, link_uri, enabled, buttonFuncStr):
        ''' 
        Enable or disable a button of type QToolButton that is part
        of a group box associated to one specific Crazyflie.

        params:
        enabled -> bool: Enable the button when True or disable when False
        buttonFuncStr -> str: Describing the specific function when
                              clicking on the button
        link_uri -> str: link_uri of the Crazyflie associated to the frame
        '''
        self.setToolButtonStatusFrameSignal.emit(link_uri, enabled, buttonFuncStr)

    def _pushButtonChangedSelectCf(self, link_uri, pushButtonCf):
        crazyflieId = self.linkUriToId[link_uri]
        if pushButtonCf.isChecked() == True:
            self.selectedCfsLinkUriList.append(link_uri)
            self.selectedCfsAddressList.append(self.linkUrisDict[crazyflieId][1])
        else:
            self.selectedCfsLinkUriList.remove(link_uri)
            self.selectedCfsAddressList.remove(self.linkUrisDict[crazyflieId][1])
        self._com.writeDataBase("selectedCfsLinkUriList", self.selectedCfsLinkUriList)
        self._com.writeDataBase("selectedCfsAddressList", self.selectedCfsAddressList)

    def updateUiConnected(self, link_uri):
        self.setColorFrame(link_uri, 'Control', 'green')
        self.setToolButtonStatusFrame(link_uri, False, "Connect")
        self.setToolButtonStatusFrame(link_uri, True, "Disconnect")
        self.setToolButtonStatusFrame(link_uri, True, "Takeoff")

    def updateUiDisconnected(self, link_uri):
        self.setColorFrame(link_uri, 'Control', 'orange')
        self.setToolButtonStatusFrame(link_uri, True, "Connect")
        self.setToolButtonStatusFrame(link_uri, False, "Disconnect")
        self.setToolButtonStatusFrame(link_uri, False, "Takeoff")
        self.setToolButtonStatusFrame(link_uri, False, "Land")

    def updateUiConnectingError(self, link_uri):
        self.setColorFrame(link_uri, 'Control', 'red')
        self.setToolButtonStatusFrame(link_uri, True, "Connect")

    def updateUiTakeoff(self, link_uri):
        self.setToolButtonStatusFrame(link_uri, False, "Takeoff")
        self.setToolButtonStatusFrame(link_uri, True, "Land")

    def updateUiLand(self, link_uri):
        self.setToolButtonStatusFrame(link_uri, True, "Takeoff")
        self.setToolButtonStatusFrame(link_uri, False, "Land")

    def initSelectButtons(self):
        # Check boxes for selecting Crazyflies
        self.pushButtonSelectCf01.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[1][0], self.pushButtonSelectCf01))
        self.pushButtonSelectCf02.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[2][0], self.pushButtonSelectCf02))
        self.pushButtonSelectCf03.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[3][0], self.pushButtonSelectCf03))
        self.pushButtonSelectCf04.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[4][0], self.pushButtonSelectCf04))
        self.pushButtonSelectCf05.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[5][0], self.pushButtonSelectCf05))
        self.pushButtonSelectCf06.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[6][0], self.pushButtonSelectCf06))
        self.pushButtonSelectCf07.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[7][0], self.pushButtonSelectCf07))
        self.pushButtonSelectCf08.clicked.connect(lambda:
            self._pushButtonChangedSelectCf(self.linkUrisDict[8][0], self.pushButtonSelectCf08))

    def initConnectButtons(self):
        self.buttonConnectCf01.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[1][0]))
        self.buttonConnectCf02.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[2][0]))
        self.buttonConnectCf03.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[3][0]))
        self.buttonConnectCf04.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[4][0]))
        self.buttonConnectCf05.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[5][0]))
        self.buttonConnectCf06.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[6][0]))
        self.buttonConnectCf07.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[7][0]))
        self.buttonConnectCf08.clicked.connect(lambda:
            self.cfControl.connectCrazyflie(self.linkUrisDict[8][0]))

    def initDisconnectButtons(self):
        self.buttonDisconnectCf01.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[1][0]))
        self.buttonDisconnectCf02.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[2][0]))
        self.buttonDisconnectCf03.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[3][0]))
        self.buttonDisconnectCf04.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[4][0]))
        self.buttonDisconnectCf05.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[5][0]))
        self.buttonDisconnectCf06.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[6][0]))
        self.buttonDisconnectCf07.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[7][0]))
        self.buttonDisconnectCf08.clicked.connect(lambda:
            self.cfControl.disconnectCf(self.linkUrisDict[8][0]))

    def initTakeoffButtons(self):
        self.buttonTakeoffCf01.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[1][0]))
        self.buttonTakeoffCf02.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[2][0]))
        self.buttonTakeoffCf03.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[3][0]))
        self.buttonTakeoffCf04.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[4][0]))
        self.buttonTakeoffCf05.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[5][0]))
        self.buttonTakeoffCf06.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[6][0]))
        self.buttonTakeoffCf07.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[7][0]))
        self.buttonTakeoffCf08.clicked.connect(lambda:
            self.flightCommander.takeoffCf(self.linkUrisDict[8][0]))

    def initLandButtons(self):
        self.buttonLandCf01.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[1][0]))
        self.buttonLandCf02.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[2][0]))
        self.buttonLandCf03.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[3][0]))
        self.buttonLandCf04.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[4][0]))
        self.buttonLandCf05.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[5][0]))
        self.buttonLandCf06.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[6][0]))
        self.buttonLandCf07.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[7][0]))
        self.buttonLandCf08.clicked.connect(lambda:
            self.flightCommander.landCfBasestation(self.linkUrisDict[8][0]))

    def shutdownTab(self):
        self.cfControl.shutdown()
        for _link_uri, timer in self.uiTimer.items():
            timer.cancel()
