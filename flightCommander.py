# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    The FlightCommander class holds functions for controlling
#                 the crazyflies in flight.
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
from threading import Thread, Timer
from PyQt5.QtCore import QObject
# https://stackoverflow.com/questions/4151320/efficient-circular-buffer
import collections # deque (ring-buffer)


class FlightCommander(QObject):
    def __init__(self, config, com, macp, swarm):
        super().__init__()
        print("All crews reporting.")

        self._config = config
        self._com = com
        self._macp = macp
        self._swarm = swarm

        self.setPositionDict    = {}
        self.currentCfPosDict   = {}
        self.cfYawAngleDict     = {}
        self.cfFlyingStatusDict = {}
        self.initialHeight      = 0.8
        self.initialSetPos      = [0.0, 0.0, self.initialHeight]

        self._com.writeDataBase("flightCommander/initHeight", self.initialHeight)

        # Create publisher and subscriber
        self.pubStartedFlying = self._com.publisher("flightCommander/startedFlying")
        self.pubStoppedFlying = self._com.publisher("flightCommander/stoppedFlying")
        self.pubUpdatedSetPos = self._com.publisher("flightCommander/updatedSetPos")
        self._com.subscriber("cfControl/connected", self._initCfPosDicts)
        self._com.subscriber("cfControl/updatedPosition", self.setCurrentCfPos)
        self._com.subscriber("cfControl/lowBattery", self.landCfBasestationLowBattery)
        self._com.subscriber("intMap/updatedSetPos", self.updateSetPosition)
        self._com.subscriber("main/keyUpdatedSetPos", self.updateSetPosDiff)
        self._com.subscriber("main/keyUpdatedSetYaw", self.updateSetYawDiff)

    def _initCfPosDicts(self, link_uri):
        """
        deque:  deque object is initialized left-to-right using append()
                Peek at leftmost item  [0]
                Peek at rightmost item [-1]
        """
        self.currentCfPosDict[link_uri] = collections.deque(maxlen=10)
        self.setPositionDict[link_uri] = self.initialSetPos.copy()
        self.cfYawAngleDict[link_uri] = 0.0
        self.cfFlyingStatusDict[link_uri] = False
        self._com.writeDataBase("flightCommander/flyingStatus", self.cfFlyingStatusDict)

    def updateSetPosDiff(self, link_uri, posDiff):
        if link_uri not in self.currentCfPosDict:
            return
        currentSetPos = self.setPositionDict[link_uri]
        newSetPos = []
        newSetPos.append(currentSetPos[0] + posDiff[0])
        newSetPos.append(currentSetPos[1] + posDiff[1])
        newSetPos.append(currentSetPos[2] + posDiff[2])
        self.updateSetPosition(link_uri, newSetPos)

    def updateSetYawDiff(self, link_uri, yawDiff):
        if link_uri not in self.cfYawAngleDict:
            return
        currentYaw = self.cfYawAngleDict[link_uri]
        newSetYaw = currentYaw + yawDiff
        self.setYawAngle(link_uri, newSetYaw)

    def setYawAngle(self, link_uri, yaw):
        if link_uri in self.cfYawAngleDict:
            self.cfYawAngleDict[link_uri] = yaw

    def setCurrentCfPos(self, link_uri, currentPos):
        self.currentCfPosDict[link_uri].append(currentPos)

        if link_uri in self.cfFlyingStatusDict:
            if self.cfFlyingStatusDict[link_uri] == True:
                return
        newSetPos = self._getCurrentCfPosDictList(link_uri)
        newSetPos[2] = self.initialSetPos[2]
        self.updateSetPosition(link_uri, newSetPos)

    def updateSetPosition(self, link_uri, newSetPos):
        if link_uri not in self.setPositionDict:
            print(f"Crazyflie {link_uri[-2:]} not connected.")
            return
        coordIndex = 0
        for newCoord in newSetPos:
            self.setPositionDict[link_uri][coordIndex] = newCoord
            coordIndex += 1
        self.pubUpdatedSetPos.publish(link_uri, self.setPositionDict[link_uri])

    def _getCurrentCfPosDictList(self, link_uri):
        if link_uri in self.currentCfPosDict:
            return list(self.currentCfPosDict[link_uri][-1])

    def getCfSetPosition(self, link_uri):
        if link_uri in self.setPositionDict:
            return self.setPositionDict[link_uri]

    def takeoffSelectedCf(self):
        for uri in self._com.readDataBase("selectedCfsLinkUriList"):
            self.takeoffCf(uri)

    def takeoffCf(self, uri):
        if uri in self.cfFlyingStatusDict:
            if self.cfFlyingStatusDict[uri] == True:
                return
        self._swarm.single(uri, self._sendTakeoffAndFlyThreaded)

    def _sendTakeoffAndFlyThreaded(self, scf):
        thread = Thread(target=self._sendTakeoffAndFly, args=[scf])
        thread.start()

    def _sendTakeoffAndFly(self, scf):
        print(f"Crazyflie {scf.cf.link_uri[-2:]} standing by.")
        self.cfFlyingStatusDict[scf.cf.link_uri] = True
        self._com.writeDataBase("flightCommander/flyingStatus", self.cfFlyingStatusDict)
        self._takeoffCf(scf.cf)
        self._flyCf(scf.cf)
        self.pubStartedFlying.publish(scf.cf.link_uri)

    def _takeoffCf(self, cf):
        link_uri = cf.link_uri
        takeoffFactor = 2.0
        sleepTime = 0.1
        speed_init = self.initialHeight / takeoffFactor
        speed = speed_init
        dt = 0.0
        Ix = 0.0
        Iy = 0.0
        Iz = 0.0
        Kp_x = 1.0
        Kp_y = Kp_x
        Kp_z = 2.0
        Ki_z = 0.25

        refPosZ = 0.1
        desired_height = self.initialHeight
        targetHeightNotReached = True

        # Calculate reference position
        refPosX = self.setPositionDict[link_uri][0]
        refPosY = self.setPositionDict[link_uri][1]

        while targetHeightNotReached:
            currentPos = self._getCurrentCfPosDictList(link_uri)
            speed = speed_init
            refPosZ = min(refPosZ + 0.1, desired_height)

            # Calculate deviation
            dx = refPosX - currentPos[0]
            dy = refPosY - currentPos[1]
            dz = refPosZ - currentPos[2]

            # Update integrator
            Ix += dx * dt
            Iy += dy * dt
            Iz += dz * dt

            # Compute controller output velocity
            outputSpeedX = Kp_x * dx
            outputSpeedY = Kp_y * dy
            outputSpeedZ = max(min(  speed + Kp_z * dz + Ki_z * Iz, speed ), -speed)

            # Send the velocity command to the Crazyflie (Yaw is 0)
            cf.commander.send_velocity_world_setpoint(outputSpeedX, outputSpeedY,
                                                      outputSpeedZ, 0)

            if dz < 0.1:
                targetHeightNotReached = False
            else:
                dt += sleepTime
                time.sleep(sleepTime)

        # Set the velocity to 0 after takeoff
        print(f"Crazyflie {link_uri[-2:]} reached target height.")
        cf.commander.send_velocity_world_setpoint(0, 0, 0, 0)

    def _flyCf(self, cf):
        cfYawAngleDict = self.cfYawAngleDict[cf.link_uri]
        cf.commander.send_position_setpoint(self.setPositionDict[cf.link_uri][0], self.setPositionDict[cf.link_uri][1],
                                            self.setPositionDict[cf.link_uri][2], cfYawAngleDict)
        # Keep the cf flying
        if self.cfFlyingStatusDict[cf.link_uri] == True:
            Timer(0.02, self._flyCf, [cf]).start()

    def landAllCfBasestation(self, uri):
        for uri in self.cfFlyingStatusDict:
                self.landCfBasestation(uri)

    def landCfBasestation(self, uri):
        if self.cfFlyingStatusDict[uri] == True:
            print(f"Crazyflie {uri[-2:]} Acknowledged H.Q.")
            self._swarm.single(uri, self._landBasestationControlledThreaded)

    def landCfBasestationLowBattery(self, uri):
        if self.cfFlyingStatusDict[uri] == True:
            print(f"Crazyflie {uri[-2:]} has low battery. Landing sequence initialized.")
            self._swarm.single(uri, self._landBasestationControlledThreaded)

    def _landBasestationControlledThreaded(self, scf):
        thread = Thread(target=self._landBasestationControlled, args=[scf])
        thread.start()

    def _landBasestationControlled(self, scf):
        landingTime   = 2.0
        sleepTime     = 0.1
        steps         = int(landingTime / sleepTime)
        self.cfFlyingStatusDict[scf.cf.link_uri] = False
        self._com.writeDataBase("flightCommander/flyingStatus", self.cfFlyingStatusDict)
        for _i in range(steps):
            velocityAxisZ = -self.currentCfPosDict[scf.cf.link_uri][-1][2] / landingTime
            scf.cf.commander.send_velocity_world_setpoint(0, 0, velocityAxisZ, 0)
            time.sleep(sleepTime)
        # Some additional landing time, so the cf doesn't plummet on the ground
        for _i in range(20):
            scf.cf.commander.send_velocity_world_setpoint(0, 0, velocityAxisZ, 0)
            time.sleep(0.1)

        scf.cf.commander.send_setpoint(0, 0, 0, 0)
        # Make sure that the last packet leaves before the link is closed
        # since the message queue is not flushed before closing
        time.sleep(0.5)
        self.pubStoppedFlying.publish(scf.cf.link_uri)

    # Use with caution! Flying crazyflies will fall down
    def _stopFly(self):
        for link_uri in self.cfFlyingStatusDict:
            self.cfFlyingStatusDict[link_uri] = False
        self._com.writeDataBase("flightCommander/flyingStatus", self.cfFlyingStatusDict)
