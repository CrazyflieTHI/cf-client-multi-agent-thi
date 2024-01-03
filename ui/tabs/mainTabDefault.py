# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Main tab for default mode.
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
from PyQt5 import uic

from ui.tabs.mainTab import MainTab
from crazyflieControl import CrazyflieControl
from flightCommander import FlightCommander

root = os.path.dirname(os.path.realpath(__file__))
mainTabDefaultClass = uic.loadUiType(os.path.join(root,'main_tab_default.ui'))[0]


class MainTabDefault(MainTab, mainTabDefaultClass):
    def __init__(self, config, com, macp, swarm):
        super(MainTabDefault, self).__init__(config, com, macp, swarm)
        self.setupUi(self)

        self.cfControl = CrazyflieControl(config, com, macp, swarm)
        self.flightCommander = FlightCommander(config, com, macp, swarm)

        self.initTab()

    def initTab(self):
        self.initSelectButtons()
        self.initConnectButtons()
        self.initDisconnectButtons()
        self.initTakeoffButtons()
        self.initLandButtons()
        self.initFunctionBoxOneButtons()
        self.initFunctionBoxTwoButtons()

    def initFunctionBoxOneButtons(self):
        self.toolButtonConnectSelected.clicked.connect(lambda:
            self.cfControl.connectSelected(self.selectedCfsLinkUriList))
        self.toolButtonTakeoffSelected.clicked.connect(lambda:
            self.flightCommander.takeoffSelectedCf())
        self.toolButtonLandClientAll.clicked.connect(self.flightCommander.landAllCfBasestation)
        self.toolButtonDisconnectAll.clicked.connect(self.cfControl.disconnectAll)
        self.toolButtonPowerCycle.clicked.connect(self.cfControl.powerCycleCf)

    def initFunctionBoxTwoButtons(self):
        self.toolButtonShutdownSelected.clicked.connect(self.cfControl.shutdownSelectedCf)
        self.toolButtonShutdownSelected.setStyleSheet('background-color: red')
        self.toolButtonShutdownConnected.clicked.connect(self.cfControl.shutdownConnectedCf)
        self.toolButtonShutdownConnected.setStyleSheet('background-color: red')
