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
import threading

import onvif
import imutils
import cv2

from janitoo.bus import JNTBus
from janitoo.value import JNTValue, value_config_poll
from janitoo.node import JNTNode
from janitoo.component import JNTComponent

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_NOTIFY = 0x3010
COMMAND_CAMERA_STREAM = 0x2203

assert(COMMAND_DESC[COMMAND_NOTIFY] == 'COMMAND_NOTIFY')
assert(COMMAND_DESC[COMMAND_CAMERA_STREAM] == 'COMMAND_CAMERA_STREAM')
##############################################################

from janitoo_camera import OID

def make_onvif(**kwargs):
    return OnvifComponent(**kwargs)

def make_ipc(**kwargs):
    return IpcComponent(**kwargs)

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
        default_blank_image = kwargs.pop('default_blank_image', "blank.pgm")
        default_occupied_video = kwargs.pop('default_occupied_video', "occupied.avi")
        default_codec_video = kwargs.pop('default_codec_video', "XVID")
        default_contour_min = kwargs.pop('default_contour_min', 700)
        JNTComponent.__init__(self, oid=oid, bus=bus, name=name, hearbeat=hearbeat,
                product_name=product_name, **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
        uuid="blank_image"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The blank image',
            label='Blk img',
            default=default_blank_image,
        )
        uuid="occupied_video"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The result video',
            label='Video',
            default=default_occupied_video,
        )
        uuid="codec_video"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The codec video',
            label='codec',
            default=default_codec_video,
        )
        uuid="contour_min"
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The minimal contour length',
            label='contour',
            default=default_contour_min,
        )
        uuid="streamuri"
        self.values[uuid] = self.value_factory['sensor_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The stream URI of your camera',
            label='Stream',
            default=None,
            get_data_cb=self.get_stream_uri,
        )
        uuid="actions"
        self.values[uuid] = self.value_factory['action_list'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The action on the camera',
            label='Actions',
            list_items=['start', 'stop', 'init'],
            set_data_cb=self.set_action,
            is_writeonly = True,
            cmd_class=COMMAND_CAMERA_STREAM,
            genre=0x01,
        )
        self._camera_lock =  threading.Lock()
        self._thread_lock =  threading.Lock()
        self.camera_cap =  None
        self.thread_cap =  None
        self.thread_stop =  threading.Event()
        self.first_frame =  None
        self.init_frames = 5
        self.out_file = None

    def get_stream_uri(self, node_uuid, index):
        """ Retrieve stream_uri """
        return None

    def check_heartbeat(self):
        """Check that the component is 'available'
        """
        return True

    def stop(self):
        """ Stop the bus """
        JNTComponent.stop(self)
        self.stop_cap()

    def start_cap(self, node_uuid=None, index=0):
        """ Start the stream capture """
        self._thread_lock.acquire()
        if self.thread_cap is not None:
            return
        self._start_cap()
        self.thread_stop.clear()
        try:
            self.first_frame = cv2.imread(self.values['blank_image'].data, flags=cv2.IMREAD_GRAYSCALE)
            self.thread_cap = threading.Thread(target=self._thread_cap)
            try:
                #For opencv 2
                fourcc = cv2.cv.CV_FOURCC(*self.values['codec_video'].data)
            except Exception:
                #Quick and dirty fix for opencv 3
                fourcc = cv2.VideoWriter_fourcc(*self.values['codec_video'].data)
            self.out_file = cv2.VideoWriter(os.path.join(self._bus.directory, self.values['occupied_video'].data), fourcc, 20.0, (640,480))
            self.thread_cap.start()
        except Exception:
            logger.exception('[%s] - Exception when start_cap', self.__class__.__name__)
        finally:
            self._thread_lock.release()

    def stop_cap(self, node_uuid=None, index=0):
        """ Stop the stream capture """
        self._thread_lock.acquire()
        try:
            self.thread_stop.set()
            if self.thread_cap is not None:
                self.thread_cap.join()
            self.thread_cap = None
            self.first_frame = None
            self._stop_cap()
            if self.out_file is not None:
                self.out_file.release()
        except Exception:
            logger.exception('[%s] - Exception when stop_cap', self.__class__.__name__)
        finally:
            self._thread_lock.release()

    def _thread_cap(self):
        """ The thread capture """
        while not self.thread_stop.is_set():
            try:
                # grab the current frame
                (grabbed, frame) = self.camera_cap.read()
                motion = False

                # resize the frame, convert it to grayscale, and blur it
                #~ frame = imutils.resize(frame, width=500)
                gray = self._gausian_transformation(frame)

                # if the first frame is None, initialize it
                if self.first_frame is None:
                    self.first_frame = gray
                    continue

                # compute the absolute difference between the current frame and
                # first frame
                frameDelta = cv2.absdiff(self.first_frame, gray)
                thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]

                # dilate the thresholded image to fill in holes, then find contours
                # on thresholded image
                thresh = cv2.dilate(thresh, None, iterations=2)
                try:
                    #For opencv 2
                    (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                except Exception:
                    #Quick and dirty fix for opencv 3
                    (_, cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                # loop over the contours
                for c in cnts:
                    # if the contour is too small, ignore it
                    if cv2.contourArea(c) < self.values['contour_min'].data:
                        logger.debug('[%s] - Ignore too small contour', self.__class__.__name__)
                        continue

                    # compute the bounding box for the contour, draw it on the frame,
                    # and update the text
                    (x, y, w, h) = cv2.boundingRect(c)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 1)
                    motion = True
                if motion:
                    logger.debug('[%s] - Motion detected in frame', self.__class__.__name__)
                    self.out_file.write(frame)
            except Exception:
                logger.exception('[%s] - Exception in _thread_cap', self.__class__.__name__)

    def _start_cap(self, node_uuid=None, index=0):
        """ Start the stream capture """
        self._camera_lock.acquire()
        try:
            if self.camera_cap is None:
                logger.debug('[%s] - Start capture', self.__class__.__name__)
                self.camera_cap = cv2.VideoCapture(self.get_stream_uri(node_uuid, index))
                #~ self.export_attrs('camera_cap', self.camera_cap)
                return True
        except Exception:
            logger.exception('[%s] - Exception when _start_cap', self.__class__.__name__)
        finally:
            self._camera_lock.release()

    def _stop_cap(self, node_uuid=None, index=0):
        """ Stop the stream capture """
        self._camera_lock.acquire()
        try:
            if self.camera_cap is not None:
                try:
                    logger.debug('[%s] - Stop capture', self.__class__.__name__)
                    self.camera_cap.release()
                except Exception:
                    logger.exception("[%s] - camera_cap.release()", self.__class__.__name__)
                self.camera_cap = None
                #~ self.export_attrs('camera_cap', self.camera_cap)
                return True
        except Exception:
            logger.exception('[%s] - Exception when _stop_cap', self.__class__.__name__)
        finally:
            self._camera_lock.release()

    def init_cap(self, node_uuid=None, index=0):
        """ Init the stream capture """
        try:
            if self.camera_cap is not None:
                return
            self._start_cap()
            logger.debug('[%s] - Grab first frame', self.__class__.__name__)
            max_frame = self.init_frames
            (grabbed, frame) = self.camera_cap.read()
            while not grabbed and max_frame>0:
                (grabbed, frame) = self.camera_cap.read()
                logger.debug('[%s] - Grab next frame', self.__class__.__name__)
                max_frame -= 1
            if grabbed:
                logger.debug('[%s] - Frame grabbed', self.__class__.__name__)
                gray = self._gausian_transformation(frame)
                cv2.imwrite(os.path.join(self._bus.directory, self.values['blank_image'].data), gray)
            self._stop_cap()
        except Exception:
            logger.exception('[%s] - Exception when init_cap', self.__class__.__name__)

    def _gausian_transformation(self, frame):
        """ Apply the gaussiand transformation """
        #~ frame = imutils.resize(frame, width=500)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        return gray

    def set_action(self, node_uuid, index, data):
        """Act on the server
        """
        params = {}
        if data == "start":
            self.start_cap()
        elif data == "stop":
            self.stop_cap()
        elif data == "init":
            self.init_cap()

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
            default=default_port,
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
        default_wsdl_dir = kwargs.pop('default_wsdl_dir', os.path.join(os.path.dirname(onvif.__path__[0]), 'wsdl'))
        uuid="wsdl_dir"
        self.values[uuid] = self.value_factory['config_string'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The wsdl directory',
            label='Dir',
            default=default_wsdl_dir,
        )

    def get_stream_uri(self, node_uuid, index):
        """ Retrieve stream_uri """
        try:
            logger.debug('[%s] - Connect to camera %s:%s', self.__class__.__name__, self.values['ip_ping_config'].data, self.values['port'].data)
            mycam = onvif.ONVIFCamera(
                self.values['ip_ping_config'].data,
                self.values['port'].data,
                self.values['user'].data,
                self.values['passwd'].data,
                wsdl_dir=self.values['wsdl_dir'].data)
            media_service = mycam.create_media_service()
            profiles = media_service.GetProfiles()
            # Use the first profile and Profiles have at least one
            token = profiles[0]._token
            suri = media_service.GetStreamUri({'StreamSetup':{'StreamType':'RTP_unicast','TransportProtocol':'UDP'},'ProfileToken':token})
            logger.debug('[%s] - Get URI %s', self.__class__.__name__, suri.Uri)
            return suri.Uri.replace("://", "://%s:%s@" % (self.values['user'].data, self.values['passwd'].data))
        except Exception:
            logger.exception('[%s] - Exception when get_stream_uri', self.__class__.__name__)
            return None

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

class IpcComponent(NetworkCameraComponent):
    """ An IPC camera component"""

    def __init__(self, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.ipc'%OID)
        name = kwargs.pop('name', "IPC (Maginon) camera")
        product_name = kwargs.pop('product_name', "IPC (Maginon) camera")
        NetworkCameraComponent.__init__(self, oid=oid, name=name,
                product_name=product_name, **kwargs)

    def get_stream_uri(self, node_uuid, index):
        """ Retrieve stream_uri """
        try:
            logger.debug('[%s] - Connect to camera %s', self.__class__.__name__, self.values['ip_ping_config'].data)
            #~ return "http://%s/videostream.cgi?user=%s&pwd=%s&quality=high"%(self.values['ip_ping_config'].data, self.values['user'].data, self.values['passwd'].data)
            return "http://%s/videostream.cgi?user=%s&pwd=%s&quality=hd"%(self.values['ip_ping_config'].data, self.values['user'].data, self.values['passwd'].data)
        except Exception:
            logger.exception('[%s] - Exception when get_stream_uri', self.__class__.__name__)
            return None
