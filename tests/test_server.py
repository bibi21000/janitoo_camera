# -*- coding: utf-8 -*-

"""Unittests for Janitoo-Events Server.
"""
__license__ = """
    This file is part of Janitoo.

    Janitoo is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Janitoo is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Janitoo. If not, see <http://www.gnu.org/licenses/>.

"""
__author__ = 'Sébastien GALLET aka bibi21000'
__email__ = 'bibi21000@gmail.com'
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

import warnings
warnings.filterwarnings("ignore")

import sys, os
import time, datetime
import unittest
import threading
import logging
from pkg_resources import iter_entry_points

from janitoo_nosetests.server import JNTTServer, JNTTServerCommon
from janitoo_nosetests.thread import JNTTThread, JNTTThreadCommon

from janitoo.utils import json_dumps, json_loads
from janitoo.utils import HADD_SEP, HADD
from janitoo.utils import TOPIC_HEARTBEAT
from janitoo.utils import TOPIC_NODES, TOPIC_NODES_REPLY, TOPIC_NODES_REQUEST
from janitoo.utils import TOPIC_BROADCAST_REPLY, TOPIC_BROADCAST_REQUEST
from janitoo.utils import TOPIC_VALUES_USER, TOPIC_VALUES_CONFIG, TOPIC_VALUES_SYSTEM, TOPIC_VALUES_BASIC

from janitoo.server import JNTServer

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_NOTIFY = 0x3010
COMMAND_CAMERA_STREAM = 0x2203

assert(COMMAND_DESC[COMMAND_NOTIFY] == 'COMMAND_NOTIFY')
assert(COMMAND_DESC[COMMAND_CAMERA_STREAM] == 'COMMAND_CAMERA_STREAM')
##############################################################

class TestCameraSerser(JNTTServer, JNTTServerCommon):
    """Test the server
    """
    loglevel = logging.DEBUG
    path = '/tmp/janitoo_test'
    broker_user = 'toto'
    broker_password = 'toto'
    server_class = JNTServer
    server_conf = "tests/data/janitoo_camera.conf"
    hadds = [HADD%(34,0), HADD%(34,1), HADD%(34,2)]

    def test_040_server_start_no_error_in_log(self):
        JNTTServerCommon.test_040_server_start_no_error_in_log(self)
        self.assertDir("/tmp/janitoo_test/home/camera")

    def test_100_request_cap_init(self):
        self.skipCITest()
        self.start()
        try:
            self.assertHeartbeatNodes(hadds=[self.hadds[1], self.hadds[1]])
            time.sleep(1)
            self.assertNodeRequest(cmd_class=COMMAND_CAMERA_STREAM, is_writeonly=True, genre=0x02, uuid='actions', data="init", node_hadd=self.hadds[2], client_hadd=HADD%(9999,0), timeout=15)
            self.assertFile("/tmp/janitoo_test/home/camera/blank2.pgm")
            self.assertNodeRequest(cmd_class=COMMAND_CAMERA_STREAM, is_writeonly=True, genre=0x02, uuid='actions', data="init", node_hadd=self.hadds[1], client_hadd=HADD%(9999,0), timeout=15)
            self.assertFile("/tmp/janitoo_test/home/camera/blank.pgm")
        finally:
            self.stop()

