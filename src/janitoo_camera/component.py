# -*- coding: utf-8 -*-
"""The compoennts

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

# Set default logging handler to avoid "No handler found" warnings.
import logging
logger = logging.getLogger(__name__)

import os
import time
import datetime
from onvif import ONVIFCamera

from janitoo.bus import JNTBus
from janitoo.value import JNTValue, value_config_poll
from janitoo.node import JNTNode
from janitoo.component import JNTComponent

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_NOTIFY = 0x3010

assert(COMMAND_DESC[COMMAND_NOTIFY] == 'COMMAND_NOTIFY')
##############################################################

from janitoo_camera import OID

def make_onvif(**kwargs):
    return OnvifComponent(**kwargs)

class CameraComponent(JNTComponent):
    """ A Camera component"""

    def __init__(self, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.generic'%OID)
        name = kwargs.pop('name', "Generic camera")
        product_name = kwargs.pop('product_name', "Generic camera")
        hearbeat = kwargs.pop('hearbeat', 900)
        bus = kwargs.pop('bus', None)
        JNTComponent.__init__(self, oid=oid, bus=bus, name=name, hearbeat=hearbeat,
                product_name=product_name, **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

    def check_heartbeat(self):
        """Check that the component is 'available'
        """
        return True

class NetworkCameraComponent(CameraComponent):
    """ A network Camera component"""

    def __init__(self, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.network'%OID)
        name = kwargs.pop('name', "Network camera")
        product_name = kwargs.pop('product_name', "Network camera")
        hearbeat = kwargs.pop('hearbeat', 900)
        default_user = kwargs.pop('default_user', "admin")
        default_passwd = kwargs.pop('default_passwd', "")
        default_port = kwargs.pop('default_port', 10080)
        CameraComponent.__init__(self, oid=oid, name=name, hearbeat=hearbeat,
                product_name=product_name, **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
        uuid="ip_ping"
        self.values[uuid] = self.value_factory['ip_ping'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='Ping the network camera',
            label='Ping',
            default='127.0.0.1'
        )
        config_value = self.values[uuid].create_config_value(help='The IP of the camera', label='IP',)
        self.values[config_value.uuid] = config_value
        poll_value = self.values[uuid].create_poll_value()
        self.values[poll_value.uuid] = poll_value
        uuid="user"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The user of your camera',
            label='User',
            default=default_user,
        )
        uuid="passwd"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The passwd of your camera',
            label='Pwd',
            default=default_passwd,
        )
        uuid="port"
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The port of your camera',
            label='Port',
            default=default_passwd,
        )

    def check_heartbeat(self):
        """Check that the component is 'available'

        """
        return self.values['ip_ping'].data

class OnvifComponent(NetworkCameraComponent):
    """ An Onvif camera component"""

    def __init__(self, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.onvif'%OID)
        name = kwargs.pop('name', "Onvif camera")
        product_name = kwargs.pop('product_name', "Onvif camera")
        NetworkCameraComponent.__init__(self, oid=oid, name=name,
                product_name=product_name, **kwargs)
        self.mycam = None
        #~ self.mycam = ONVIFCamera(self.values['ip_ping_config'].data, self.values['port'].data, self.values['user'].data, self.values['passwd'].data, wsdl_dir='/usr/local/wsdl/')

    #~ def check_heartbeat(self):
        #~ """Check that the component is 'available'
        #~ """
        #~ try:
            #~ req = request(self.values['url'].data)
            #~ response = urllib.urlopen(req)
            #~ the_page = response.read()
            #~ return True
        #~ except urllib.HTTPError as e:
            #~ if e.code == 400:
                #~ return True
            #~ else:
                #~ logger.exception('[%s] - Exception when checking heartbeat')
                #~ return False
        #~ except Exception:
            #~ logger.exception('[%s] - Exception when checking heartbeat')
            #~ return False
