# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Essential functions for controlling the Crazyflies and the
#                 swarm.
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

import time
from threading import Thread
from copy import deepcopy

from cflib.crazyflie.log import LogConfig
from cflib.utils.power_switch import PowerSwitch
from PyQt5.QtCore import pyqtSignal, QObject

from dynamic import CachedCfFactory


class CrazyflieControl(QObject):

    # Used by the connecter threads
    connectedSignal = pyqtSignal(object)

    def __init__(self, config, com, macp, swarm):
        super().__init__()
        self._config = config
        self._com = com
        self._macp = macp
        self._swarm = swarm

        self.connectedCfs = []

        # Voltage threshold for landing the Crazyflie
        self.lowVoltageThreshold = 3.15
        self.lowBatteryVoltageUndercut = {}

        # SD card logging
        self.sdCardLogging = False

        # Factory object for cf creation
        self._factory = CachedCfFactory(rw_cache='./cache')

        self.connecterThreads = {}
        self.scannerThreads = {}

        self.connectedSignal.connect(self._cfConnectedThread)

        # Create publisher and subscriber
        self.pubConnected = self._com.publisher("cfControl/connected")
        self.pubDisconnected = self._com.publisher("cfControl/disconnected")
        self.pubPosition = self._com.publisher("cfControl/updatedPosition")
        self.pubBatteryVoltage = self._com.publisher("cfControl/updatedVoltage")
        self.pubConsole = self._com.publisher("cfControl/console")
        self.pubLowBattery = self._com.publisher("cfControl/lowBattery")

        self._com.subscriber("cfControl/connected", self._initLowBatteryVoltageUndercutDict)
        self._com.subscriber("cfControl/disconnected", self._disconnectCfCb)
        self._com.subscriber("cfControl/updatedVoltage", self.monitorBatteryVoltage)

    def getConnectedCfsList(self):
        return self.connectedCfs

    def connectSelected(self, linkUrisList):
        '''
        Try to connect to multiple Crazyflies

        params:
        linkUrisList -> list: Python list with the link_uris of the
                              Crazyflies to be connected
        '''
        for link_uri in linkUrisList:
            self.connectCrazyflie(link_uri)

    def connectCrazyflie(self, link_uri):
        '''
        Try to connect to a Crazyflie

        params:
        link_uri -> str: Radio identification of the Crazyflie
        '''
        if link_uri not in self.connecterThreads:
            print(f"Connecting to Crazyflie {link_uri}")
            self.connecterThreads[link_uri] = Thread(target=self._connectThreaded, args=(link_uri,))
            self.connecterThreads[link_uri].start()

    def _connectThreaded(self, link_uri):
        if not self._swarm.addCf(link_uri, factory=self._factory):
            return
        self._swarm.single(link_uri, self.registerCfCallbackFunctions)
        if self._swarm.open_link(link_uri):
            self._swarm.single(link_uri, self.registerLogData)
            self.connectedSignal.emit(link_uri)
        else:
            self._swarm.removeCf(link_uri)
            self.connecterThreads.pop(link_uri)
            print(f"Could not connect to Crazyflie {link_uri}")

    def deleteConnecterThreads(self):
        self.connecterThreads.clear()

    def _cfConnectedThread(self, link_uri):
        if link_uri not in self.connectedCfs:
            self.connectedCfs.append(link_uri)
        self.connecterThreads.pop(link_uri)
        self._com.writeDataBase("connectedCfsLinkUriList", self.connectedCfs)
        print(f"Crazyflie {link_uri[-2:]} operational.")

    def disconnectAll(self):
        connectedCfsCopy = deepcopy(self.connectedCfs)
        for link_uri in connectedCfsCopy:
            self.disconnectCf(link_uri)

    def disconnectCf(self, link_uri):
        if self._swarm == None:
            return
        self._swarm.close_link(link_uri)
        self._swarm.removeCf(link_uri)

    def _disconnectCfCb(self, link_uri):
        if link_uri in self.connectedCfs:
            self.connectedCfs.remove(link_uri)
            self._com.writeDataBase("connectedCfsLinkUriList", self.connectedCfs)

    ######### Logging #########

    # Gets called by the connecter thread just after opening the link to a crazyflie
    def registerLogData(self, scf):
        self._logBattery(scf)
        self._logCurrentPos(scf)
        while not scf.cf.param.is_updated:
            time.sleep(0.1)

    # -- battery voltage --

    def _logBattery(self, scf):
        logBatConf = LogConfig(name="batMonitoring", period_in_ms=500)
        logBatConf.add_variable('pm.vbat', 'float')
        try:
            scf.cf.log.add_config(logBatConf)
            logBatConf.data_received_cb.add_callback(lambda timestamp, data, logconf:
                                                     self.batteryStatusRefresh(scf.cf, timestamp, data, logconf))
            logBatConf.start()
        except KeyError as e:
            print("Could not start log configuration"
            "{} not found in TOC".format(str(e)))
        except AttributeError:
            print("Bad configuration!")

    def batteryStatusRefresh(self, cf, timestamp, data, logconf):
        self.pubBatteryVoltage.publish(cf.link_uri, data["pm.vbat"])

    # -- current position data --

    def _logCurrentPos(self, scf):
        logCurrentPos = LogConfig(name='positionMonitoring', period_in_ms=200)
        logCurrentPos.add_variable('stateEstimate.x', 'float')
        logCurrentPos.add_variable('stateEstimate.y', 'float')
        logCurrentPos.add_variable('stateEstimate.z', 'float')

        scf.cf.log.add_config(logCurrentPos)

        logCurrentPos.data_received_cb.add_callback(lambda timestamp, data, log_conf:
                                    self._updateCurrentCfPos(timestamp, data, log_conf, scf))
        logCurrentPos.start()

    def _updateCurrentCfPos(self, timestamp, data, log_conf, scf):
        link_uri = scf.cf.link_uri
        cfPos = [data['stateEstimate.x'], data['stateEstimate.y'], data['stateEstimate.z']] # timestamp]
        self.pubPosition.publish(link_uri, cfPos)

    ######### SD Card Logging #########

    def toggleLoggingSdCard(self):
        self._swarm.parallel(self.toggleLoggingParameter)

    def toggleLoggingParameter(self, scf):
        cf = scf.cf
        param = str(0x1)
        if self.sdCardLogging:
            param = str(0x0)
            self.sdCardLogging = False
        else:
            self.sdCardLogging = True
        print(f"Setting SD card param to {self.sdCardLogging}")
        cf.param.set_value('usd.logging', param)

    ########### Callback functions ###########

    # Gets called by the connecter thread before opening the link to a crazyflie
    def registerCfCallbackFunctions(self, scf):
        scf.cf.connected.add_callback(lambda link_uri: self._connected(link_uri, scf))
        scf.cf.add_port_callback(0x9, lambda crtpPacket: self._macp.distributeMacpPortCrtp(crtpPacket, scf.cf))
        scf.cf.console.receivedChar.add_callback(lambda text: self._receiveConsoleText(scf.cf.link_uri, text))
        scf.cf.disconnected.add_callback(lambda link_uri: self._disconnected(link_uri, scf))

    def _receiveConsoleText(self, link_uri, text):
        self.pubConsole.publish(link_uri, text)

    def _connected(self, link_uri, scf):
        self.pubConnected.publish(link_uri)

    def _disconnected(self, link_uri, scf):
        self.pubDisconnected.publish(link_uri)

    ########### Battery voltage monitoring ###########

    def _initLowBatteryVoltageUndercutDict(self, link_uri):
        self.lowBatteryVoltageUndercut[link_uri] = 0

    def monitorBatteryVoltage(self, link_uri, voltage):
        if voltage < self.lowVoltageThreshold:
            self.lowBatteryVoltageUndercut[link_uri] += 1
            if self.lowBatteryVoltageUndercut[link_uri] == 10:
                self.pubLowBattery.publish(link_uri)

    ########### Power-cycle and switch off ###########

    def shutdownSelectedCf(self):
        selectedCrazyflies = self._com.readDataBase("selectedCfsLinkUriList")
        if selectedCrazyflies is None:
            return
        for link_uri in selectedCrazyflies:
            try:
                PowerSwitch(link_uri).platform_power_down()
                print(f"Shutting down Crazyflie {link_uri[-2:]}")
            except:
                print(f"Could not shut down Crazyflie {link_uri[-2:]}")

    def shutdownConnectedCf(self):
        for link_uri in self.connectedCfs:
            try:
                PowerSwitch(link_uri).platform_power_down()
                print(f"Shutting down Crazyflie {link_uri[-2:]}")
            except:
                print(f"Could not shut down Crazyflie {link_uri[-2:]}")

    def powerCycleCf(self):
        selectedCrazyflies = self._com.readDataBase("selectedCfsLinkUriList")
        if selectedCrazyflies is None:
            return
        for link_uri in selectedCrazyflies:
            print(f"Power-cycling Crazyflie {link_uri[-2:]}")
            try:
                PowerSwitch(link_uri).stm_power_cycle()
            except:
                print(f"Could not power-cycle Crazyflie {link_uri}")

    def shutdown(self):
        # Disconnect all Crazyflies if connected
        self.disconnectAll()
        # End connecter threads if running
        self.deleteConnecterThreads()
