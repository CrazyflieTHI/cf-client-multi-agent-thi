# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Collection of different and hopefully useful functions.
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

import sys
import json # statham
from threading import Lock
from datetime import datetime
import os.path


class FileReaderWriter:
    def __init__(self, filename, addDate=False):
        if addDate:
            self.now = datetime.now()
            self.date = self.now.strftime("_%d_%m_%Y_%H_%M_%S")
            self.index = filename.find('.')
            if self.index == -1:
                self.filename = filename + self.date
            else:
                self.filename = filename[:self.index] + self.date + filename[self.index:]
        else:
            self.filename = filename

    def write(self, data):
        with open(self.filename, 'w') as self.file:
            self.file.write(data)

    def append(self, data):
        with open(self.filename, 'a+') as self.file:
            self.file.write(data)

    def appendLine(self, data):
        """
        Appends the data with a new line ending.
        """
        with open(self.filename, 'a+') as self.file:
            self.file.write(str(data) + "\r\n")

    def appendList(self, dataList, trailing=" "):
        """
        Every element of the list is written in a separate
        column of the file. Columns are values separated
        by one space.
        """
        line = ""
        for item in dataList:
            line += str(item) + trailing
        line = line[:-1]
        self.appendLine(line)

    def read(self):
        """
        Reads the whole file and returns it as one string
        """
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            return self.file.read()

    def readLine(self):
        """
        Reads the first line of the file and returns it
        """
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            return self.file.readline()

    def readLines(self):
        """
        Reads the whole file and returns a list with
        all lines.
        """
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            return self.file.readlines()

    def readLinesList(self):
        """
        Reads the whole file and returns a 2D list with,
        where every item in a line is written to a list.
        """
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            dataList = []
            line = self.file.readline()
            oneLine = line.strip()
            columnsStrList = oneLine.split()
            length = len([float(i) for i in columnsStrList])
            # Init lists holding the columns
            columns = []
            for i in range(length):
              columns.append([])

            return self.file.readlines()

    def readColumnsList(self):
        ''' Every line is a list. All these lists are gathered in one
            big list.'''
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            columnsList = []
            for line in self.file:
                oneLine = line.strip()
                columnsStrList = oneLine.split()
                tempList = [float(i) for i in columnsStrList]
                columnsList.append(tempList)
            return columnsList

    def readExtractColumnsList(self, separator=" "):
        ''' Extract (log) data from a file
            params:
            separator -> str: Character that separates the columns

            return:
            length -> int: Number of columns extracted
            columns -> list: Columns as a nested list. Every column
                             is a list.
        '''
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            columnsList = []
            # Get the amount of columns in the file
            line = self.file.readline()
            oneLine = line.strip()
            columnsStrList = oneLine.split()
            length = len([i for i in columnsStrList])
            # Init lists holding the columns
            columns = []
            for i in range(length):
              columns.append([])
            # Extract the columns
            for line in self.file:
                oneLine = line.strip()
                columnsStrList = oneLine.split(separator)
                tempList = [float(i) for i in columnsStrList]
                for i in range(length):
                  columns[i].append(tempList[i])
            return length, columns

    def extractLogFile(self, separator=" "):
        ''' Extract (log) data from a file
            params:
            separator -> str: Character that separates the columns

            return:
            length -> int: Number of columns extracted
            columns -> list: Columns as a nested list. Every column
                             is a list.
            details -> list: First line of the log file holding, by
                             convention, the description of log data
        '''
        if not self._checkFileExists():
            return
        with open(self.filename, 'r') as self.file:
            columnsList = []
            # Get the amount of columns in the file
            line = self.file.readline()
            oneLine = line.strip()
            columnsStrList = oneLine.split()
            length = len([i for i in columnsStrList])
            # Init lists holding the columns
            details = columnsStrList
            columns = []
            for i in range(length):
              columns.append([])
            # Extract the columns
            for line in self.file:
                oneLine = line.strip()
                columnsStrList = oneLine.split(separator)
                tempList = [float(i) for i in columnsStrList]
                for i in range(length):
                  columns[i].append(tempList[i])
            return length, columns, details

    def _checkFileExists(self):
        if os.path.isfile(self.filename):
            return True
        else:
            print(f"File {self.filename} does not exist.")
            return False


class SafeCaller():
    """
    Based on the Caller class from Bitcraze.
    An object were callbacks can be registered and called.
    Access to the callback is protected by a semaphore.
    """
    def __init__(self):
        """ Create the object """
        self.callbacks = []
        self.lock = Lock()

    def add_callback(self, cb):
        """ Register cb as a new callback. Will not register duplicates. """

        with self.lock:
            if ((cb in self.callbacks) is False):
                    self.callbacks.append(cb)

    def remove_callback(self, cb):
        """ Un-register cb from the callbacks """
        with self.lock:
            self.callbacks.remove(cb)

    def call(self, *args):
        """ Call the callbacks registered with the arguments args """
        with self.lock:
            copy_of_callbacks = list(self.callbacks)
            for cb in copy_of_callbacks:
                cb(*args)

    def removeAllCallbacks(self):
        with self.lock:
            self.callbacks.clear()


