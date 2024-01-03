# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# This file is part of the Cooperative Control Laboratory's Crazyflie Project
# (C) 2024 Technische Hochschule Augsburg, Technische Hochschule Ingolstadt
# -----------------------------------------------------------------------------
#
# Author:         Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description:    MACP and CRTP ports for establishing a pseudo decentral
#                 communication network.
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

# Multi-agent communication protocol via CRTP
CRTP_PORT_MACP = 0x09
CRTP_DEFAULT_CHANNEL = 0x0

# Multi-agent communication protocol local between processes
LOCAL_PORT_MACP = 0x01

# Special addresses
MACP_BROADCAST_ADDR = 0xF
MACP_CLIENT_ADDR = 0x0

# MACP ports
MACP_PORT_RESERVED = 0x00
MACP_PORT_RESERVED = 0x01
MACP_PORT_RESERVED = 0x02
MACP_PORT_RESERVED = 0x03
MACP_PORT_RESERVED = 0x04
MACP_PORT_RESERVED = 0x05

# MACP remote ports
MACP_REMOTE_PORT_RESERVED = 0x10
MACP_REMOTE_PORT_RESERVED = 0x11
MACP_REMOTE_PORT_RESERVED = 0x12
MACP_REMOTE_PORT_RESERVED = 0x13
MACP_REMOTE_PORT_RESERVED = 0x14
MACP_REMOTE_PORT_RESERVED = 0x15
