# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Main file for the THA/THI base station.
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
import inspect
import importlib.util

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal

from cflib import crtp

import ui
import ui.tabs
from communicator import Communicator
from dynamic import Swarm
from macp import MACPCommunication
from ui.topStatusBar import TopStatusBar
from ui.intMapSettings import IntMapSettings
from interactiveMap import InteractiveMap
from utilities import ConfigHandler

root = os.path.dirname(os.path.realpath(__file__))
(main_window_class,
 main_windows_base_class) = (uic.loadUiType(os.path.join(root,'crazyflie_client_multi_agent.ui')))


class MainUI(QtWidgets.QMainWindow, main_window_class):

    printTextConsoleSignal = pyqtSignal(str, str)
    keypressSpaceSignal = pyqtSignal()
    keypressReturnSignal = pyqtSignal()

    def __init__(self):
        super(MainUI, self).__init__()
        self.setupUi(self)

        # Read json config file
        self._config = ConfigHandler("config/bs_config.json", "config/default_bs_config.json")

        # Read the link_uris and the addresses for the Crazyflies from the config file.
        # The link_uri is the identifier containing
        # - Radio number (starting with 0. Allowing use of multiple radios)
        # - Radio channel (80, 90, ...)
        # - Address of the Crazyflie (0xE7E7E7E7XX, e.g. 0xE7E7E7E701)
        # link_uri example: "radio://0/80/2M/E7E7E7E701"
        # This client defines the crazyflieId as an identifier used to associate
        # the right buttons to the Crazyflie's link_uri. Ids start at "01" and go up
        # to "08", the current maximum of connected Crazyflies
        # self.linkUrisDict: {crazyflieId -> int: [link_uri -> str, crazyflieAddress -> int]}
        # self.linkUriToId: {link_uri -> str: crazyflieId -> int}
        # self.idToLinkUri: {crazyflieId -> int: link_uri -> str}
        self.linkUrisDict = {}
        self.linkUrisDictStr = {}
        self.linkUriToId = {}
        self.linkUriToIdStr = {}
        self.idToLinkUri = {}
        self.idStrToLinkUri = {}
        linkUrisConfig = self._config.readCategory("crazyflies")
        id = 1
        for link_uri, address in linkUrisConfig.items():
            self.linkUrisDict[id] = [link_uri, address]
            self.linkUrisDictStr[f"{id:02}"] = [link_uri, address]
            self.linkUriToId[link_uri] = id
            self.linkUriToIdStr[link_uri] = f"{id:02}"
            self.idToLinkUri[id] = link_uri
            self.idStrToLinkUri[f"{id:02}"] = link_uri
            id += 1

        self._intMapSetting = self._config.readValue("interactiveMap", "setting")

        # Get the operation mode from the config file
        operationMode = self._config.readValue("main", "mode")
        self.simulationActive = self._config.readValue("main", "simulation")

        # Load crtp drivers dependent on simulation is active or not
        if self.simulationActive == "True":
            enableSimDriver = True
        else:
            enableSimDriver = False

        # If the running operating system is Windows,
        # the ROS Gazebo simulation cannot be used
        if (os.name == 'nt') and (self.simulationActive):
            self.simulationActive = False
            self._selectOperationModeDefault(printInfo=False)
            print("\nThe ROS Gazebo simulation is not available on Windows")
            print("Turned simulation off.\n")

        parameters = inspect.signature(crtp.init_drivers).parameters
        if 'enable_sim_driver' not in parameters or "enable_cpp_driver" not in parameters:
            print("ERROR: The cflib version seems to be not correct."
                  "Make sure to install cflib from the THI crazyflie-lib-python repository")
            exit()

        useLinkCpp = False
        if not enableSimDriver:
            if importlib.util.find_spec("cflinkcpp") is None:
                print("WARNING: The C++ radio link driver cflinkcpp is not installed. "
                      "Using the standard python radio link driver (with higher latencies)")
            else:
                useLinkCpp = True

        try:
            crtp.init_drivers(enable_sim_driver=enableSimDriver, enable_cpp_driver=useLinkCpp)
        except TypeError as e:
            print(f"ERROR: {e}")
            exit()

        self._com = Communicator()
        self._swarm = Swarm()
        self._macp = MACPCommunication(self._config, self._com, self._swarm)

        # Write the Crazyflie mapping to the data base
        self._com.writeDataBase("linkUrisDict", self.linkUrisDict)
        self._com.writeDataBase("linkUrisDictStr", self.linkUrisDictStr)
        self._com.writeDataBase("linkUriToId", self.linkUriToId)
        self._com.writeDataBase("linkUriToIdStr", self.linkUriToIdStr)
        self._com.writeDataBase("idToLinkUri", self.idToLinkUri)
        self._com.writeDataBase("idStrToLinkUri", self.idStrToLinkUri)

        # Main tab is mandatory and depends on operation mode
        self.mainTab = ui.tabs.mainTabDict[operationMode](self._config, self._com, self._macp, self._swarm)
        self.tabWidgetMain.addTab(self.mainTab, self.mainTab.getTabName())

        # Add Interactive Map settings window
        self.intMapSettingsWindow = IntMapSettings(self._config, self._com)

        # Add the top status bar to the ui and set appropriate label text
        self.topStatusBar = TopStatusBar(self._com)
        self.topLeftHorizontalLayout.insertWidget(0, self.topStatusBar)
        for mode, heading in ui.tabs.operationModeHeadings.items():
            if mode == operationMode:
                self.topStatusBar.labelOperationMode.setText(heading)

        # Add the interactive map to the ui
        self.intMap = InteractiveMap(self._config, self._com)
        self.middleLeftMiddleVerticalLayout.insertWidget(0, self.intMap)

        # Add standard tabs to QTabWidget
        self.standardTabInstances = []
        for tabClass in ui.tabs.standardTabList:
            tabInstance = tabClass(self._config, self._com, self._macp, self._swarm)
            self.standardTabInstances.append(tabInstance)
            tabName = tabInstance.getTabName()
            self.tabWidgetMain.addTab(tabInstance, tabName)

        # Add additional, operation-mode specific tabs
        self.specificTabInstances = []
        for opMode, tabClassList in ui.tabs.specificTabDict.items():
            if opMode == operationMode:
                for tabClass in tabClassList:
                    tabInstance = tabClass(self._config, self._com, self._macp, self._swarm)
                    tabName = tabInstance.getTabName()
                    self.specificTabInstances.append(tabInstance)
                    self.tabWidgetMain.addTab(tabInstance, tabName)

        # Init the menu bar
        self._initSettingsBar()
        self._initSimulationBar()

        # Init the debug console
        self._initConsoles()
        self._com.subscriber("cfControl/console", self._printTextConsoleCb)
        self.printTextConsoleSignal.connect(self._printTextConsole)

        # Publish controlling pose with keys
        self.pubUpdatedSetPos = self._com.publisher("main/keyUpdatedSetPos")
        self.pubUpdatedSetYaw = self._com.publisher("main/keyUpdatedSetYaw")

    def createIntMap(self):
        self.intMap.createIntMap()

    def _initSimulationBar(self):
        if self.simulationActive == "True":
            self.actionSimulationToggle.setText("Deactivate Simulation")
            self.topStatusBar.labelOperationModeSim.setText("Simulation Active")
        else:
            self.actionSimulationToggle.setText("Activate Simulation")
            self.topStatusBar.labelOperationModeSim.setText("Regular (Simulation not Active)")
        self.actionSimulationToggle.triggered.connect(self._safeSimulationSetting)

    def _safeSimulationSetting(self):
        if self.simulationActive == "True":
            newValue = "False"
        else:
            newValue = "True"
        self._config.writeValue("main", "simulation", newValue)
        print(f"Changed \"Simulation Active\" to \"{newValue}\".")
        print("Please restart the GUI.")

    def _initSettingsBar(self):
        self.actionSettingsInteractiveMap.triggered.connect(self._openIntMapSettings)
        self.actionSettingsOpModeDefault.triggered.connect(self._selectOperationModeDefault)

    def _selectOperationModeDefault(self, printInfo=True):
        self._config.writeValue("main", "mode", "default")
        if printInfo:
            print("Changed operation mode to \"Default\".")
            print("Please restart the GUI.")

    def _openIntMapSettings(self):
        self.intMapSettingsWindow.show()

    def _initConsoles(self):
        self.toolButtonClearDebugConsole.clicked.connect(self._clearConsoles)

    def _printTextConsoleCb(self, link_uri, text):
        self.printTextConsoleSignal.emit(link_uri, text)

    # TODO Maybe add automatic buffer reset or something to prevent buffer overflow
    # https://stackoverflow._com/questions/19912824/pyqt-depth-of-qtextedit-buffer
    def _printTextConsole(self, link_uri, text):
        crazyflieIdStr = self.linkUriToIdStr[link_uri]
        textBrowserName = 'textBrowserDebug' + crazyflieIdStr
        textBrowserDebugX = getattr(self, textBrowserName)
        textBrowserDebugX.insertPlainText(text)
        textBrowserDebugX.ensureCursorVisible()

    def _clearConsoles(self):
        for crazyflieId in range(1, 8):
            textBrowserName = 'textBrowserDebug' + f"{crazyflieId:02}"
            textBrowserDebugX = getattr(self, textBrowserName)
            textBrowserDebugX.clear()

    ########## Key press events ##########

    def keyPressEvent(self, event):
        for link_uri in self._com.readDataBase("selectedCfsLinkUriList"):
            posDiff = [0.0, 0.0, 0.0]
            yawDiff = 0.0
            if self._intMapSetting == "Laboratory":
                if event.key() == QtCore.Qt.Key_8:
                    posDiff[1] -= 0.1
                if event.key() == QtCore.Qt.Key_5:
                    posDiff[1] += 0.1
                if event.key() == QtCore.Qt.Key_6:
                    posDiff[0] -= 0.1
                if event.key() == QtCore.Qt.Key_4:
                    posDiff[0] += 0.1
            else:
                if event.key() == QtCore.Qt.Key_8:
                    posDiff[1] += 0.1
                if event.key() == QtCore.Qt.Key_5:
                    posDiff[1] -= 0.1
                if event.key() == QtCore.Qt.Key_4:
                    posDiff[0] -= 0.1
                if event.key() == QtCore.Qt.Key_6:
                    posDiff[0] += 0.1
            if event.key() == QtCore.Qt.Key_A:
                yawDiff -= 15
            if event.key() == QtCore.Qt.Key_D:
                yawDiff += 15
            if event.key() == QtCore.Qt.Key_W:
                posDiff[2] += 0.1
            if event.key() == QtCore.Qt.Key_S:
                posDiff[2] -= 0.1
            self.pubUpdatedSetPos.publish(link_uri, posDiff)
            self.pubUpdatedSetYaw.publish(link_uri, yawDiff)

    def eventFilter(self, obj, event):
        if (event.type() == QtCore.QEvent.Resize):
            self.intMap.scaleIntMap()
        return super().eventFilter(obj, event)

    ########## Close main window ##########

    def closeEvent(self, event):
        """
        Clean up when closing the window.
        """
        for tab in self.standardTabInstances:
            tab.shutdownTab()
        for tab in self.specificTabInstances:
            tab.shutdownTab()
        self.mainTab.shutdownTab()
        print("I really have to go, Number One.")
        event.accept()
