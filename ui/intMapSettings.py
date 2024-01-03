# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    Window for setting interactive map specs.
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

from PyQt5 import  uic
from PyQt5.QtWidgets import QDialog

root = os.path.dirname(os.path.realpath(__file__))
(intMapSettingsClass,
 intMapSettingsBaseClass) = (uic.loadUiType(os.path.join(root,'int_map_settings.ui')))


class IntMapSettings(QDialog, intMapSettingsClass):
    def __init__(self, config, com):
        super(IntMapSettings, self).__init__()
        self.setupUi(self)
        self.setWindowTitle("Interactive Map Settings")

        self.config = config
        self.com = com

        # Read the current config
        self.setting   = self.config.readValue("interactiveMap", "setting")
        self.mapHeight = self.config.readValue("interactiveMap", "depth")
        self.mapWidth  = self.config.readValue("interactiveMap", "width")

        # Set text for QLineEdit and select ComboBox
        self.lineEditIntMapSettingsHeight.setText(str(self.mapHeight))
        self.lineEditIntMapSettingsWidth.setText(str(self.mapWidth))
        if self.setting == self.checkBoxIntMapSettingsDefault.text():
            self.checkBoxIntMapSettingsDefault.setChecked(True)
            self.checkBoxIntMapSettingsLaboratory.setChecked(False)
        else:
            self.checkBoxIntMapSettingsLaboratory.setChecked(True)
            self.checkBoxIntMapSettingsDefault.setChecked(False)

        # Connect buttons and combo boxes
        self.toolButtonIntMapSettingsCancel.clicked.connect(self.close)
        self.toolButtonIntMapSettingsSave.clicked.connect(self.saveSettings)
        self.checkBoxIntMapSettingsDefault.toggled.connect(lambda:
             self.toggleMapSettingComboBoxes(self.checkBoxIntMapSettingsDefault))
        self.checkBoxIntMapSettingsLaboratory.toggled.connect(lambda:
             self.toggleMapSettingComboBoxes(self.checkBoxIntMapSettingsLaboratory))

    def toggleMapSettingComboBoxes(self, comboBox):
        if comboBox.text() == "Laboratory":
            if comboBox.isChecked() == True:
                self.checkBoxIntMapSettingsDefault.setChecked(False)
            else:
                self.checkBoxIntMapSettingsDefault.setChecked(True)     
        if comboBox.text() == "Default":
            if comboBox.isChecked() == True:
                self.checkBoxIntMapSettingsLaboratory.setChecked(False)
            else:
                self.checkBoxIntMapSettingsLaboratory.setChecked(True)   

    def saveSettings(self):
        newMapHeight = int(self.lineEditIntMapSettingsHeight.text())
        newMapWidth = int(self.lineEditIntMapSettingsWidth.text())
        if self.checkBoxIntMapSettingsLaboratory.isChecked():
            newIntMapSetting = self.checkBoxIntMapSettingsLaboratory.text()
        else:
            newIntMapSetting = self.checkBoxIntMapSettingsDefault.text()
        self.config.writeValue("interactiveMap", "setting", newIntMapSetting)
        self.config.writeValue("interactiveMap", "width", newMapWidth)
        self.config.writeValue("interactiveMap", "depth", newMapHeight)
        if (self.setting != newIntMapSetting) or (self.mapHeight != newMapHeight) or (self.mapWidth != newMapWidth):
            print("Changed Interactive Map Settings to:\n"
                f"Map Setting: {newIntMapSetting}\n"
                f"Map Width: {newMapWidth}\n"
                f"Map Height {newMapHeight}\n"
                "Please restart the UI for changes to take effect.")
        self.close()

    def closeEvent(self, event):
        event.accept()
