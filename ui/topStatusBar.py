# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Top status bar.
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
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal


root = os.path.dirname(os.path.realpath(__file__))
topStatusBarClass = uic.loadUiType(os.path.join(root,'top_status_bar.ui'))[0]

class TopStatusBar(QtWidgets.QWidget, topStatusBarClass):

    updateBatteryVoltageSignal = pyqtSignal(object, object)
    updateCurrentPosSignal     = pyqtSignal(str, object)
    updateSuccessfulScanSignal = pyqtSignal(str)
    updateConnectedCfSignal    = pyqtSignal(str)
    updateDisconnectedCfSignal = pyqtSignal(str)

    def __init__(self, com):
        super(TopStatusBar, self).__init__()
        self.setupUi(self)
        self.tabName = "topStatusBar"
        self._com = com

        # Create subscriber
        self._com.subscriber("cfControl/connected", self._changeStatusBgColorConnectedCb)
        self._com.subscriber("cfControl/disconnected", self._handleDisconnectCfCb)
        self._com.subscriber("cfControl/updatedPosition", self._updateLabelControlPosCb)
        self._com.subscriber("cfControl/updatedVoltage", self._updateLabelVBatCb)

        self.linkUriToIdStr = self._com.readDataBase("linkUriToIdStr")

        # Connect signals
        self.updateBatteryVoltageSignal.connect(self._updateLabelVBat)
        self.updateCurrentPosSignal.connect(self._updateLabelCurrentPos)
        self.updateConnectedCfSignal.connect(self._changeStatusBgColorConnected)
        self.updateDisconnectedCfSignal.connect(self._resetStatusLabel)

    def getTabName(self):
        return self.tabName

    def _changeStatusBgColor(self, link_uri, status):
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        statusFrameCfStr = "statusFrameCf" + crazyflieIdStr
        statusFrameCf = getattr(self, statusFrameCfStr)
        statusFrameCfSetStyleSheet = getattr(statusFrameCf, 'setStyleSheet')

        if status == 'connected':
            statusFrameCfSetStyleSheet('background-color: #7CFC00') # green
        elif status == 'ready':
            statusFrameCfSetStyleSheet('background-color: #0080ff') # blue
        else:
            statusFrameCfSetStyleSheet('') # default

    def _changeStatusBgColorConnectedCb(self, link_uri):
        self.updateConnectedCfSignal.emit(link_uri)

    def _changeStatusBgColorConnected(self, link_uri):
        self._changeStatusBgColor(link_uri, 'connected')

    def _handleDisconnectCfCb(self, link_uri):
        self.updateDisconnectedCfSignal.emit(link_uri)

    def _resetStatusLabel(self, link_uri):
        self._changeStatusBgColor(link_uri, 'disconnected')
        self._resetLabelVBat(link_uri)

    def _updateLabelVBatCb(self, link_uri, rawBatteryVoltage):
        self.updateBatteryVoltageSignal.emit(link_uri, rawBatteryVoltage)

    def _updateLabelVBat(self, link_uri, rawBatteryVoltage):
        batteryVoltage = format(rawBatteryVoltage, '.2f')
        # Update label showing current battery voltage
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        labelControlName = 'labelStatusVBatCf' + crazyflieIdStr
        functionPart1 = getattr(self, labelControlName)
        completeFunctionName = getattr(functionPart1, 'setText')

        # e.g. ui.labelStatusVBatCf1.setText("VBat: 3.95 V")
        completeFunctionName("VBat: " + str(batteryVoltage) +" V")

    def _resetLabelVBat(self, link_uri):
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        labelControlName = 'labelStatusVBatCf' + crazyflieIdStr
        functionPart1 = getattr(self, labelControlName)
        completeFunctionName = getattr(functionPart1, 'setText')

        # e.g. MainUI.labelStatusVBatCf1.setText("VBat: ")
        completeFunctionName("VBat: ")

    def _updateLabelControlPosCb(self, link_uri, posList):
        self.updateCurrentPosSignal.emit(link_uri, posList)

    def _updateLabelCurrentPos(self, link_uri, posList):
        axis = ["X", "Y", "Z"]
        index = 0
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        for newPos in posList:
            labelControlName = 'labelControl' +axis[index]+ 'PosCf' + crazyflieIdStr
            functionPart1 = getattr(self, labelControlName)
            completeFunctionName = getattr(functionPart1, 'setText')
            # e.g. ui.labelControlXSetPosCf1.setText(0.03)
            completeFunctionName("{:.2f}".format(newPos))
            index += 1
