# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Publisher/Subscriber class for the multi-agent client
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

from threading import Lock
from copy import deepcopy

from PyQt5.QtCore import pyqtSignal, QObject


class Communicator(QObject):
    def __init__(self):
        super().__init__()
        # Dictionaries with subscriber and publisher objects
        self._pubDict = {}
        self._subDict = {}

        # The data base saves copies of the provided data
        self.dataMutex = Lock()
        self.dataBase = {}

    def publisher(self, topic, used=True):
        # Check if topic allready exists
        if topic not in self._pubDict:
            self._pubDict[topic] = _Publisher(topic, used)
            # print(f"Created publisher for topic {topic}")
            return self._pubDict[topic]
        elif self._pubDict[topic].used:
            return self._pubDict[topic]
        else:
            pub = self._pubDict[topic]
            pub.used = True
            return pub

    def subscriber(self, topic, callback):
        # A subscriber cannot exist on its own. If there is no
        # publisher, one has to be created, no matter if it
        # is going to be used or not.
        if topic not in self._pubDict:
            pub = self.publisher(topic, used=False)
        else:
            pub = self._pubDict[topic]
        
        sub = _Subscriber(topic, callback, pub)
        if topic not in self._subDict:
            self._subDict[topic] = [sub]
        else:
            self._subDict[topic].append(sub)
        # print(f"Created subscriber for topic {topic}")
        return sub

    def writeDataBase(self, topic, data):
        self.dataMutex.acquire()
        self.dataBase[topic] = deepcopy(data)
        self.dataMutex.release()

    def readDataBase(self, topic):
        self.dataMutex.acquire()
        if topic not in self.dataBase:
            data = None
        else:
            data = deepcopy(self.dataBase[topic])
        self.dataMutex.release()
        return data


class _Publisher(QObject):
    signal = pyqtSignal(object)
    def __init__(self, topic, used=False):
        super().__init__()
        self.topic = topic
        self.used = used

    def publish(self, *args):
        self.signal.emit(args)

    def connect(self, cb):
        self.signal.connect(cb)


class _Subscriber(QObject):
    def __init__(self, topic, callback, publisher):
        super().__init__()
        self.pub = publisher
        self.topic = topic
        self.callback = callback
        # Connect to the publisher
        self._subscribe()

    def _subscribe(self):
        self.pub.connect(self._callback)

    def _callback(self, argTuple):
        self.callback(*argTuple)
