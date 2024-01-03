# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    The Multi Agent Communication Protocol (MACP) allows direct
#                 communication between agents in Bitcraze's centralistic
#                 network. It emulates a decentral network.
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

import struct
from threading import Thread
from queue import Queue, Empty

from macpTypes import *
from cflib.crtp.crtpstack import CRTPPacket


class MACPCommunication(object):
    def __init__(self, config, com, swarm):
        print("Hailing frequencies open.")
        self._config = config
        self._com = com
        self._swarm = swarm

        # Dictionary with callback functions
        # associated with a MACP message type
        self._macpPortCallbacks = {}
        self._macpPortLocalCallbacks = {}

        # Callbacks registered to peek inside routed packets,
        # which are send directly between Crazyflies
        self._macpPeekPortCallbacks = {}

        # Intermediate dictionary for keeping track of
        # Crazyflies connected to the basestation
        self.connectedNetworkCfs = {}
        self.connectedLocalCfs = {}

    def addPeekPortCallback(self, port, subPort, cb):
        ''' Add a callback function for grabbing data of a routed
            MACP packet between Crazyflies on the specified port
            and subPort. Does not work with local ports.

        :param port: Port of the MACP packet
        :param subPort: Sub port of the MACP packet
        :param cb: Callback function to be called when data arrives.
                   The function needs to take one parameter for
                   accepting the payload (the MACP packet) and one
                   for the Crazyflie object.
        '''
        # Check if the callback is already registered on the port
        if port in self._macpPeekPortCallbacks:
            if subPort in self._macpPeekPortCallbacks[port]:
                for key, currentCbList in self._macpPeekPortCallbacks[port].items():
                    # Do not register duplicates
                    if ((cb in currentCbList) is True):
                        return

        # If there are no callbacks on the port, initialize the port
        if port not in self._macpPeekPortCallbacks:
            self._macpPeekPortCallbacks[port] = {}

        if subPort not in self._macpPeekPortCallbacks[port]:
            self._macpPeekPortCallbacks[port][subPort] = []

        # Finally register the callback
        self._macpPeekPortCallbacks[port][subPort].append(cb)

    def addPortCallback(self, port, cb):
        ''' Add a callback function for receiving an MACP packet
            on the specified port.

        :param port: Port on which the MACP packet arrives
        :param cb: Callback function to be called when data arrives.
                   The function needs to take one parameter for
                   accepting the payload (the MACP packet) and one
                   for the Crazyflie object.
        '''
        # Check what kind of port is present (regular or local)
        if port >= 0x10:
            self._addPortLocalCallback(port, cb)
            return

        # Check if the callback is already registered on the port
        if port in self._macpPortCallbacks:
            for key, currentCbList in self._macpPortCallbacks.items():
                # Do not register duplicates
                if ((cb in currentCbList) is True):
                    return

        # If there are no callbacks on the port, initialize the port
        if port not in self._macpPortCallbacks:
            self._macpPortCallbacks[port] = []

        # Finally register the callback
        self._macpPortCallbacks[port].append(cb)

    def _addPortLocalCallback(self, port, cb):
        ''' Add a callback function for receiving an MACP packet
            on the specified local port. Local ports are used for
            receiving/transmitting data to Crazyflie applications
            running in separate python processes.
            Refer to LocalCrazyflie class for additional info.

        :param port: Port on which the MACP packet arrives
        :param cb: Callback function to be called when data arrives.
                   The function needs to take one parameter for
                   accepting the payload (the MACP packet) and one
                   for the LocalCrazyflie object.
        '''
        # Check if the callback is already registered on the port
        if port in self._macpPortLocalCallbacks:
            for key, currentCbList in self._macpPortLocalCallbacks.items():
                # Do not register duplicates
                if ((cb in currentCbList) is True):
                    return

        # If there are no callbacks on the port, initialize the port
        if port not in self._macpPortLocalCallbacks:
            self._macpPortLocalCallbacks[port] = []

        # Finally register the callback
        self._macpPortLocalCallbacks[port].append(cb)

    def removePortCallback(self, port, cb):
        # Check what kind of port is present (regular or local)
        if port >= 0x10:
            self._removePortLocalCallback(port, cb)
            return

        # Check if the callback is registered on the port
        if port not in self._macpPortCallbacks:
            return
        for key, currentCbList in self._macpPortCallbacks.items():
            if ((cb in currentCbList) is True):
                currentCbList.remove(cb)
                return

    def _removePortLocalCallback(self, port, cb):
        # Check if the callback is registered on the port
        if port not in self._macpPortLocalCallbacks:
            return
        for key, currentCbList in self._macpPortLocalCallbacks.items():
            if ((cb in currentCbList) is True):
                currentCbList.remove(cb)
                return

    def createCRTPPacket(self, port, channel, payload):
        if isinstance(payload, int):
            pk = CRTPPacket()
            pk.data = struct.pack('<I', payload)
        else:
            pk = CRTPPacket(data=payload)

        pk.set_header(port, channel)
        return pk

    def sendCRTP(self, channel, payload, cf, port=CRTP_PORT_MACP):
        crtpPacket = self.createCRTPPacket(port, channel, payload)
        cf.send_packet(crtpPacket)

    def _createMACPPacket(self, destinationId, senderId, macpPort, macpSubPort, payload):
        macpPacket = bytearray()

        # First 4 bits of the 1 Byte address header is the destination, other 4 bits sender
        addressHeader = ((senderId & 0x0F) << 4 |
                         (destinationId & 0x0F))

        macpPacketHeader = struct.pack('<BBB', addressHeader, macpPort, macpSubPort)

        macpPacket.extend(macpPacketHeader)
        macpPacket.extend(payload)
        return macpPacket

    def sendMACPPacketLinkUri(self, destinationId, senderId, macpPort, macpSubPort, payload, link_uri):
        '''
        Creates a MACP packet and sends it via crtp to a Crazyflie.
        All MACP packets get send over crtp port 0x9.

        params:
        destinationId -> int: Identification of the destination Crazyflie
        senderId -> int: Identification of the sending Crazyflie
        macpPort -> int: port of the MACP packet
        macpSubPort -> int: sub-port of the MACP packet
        payload -> bytearray: Data to be send
        link_uri -> str: Link URI of Crazyflie that is sending and therefore
                         receiving the packet. This is a bit strange and maybe should
                         be changed in the future.
        '''
        args = [destinationId, senderId, macpPort, macpSubPort, payload]

        if macpPort >= 0x10:
            self._swarm.singleLocal(link_uri, self._sendMACPPacketLocalLinkUri, args)
        else:
            self._swarm.single(link_uri, self._sendMACPPacketLinkUri, args)

    def _sendMACPPacketLocalLinkUri(self, lcf, destinationId, senderId, macpPort, macpSubPort, payload):
        macpPacket = self._createMACPPacket(destinationId, senderId, macpPort, macpSubPort, payload)
        lcf.sendPacket(macpPacket)

    def _sendMACPPacketLinkUri(self, scf, destinationId, senderId, macpPort, macpSubPort, payload):
        crtpPayload = self._createMACPPacket(destinationId, senderId, macpPort, macpSubPort, payload)
        self.sendCRTP(CRTP_DEFAULT_CHANNEL, crtpPayload, scf.cf)

    def sendMACPPacket(self, destinationId, senderId, macpPort, macpSubPort, payload, cf):
        '''
        Creates a MACP packet and sends it via crtp to a Crazyflie.
        All MACP packets get send over crtp port 0x9.

        params:
        destinationId -> int: Identification of the destination Crazyflie
        senderId -> int: Identification of the sending Crazyflie
        macpPort -> int: port of the MACP packet
        macpSubPort -> int: sub-port of the MACP packet
        payload -> bytearray: Data to be send
        cf -> Crazyflie: Crazyflie object that is sending the packet. This means the real
                         Crazyflie linked to the object will receive this packet.
        '''
        crtpPayload = self._createMACPPacket(destinationId, senderId, macpPort, macpSubPort, payload)
        self.sendCRTP(CRTP_DEFAULT_CHANNEL, crtpPayload, cf)

    def unpackMacpHeader(self, macpPacket):
        '''
        Unpack a MACP packet header.

        return:
        macpDstId -> int: Id of the destination Crazyflie
        macpSrcId -> int: Id of the sender Crazyflie
        macpPort -> int: Port the MACP packet was received on
        macpSubPort -> int: Sub port of the MACP packet
        macpPayload -> bytearray: Unpacked payload og the MACP packet
        '''
        _macpHeaderBytes = macpPacket[:3]
        macpPayload = macpPacket[3:]
        macpHeader = struct.unpack('BBB', _macpHeaderBytes)
        macpAddressHeader = macpHeader[0]
        macpDstId = (macpAddressHeader & 0x00F0) >> 4
        macpSrcId = macpAddressHeader & 0x000F
        macpPort = macpHeader[1]
        macpSubPort = macpHeader[2]
        return macpDstId, macpSrcId, macpPort, macpSubPort, macpPayload

    ## Pseudo Decentral Communication ##

    def distributeMacpPortCrtp(self, crtpPacket, cf):
        ''' Receive and distribute CRTP packets arriving on CRTP port 0x9
            based on the source and destination from the MACP header '''
        _channel = crtpPacket._channel
        _macpPacket = crtpPacket._data
        if _channel == CRTP_DEFAULT_CHANNEL:
            _macpHeaderBytes = _macpPacket[:3]
            macpHeader = struct.unpack('BBB', _macpHeaderBytes)
            macpAddressHeader = macpHeader[0]
            macpDstId = (_macpPacket[0] & 0x00F0) >> 4
            macpSrcId = _macpPacket[0] & 0x000F
            macpPort = macpHeader[1]
            macpSubPort = macpHeader[2]

        # Regular MACP ports
        if macpPort <= 0x10:
            if macpDstId == MACP_BROADCAST_ADDR:
                self._forwardBroadcastPacket(_macpPacket, macpSrcId)
            if (macpDstId == MACP_CLIENT_ADDR) or (macpDstId == MACP_BROADCAST_ADDR):
                self._handleMacpPacket(_macpPacket, macpPort, cf)
            # Forward the packet to an individual agent
            else:
                self._forwardPacketExclusive(_macpPacket, macpSrcId, macpDstId)
                # Since all packets get routed through the basestation we can peek
                # into the packets to get the data, e.g. for logging purposes
                self._peekPacketExclusive(_macpPacket, macpPort, macpSubPort, cf)

        # Local MACP ports
        # Info: Packets sent from a real Crazyflie to local port with source and destination
        # addresses being the same result in the packet being routed directly to the python
        # Crazyflie process
        # MACP_CLIENT_ADDR cannot be used with local ports.
        # MACP_BROADCAST_ADDR will not receive packets for same source and destination
        # addresses
        else:
            if macpDstId == MACP_BROADCAST_ADDR:
                self._forwardBroadcastPacketLocal(_macpPacket, macpSrcId)
            # Forward the packet to an individual agent
            else:
                self._forwardPacketExclusiveLocal(_macpPacket, macpSrcId, macpDstId)

    def _updateSwarmUris(self, scf):
        ''' Fill the self.connectedNetworkCfs dictionary with all connected cfs'''
        self.connectedNetworkCfs[scf.cf.link_uri] = [int(scf.cf.link_uri[-2:])]

    def _forwardBroadcastPacket(self, macpPacket, macpSrcId):
        ''' Sends a MACP packet to every connected Crazyflie'''
        cfsDict = {}
        self._swarm.parallel(self._updateSwarmUris)
        cfsDict = self.connectedNetworkCfs.copy()

        for link_uri in cfsDict:
            cfsDict[link_uri] = [macpPacket, macpSrcId]
        self._swarm.parallel(self._forwardPacket, cfsDict)

    def _forwardPacket(self, scf, macpPacket, macpSrcId):
        ''' Sends a MACP packet to a connected Crazyflie, except if
            the destination id is the same as the source id. This
            prevents Crazyflies from receiving the own broadcasted
            messages.
            Intended to be used with the "parallel" method of the
            Swarm class.
        '''
        if int(scf.cf.link_uri[-2:]) == macpSrcId:
            return
        self.sendCRTP(CRTP_DEFAULT_CHANNEL, macpPacket, scf.cf)

    def _forwardPacketExclusive(self, macpPacket, macpSrcId, macpDstId):
        cfsDict = {}
        self._swarm.parallel(self._updateSwarmUris)
        cfsDict = self.connectedNetworkCfs.copy()

        for link_uri in cfsDict:
            if int(link_uri[-2:]) == macpDstId:
                argsList = [macpPacket, macpSrcId, macpDstId]
                self._swarm.single(link_uri, self._sendPacketExclusive, argsList)
                return

    def _sendPacketExclusive(self, scf, macpPacket, macpSrcId, macpDstId):
        self.sendCRTP(CRTP_DEFAULT_CHANNEL, macpPacket, scf.cf)

    ## Packet handler for packets with destination basestation (also broadcast) ##

    def _handleMacpPacket(self, payload, macpPort, cf):
        if macpPort not in self._macpPortCallbacks:
            return
        copyOfCallbacks = list(self._macpPortCallbacks[macpPort])
        for cb in copyOfCallbacks:
            cb(payload, cf)

    ## Pseudo Decentral Communication for local Crazyflie processes ##

    def distributeMacpPortLocal(self, macpPacket, lcf):
        ''' Receive and distribute MACP packets arriving from the local
            python Crazyflie processes. Packets get distributed based
            on the source and destination IDs from the MACP header as well
            as the MACP port. Local MACP ports cause data to be routed to
            the Crazyflie processes whereas MACP packets with regular MACP
            ports are sent to the real Crazyflies.
        '''

        _macpHeaderBytes = macpPacket[:3]
        macpHeader = struct.unpack('BBB', _macpHeaderBytes)
        macpAddressHeader = macpHeader[0]
        macpDstId = (macpAddressHeader & 0x00F0) >> 4
        macpSrcId = macpAddressHeader & 0x000F
        macpPort = macpHeader[1]
        macpSubPort = macpHeader[2]

        # Regular MACP ports
        # Info: Packets from python Crazyflie processes can be send
        # to the client's main process only through local ports. 
        if macpPort <= 0x10:
            if macpDstId == MACP_BROADCAST_ADDR:
                self._forwardBroadcastPacket(macpPacket, macpSrcId)
            # Forward the packet to an individual agent
            else:
                self._forwardPacketExclusive(macpPacket, macpSrcId, macpDstId)
        # Local MACP ports
        else:
            if macpDstId == MACP_BROADCAST_ADDR:
                self._forwardBroadcastPacketLocal(macpPacket, macpSrcId)
            if (macpDstId == MACP_CLIENT_ADDR) or (macpDstId == MACP_BROADCAST_ADDR):
                self._handleMacpPacketLocal(macpPacket, macpPort, lcf)
            # Forward the packet to an individual agent
            else:
                self._forwardPacketExclusiveLocal(macpPacket, macpSrcId, macpDstId)

    def _updateSwarmUrisLocal(self, lcf):
        ''' Fill the self.connectedLocalCfs dictionary with all the IDs of
            the Crazyflies that have active separate Crazyflie processes running
        '''
        self.connectedLocalCfs[lcf.link_uri] = [int(lcf.link_uri[-2:])]

    def _forwardBroadcastPacketLocal(self, macpPacket, macpSrcId):
        ''' Sends a MACP packet to every connected Crazyflie process '''
        cfsDict = {}
        self._swarm.parallelLocal(self._updateSwarmUrisLocal)
        cfsDict = self.connectedLocalCfs.copy()

        for link_uri in cfsDict:
            cfsDict[link_uri] = [macpPacket, macpSrcId]
        self._swarm.parallelLocal(self._forwardPacketLocal, cfsDict)

    def _forwardPacketLocal(self, lcf, macpPacket, macpSrcId):
        ''' Sends a MACP packet to a connected Crazyflie process, 
            except if the destination id is the same as the source id.
            This prevents Crazyflies from receiving the own broadcasted
            messages.
            Intended to be used with the "parallelLocal" method of the
            Swarm class.
        '''
        if int(lcf.link_uri[-2:]) == macpSrcId:
            return
        lcf.sendPacket(macpPacket)

    def _forwardPacketExclusiveLocal(self, macpPacket, macpSrcId, macpDstId):
        cfsDict = {}
        self._swarm.parallel(self._updateSwarmUris)
        cfsDict = self.connectedNetworkCfs.copy()

        for link_uri in cfsDict:
            if int(link_uri[-2:]) == macpDstId:
                argsList = [macpPacket, macpSrcId, macpDstId]
                self._swarm.singleLocal(link_uri, self._sendPacketExclusiveLocal, argsList)
                return

    def _sendPacketExclusiveLocal(self, lcf, macpPacket, macpSrcId, macpDstId):
        lcf.sendPacket(macpPacket)

    ## Packet handler for packets with destination basestation (also broadcast) ##

    def _handleMacpPacketLocal(self, macpPacket, macpPort, lcf):
        if macpPort not in self._macpPortLocalCallbacks:
            return
        copyOfCallbacks = list(self._macpPortLocalCallbacks[macpPort])
        for cb in copyOfCallbacks:
            cb(macpPacket, lcf)

    ## Peek into packets routed between Crazyflies

    def _peekPacketExclusive(self, macpPacket, macpPort, macpSubPort, cf):
        if (macpPort not in self._macpPeekPortCallbacks):
            return
        if (macpSubPort not in self._macpPeekPortCallbacks[macpPort]):
            return

        callbacks = list(self._macpPeekPortCallbacks[macpPort][macpSubPort])
        for cb in callbacks:
            cb(macpPacket, cf)

