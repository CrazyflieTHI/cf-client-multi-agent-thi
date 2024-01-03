# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Inter-process communication. Two instances of the
#                 InterProcessCommunicator class, every one in a separate
#                 process, are used to establish port-based communication
#                 between those processes. Ports are defined by the user.
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

from queue import Queue, Empty
from threading import Thread
import struct


class InterProcessPacket:
    def __init__(self, port, payload):
        self.port = port
        self.payload = payload

    def getPort(self):
        return self.port

    def getPayload(self):
        return self.payload

    def getBytes(self):
        '''Requires payload to be already of type bytearray'''
        if(type(self.payload) != bytearray):
            print("ERROR InterProcessPacket: Payload needs to be of type bytearray.")
            return None
        packetBytes = bytearray()

        portBytes = struct.pack('<B', self.port)
        packetBytes.extend(portBytes)
        packetBytes.extend(self.payload)
        return packetBytes


class InterProcessCommunicator:
    '''
    Inter process communication. Uses the InterProcessPacket to
    send and receive data on user-defined ports.

    :param txQueue: multiprocessing.Queue for transmitting data
    :param rxQueue: multiprocessing.Queue for receiving data

    Remember, the txQueue of the first process is the rxQueue
    of the second process and vice versa.
    '''
    def __init__(self, txQueue, rxQueue):
        self.txQueue = txQueue
        self.rxQueue = rxQueue

        self.txThreadQueue = Queue()

        # The port is the key associated to a
        # list of registered callback functions
        self.portCallbacks = {}

        self.rxData = True
        self.rxThread = Thread(target = self._receiveIpcPacket)
        self.txData = True
        self.txThread = Thread(target=self._sendIpcPacket)
        self.rxThread.start()
        self.txThread.start()

    def _receiveIpcPacket(self):
        while(self.rxData):
            try:
                # Wait for a packet to arrive
                ipcPacket = self.rxQueue.get(block=True, timeout=0.05)
                port = ipcPacket.getPort()

                self._invokePortCallbacks(port, ipcPacket.getPayload())
            except:
                pass

    def addPortCallback(self, port, cb):
        ''' Add a callback function for receiving data on the specified port

        :param port: Port on which the InterProcessPacket arrives
        :param cb: Callback function to be called when data arrives.
                   The function needs to take one parameter for
                   accepting the payload.
        '''
        # Check if the callback is already registered on the port
        if port in self.portCallbacks:
            for key, currentCbList in self.portCallbacks.items():
                if ((cb in currentCbList) is True):
                    # Do not register duplicates
                    return

        # If there are no callbacks on the port, initialize the port
        if port not in self.portCallbacks:
            self.portCallbacks[port] = []

        # Finally register the callback
        self.portCallbacks[port].append(cb)

    def _invokePortCallbacks(self, port, payload):
        """ Call the registered callbacks """
        if port not in self.portCallbacks:
            return
        copyOfCallbacks = list(self.portCallbacks[port])
        for cb in copyOfCallbacks:
            cb(payload)

    def removePortCallback(self, port, cb):
        # Check if the callback is registered on the port
        if port not in self.portCallbacks:
            return
        for key, currentCbList in self.portCallbacks.items():
            if ((cb in currentCbList) is True):
                currentCbList.remove(cb)
                return

    def _removeAllPortCallbacks(self):
        self.portCallbacks.clear()

    def send(self, port, payload):
        ipcPacket = InterProcessPacket(port, payload)
        self.txThreadQueue.put(ipcPacket)

    def _sendIpcPacket(self):
        while(self.txData):
            try:
                ipcPacket = self.txThreadQueue.get(block=True, timeout=0.05)
                self.txQueue.put(ipcPacket, block=True)
            except Empty:
                pass
            except:
                raise

    def endCommunication(self):
        self._removeAllPortCallbacks()
        self.rxData = False
        self.txData = False
        self.rxThread.join()
        self.txThread.join()

class InterProcessCommunicatorPosix(InterProcessCommunicator):
    def __init__(self, txQueue, rxQueue):
        super().__init__(txQueue, rxQueue)

    def _receiveIpcPacket(self):
        while(self.rxData):
            try:
                # Wait for a packet to arrive
                ipcPacketBytes = self.rxQueue.receive(timeout=0.1)

                # ipcPacketPrio = ipcPacketBytes[1]
                # print(f"Packet prio: {ipcPacketPrio}")
                ipcPacketPort = struct.unpack('<B', ipcPacketBytes[0][:1])[0]
                # print(f"ipcPacketBytes: {ipcPacketBytes}")
                # print(f"crtpBytes: {ipcPacketBytes[0][1:]}")

                self._invokePortCallbacks(ipcPacketPort, ipcPacketBytes[0][1:])
            except:
                pass

    def _sendIpcPacket(self):
        while(self.txData):
            try:
                ipcPacket = self.txThreadQueue.get(block=True, timeout=0.1)
                tmpPacket = ipcPacket.getBytes()
                # print(f"Packet size: {len(tmpPacket)}")
                self.txQueue.send(ipcPacket.getBytes())
            except:
                pass