class ConfigHandler():
    '''
    Handle a json configuration file

    params:
    jsonFileName -> str: Name of the configuration file in json format
    defaultConfigFileName -> str: Name of the default configuration file in
        json format. If the config file with name "jsonFileName"
        does not exist, it is created with the contents of the default
        config file. If defaultConfigFileName is not provided, no copy
        will be created.
    '''

    def __init__(self, jsonFileName, defaultConfigFileName=None):
        self.config = jsonFileName
        self.defaultConfig = defaultConfigFileName
        self.errorText = f"Error opening \"{jsonFileName}\" configuration file."

        if defaultConfigFileName is not None:
            if not os.path.exists(self.config):
                self.copyJsonFile(self.defaultConfig, self.config)

    def writeValue(self, category, entry, value):
        # First read the json file and modify the content
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                jsonCategory = data[category]
                jsonCategory[entry] = value
        except IOError:
            print(self.errorText)
            sys.exit(0)
        # Second, replace the json file with the modified content
        try:
            with open(self.config, "w") as write_file:
                json.dump(data, write_file, indent=4)
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def createSubCategoryValue(self, category, subCategory, entry, value):
        ''' Create a new subcategory with a specified entry and value within a category

        params:
        category -> str: Name of the category
        subCategory -> str: Name of the subcategory to create
        entry -> str: Name of the entry in the subcategory
        value -> any: Value to set for the entry
        '''
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                if category not in data:
                    data[category] = {}
                if subCategory not in data[category]:
                    data[category][subCategory] = {}
                data[category][subCategory][entry] = value

            with open(self.config, "w") as write_file:
                json.dump(data, write_file, indent=4)
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def deleteSubCategory(self, category, subCategory):
        ''' Delete a subcategory from the json file

        params:
        category -> str: Name of the category
        subCategory -> str: Name of the subcategory to be deleted
        '''
        # First read the json file and check if the subcategory exists
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                if category in data and subCategory in data[category]:
                    # Delete the subcategory
                    del data[category][subCategory]
                else:
                    print(f"Subcategory '{subCategory}' not found in category '{category}'")
                    return
        except IOError:
            print(self.errorText)
            sys.exit(0)

        # Second, replace the json file with the modified content
        try:
            with open(self.config, "w") as write_file:
                json.dump(data, write_file, indent=4)
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def writeCategoryValue(self, category, value):
        # First read the json file and modify the content
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                data[category] = value
        except IOError:
            print(self.errorText)
            sys.exit(0)
        # Second, replace the json file with the modified content
        try:
            with open(self.config, "w") as write_file:
                json.dump(data, write_file, indent=4)
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def writeSubCategoryValue(self, category, subCategory, entry, value):
        ''' Write a value into the subcategory of a json file

        params:
        category -> str: Name of the category
        subCategory -> str: Name of the nested category
        entry -> str: Name of the entry in the nested category
        '''
        # First read the json file and modify the content
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                jsonCategory = data[category]
                jsonSubCategory = jsonCategory[subCategory]
                jsonSubCategory[entry] = value
        except IOError:
            print(self.errorText)
            sys.exit(0)
        # Second, replace the json file with the modified content
        try:
            with open(self.config, "w") as write_file:
                json.dump(data, write_file, indent=4)
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def readValue(self, category, entry):
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                jsonCategory = data[category]
                return jsonCategory[entry]
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def readSubCategoryValue(self, category, subCategory, entry):
        """ Read an entry from a subcategory

        params:
        category -> str: Name of the category
        subCategory -> str: Name of the nested category
        entry -> str: Name of the entry in the nested category

        return: Return the object saved in the config file
        """
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                jsonCategory = data[category]
                jsonSubCategory = jsonCategory[subCategory]
                return jsonSubCategory[entry]
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def readCategory(self, category):
        try:
            with open(self.config, "r") as read_file:
                data = json.load(read_file)
                return data[category]
        except IOError:
            print(self.errorText)
            sys.exit(0)

    def copyJsonFile(self, src, dst):
        # Read src file
        try:
            with open(src, "r") as read_file:
                data = json.load(read_file)
        except IOError:
            print(self.errorText)
            sys.exit(0)
        # Write to dst file
        try:
            with open(dst, "w") as write_file:
                json.dump(data, write_file, indent=4)
        except IOError:
            print(self.errorText)
            sys.exit(0)

def uint16ToFloat(uint16Value, scaleFactor=(65535/0.499)):
    # Convert the uint16_t value to float
    floatValue = float(uint16Value)

    # Undo the scaling by dividing by the scale factor
    originalFloat = floatValue / scaleFactor

    return originalFloat