class MACPRemote(object):
    def __init__(self):
        ''' MACP interface on the side of the Crazyflie process '''
        # Dictionary with callback functions
        # associated with a MACP message type
        self._macpPortLocalCallbacks = {}

        self.handleMacpPacketQueue = Queue()

        self.handlerThreadRun = True
        self.handlerThread = Thread(target=self._handleMacpPacket)
        self.handlerThread.start()

    def addPortCallback(self, port, cb):
        ''' Add a callback function for receiving an MACP packet
            on the specified port.

        params:
        port -> int: Port on which the MACP packet arrives
        cb -> function reference: Callback function to be called when data arrives.
                The function needs to take three parameters.
                srcId -> int: Id of the sender
                subPort -> int: Sub port of the MACP packet
                payload -> bytearray: Payload of the MACP packet
        '''
        # Check if the callback is already registered on the port
        if port in self._macpPortLocalCallbacks:
            for key, currentCbList in self._macpPortLocalCallbacks.items():
                # Do not register duplicates
                if ((cb in currentCbList) is True):
                    return

        # If there are no callbacks on the port, initialize the port
        if port not in self._macpPortLocalCallbacks:
            self._macpPortLocalCallbacks[port] = []

        # Finally register the callback
        self._macpPortLocalCallbacks[port].append(cb)

    def removePortCallback(self, port, cb):
        # Check if the callback is registered on the port
        if port not in self._macpPortLocalCallbacks:
            return
        for key, currentCbList in self._macpPortLocalCallbacks.items():
            if ((cb in currentCbList) is True):
                currentCbList.remove(cb)
                return

    def _removeAllPortCallbacks(self):
        self._macpPortLocalCallbacks.clear()

    def _createMACPPacket(self, destinationId, senderId, macpPort, macpSubPort, payload):
        macpPacket = bytearray()

        # First 4 bits of the 1 Byte address header is the destination, other 4 bits sender
        addressHeader = ((destinationId & 0x0F) << 4 |
                         (senderId & 0x0F))

        macpPacketHeader = struct.pack('<BBB', addressHeader, macpPort, macpSubPort)

        macpPacket.extend(macpPacketHeader)
        macpPacket.extend(payload)
        return macpPacket

    def sendMACPPacket(self, destinationId, senderId, macpPort, macpSubPort, payload, ipc):
        '''
        Create a MACP packet and send it to a Crazyflie or a Crazyflie process, depending
        on the provided macpPort (local vs normal).

        params:
        destinationId -> int: Identification of the destination Crazyflie
        senderId -> int: Identification of the sending Crazyflie
        macpPort -> int: port of the MACP packet
        macpSubPort -> int: sub-port of the MACP packet
        payload -> bytearray: Data to be send
        cf -> Crazyflie: Crazyflie object that is sending the packet
        '''
        macpPacket = self._createMACPPacket(destinationId, senderId, macpPort, macpSubPort, payload)
        ipc.send(LOCAL_PORT_MACP, macpPacket)

    def handleMacpPacket(self, macpPacket):
        ''' Handle incoming MACP packets from the InterProcessCommunicator and call the
            callback functions on the registered (local) MACP ports.

        params:
            macpPacket -> bytearray: MACP packet
        '''
        _macpHeaderBytes = macpPacket[:3]
        macpPayload = macpPacket[3:]
        macpHeader = struct.unpack('BBB', _macpHeaderBytes)
        macpAddressHeader = macpHeader[0]
        macpDstId = (macpAddressHeader & 0x00F0) >> 4
        macpSrcId = macpAddressHeader & 0x000F
        macpPort = macpHeader[1]
        macpSubPort = macpHeader[2]

        self.handleMacpPacketQueue.put([macpSrcId, macpPort, macpSubPort, macpPayload])

    def _handleMacpPacket(self):
        while self.handlerThreadRun:
            try:
                packetItems = self.handleMacpPacketQueue.get(block=True, timeout=0.05)

                def unpackList(macpSrcId, macpPort, macpSubPort, macpPayload):
                    return macpSrcId, macpPort, macpSubPort, macpPayload
                srcId, macpPort, subPort, payload = unpackList(*packetItems)

                if macpPort not in self._macpPortLocalCallbacks:
                    return
                copyOfCallbacks = list(self._macpPortLocalCallbacks[macpPort])
                for cb in copyOfCallbacks:
                    cb(srcId, subPort, payload)
            except Empty:
                pass
            except:
                raise

    def closeMacp(self):
        self._removeAllPortCallbacks()
        self.handlerThreadRun = False
        self.handlerThread.join()
