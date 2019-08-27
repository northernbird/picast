#!/usr/bin/env python3

"""
picast - a simple wireless display receiver for Raspberry Pi

    Copyright (C) 2019 Hiroshi Miura
    Copyright (C) 2018 Hsun-Wei Cho

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import errno
import fcntl
import os
import re
import socket
import subprocess
import tempfile
import threading
from logging import DEBUG, StreamHandler, getLogger
from time import sleep

import gi

os.putenv('DISPLAY', ':0')  # noqa: E402 # isort:skip
gi.require_version('Gst', '1.0')  # noqa: E402 # isort:skip
gi.require_version('Gtk', '3.0')  # noqa: E402 # isort:skip
gi.require_version('GstVideo', '1.0')  # noqa: E402 # isort:skip
gi.require_version('GdkX11', '3.0')  # noqa: E402 # isort:skip
from gi.repository import Gst, Gtk  # noqa: E402 # isort:skip


class Settings:
    device_name = 'picast'
    wifi_p2p_group_name = 'persistent'
    pin = '12345678'
    timeout = 300
    control_port = 7236
    myaddress = '192.168.173.1'
    peeraddress = '192.168.173.80'
    netmask = '255.255.255.0'
    rtp_port = 7236


class Dhcpd():
    """DHCP server daemon running in background."""

    def __init__(self, interface):
        """Constructor accept an interface to listen."""
        self.dhcpd = None
        self.interface = interface

    def start(self):
        fd, self.conf_path = tempfile.mkstemp(suffix='.conf')
        conf = "start  {}\nend {}\ninterface {}\noption subnet {}\noption lease {}\n".format(
            Settings.peeraddress, Settings.peeraddress, self.interface, Settings.netmask, Settings.timeout)
        with open(self.conf_path, 'w') as c:
            c.write(conf)
        self.dhcpd = subprocess.Popen(["sudo", "udhcpd", self.conf_path])

    def stop(self):
        if self.dhcpd is not None:
            self.dhcpd.terminate()
            self.conf_path.unlink()


class Res:

    def __init__(self, id, width, height, refresh, progressive=True):
        self.id = id
        self.width = width
        self.height = height
        self.refresh = refresh
        self.progressive = progressive

    @property
    def score(self):
        return self.width * self.height * self.refresh * (1 + 1 if self.progressive else 0)

    def __repr__(self):
        return "%s(%d,%d,%d,%d,%s)" % (type(self).__name__, self.id, self.width, self.height, self.refresh,
                                       'p' if self.progressive else 'i')

    def __str__(self):
        return 'resolution(%d) %d x %d x %d%s' % (self.id, self.width, self.height, self.refresh,
                                                  'p' if self.progressive else 'i')

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __ne__(self, other):
        return repr(self) != repr(other)

    def __ge__(self, other):
        return self.score >= other.score

    def __gt__(self, other):
        return self.score > other.score

    def __le__(self, other):
        return self.score <= other.score

    def __lt__(self, other):
        return self.score < other.score


class WfdVideoParameters:

    resolutions_cea = [
        Res(0,   640,  480, 60),  # mandatory res.
        Res(1,   720,  480, 60),  # p60
        Res(2,   720,  480, 60, False),  # i60
        Res(3,   720,  480, 50),  # p50
        Res(4,   720,  576, 50, False),  # i50
        Res(5,  1280,  720, 30),  # p30
        Res(6,  1280,  720, 60),  # p60
        Res(7,  1280, 1080, 30),  # p30
        Res(8,  1920, 1080, 60),  # p60
        Res(9,  1920, 1080, 60, False),  # i60
        Res(10, 1280,  720, 25),  # p25
        Res(11, 1280,  720, 50),  # p50
        Res(12, 1920, 1080, 25),  # p25
        Res(13, 1920, 1080, 50),  # p50
        Res(14, 1920, 1080, 50, False),  # i50
        Res(15, 1280,  720, 24),  # p24
        Res(16, 1920, 1080, 24),  # p24
        Res(17, 3840, 2160, 30),  # p30
        Res(18, 3840, 2160, 60),  # p60
        Res(19, 4096, 2160, 30),  # p30
        Res(20, 4096, 2160, 60),  # p60
        Res(21, 3840, 2160, 25),  # p25
        Res(22, 3840, 2160, 50),  # p50
        Res(23, 4096, 2160, 25),  # p25
        Res(24, 4086, 2160, 50),  # p50
        Res(25, 4096, 2160, 24),  # p24
        Res(26, 4096, 2160, 24),  # p24
    ]

    resolutions_vesa = [
        Res(0,   800,  600, 30),  # p30
        Res(1,   800,  600, 60),  # p60
        Res(2,  1024,  768, 30),  # p30
        Res(3,  1024,  768, 60),  # p60
        Res(4,  1152,  854, 30),  # p30
        Res(5,  1152,  854, 60),  # p60
        Res(6,  1280,  768, 30),  # p30
        Res(7,  1280,  768, 60),  # p60
        Res(8,  1280,  800, 30),  # p30
        Res(9,  1280,  800, 60),  # p60
        Res(10, 1360,  768, 30),  # p30
        Res(11, 1360,  768, 60),  # p60
        Res(12, 1366,  768, 30),  # p30
        Res(13, 1366,  768, 60),  # p60
        Res(14, 1280, 1024, 30),  # p30
        Res(15, 1280, 1024, 60),  # p60
        Res(16, 1440, 1050, 30),  # p30
        Res(17, 1440, 1050, 60),  # p60
        Res(18, 1440,  900, 30),  # p30
        Res(19, 1440,  900, 60),  # p60
        Res(20, 1600,  900, 30),  # p30
        Res(21, 1600,  900, 60),  # p60
        Res(22, 1600, 1200, 30),  # p30
        Res(23, 1600, 1200, 60),  # p60
        Res(24, 1680, 1024, 30),  # p30
        Res(25, 1680, 1024, 60),  # p60
        Res(26, 1680, 1050, 30),  # p30
        Res(27, 1680, 1050, 60),  # p60
        Res(28, 1920, 1200, 30),  # p30
        Res(29, 2560, 1440, 30),  # p30
        Res(30, 2560, 1440, 60),  # p60
        Res(31, 2560, 1600, 30),  # p30
        Res(32, 2560, 1600, 60),  # p60
    ]

    resolutions_hh = [
        Res(0, 800, 400, 30),
        Res(1, 800, 480, 60),
        Res(2, 854, 480, 30),
        Res(3, 854, 480, 60),
        Res(4, 864, 480, 30),
        Res(5, 864, 480, 60),
        Res(6, 640, 360, 30),
        Res(7, 640, 360, 60),
        Res(8, 960, 540, 30),
        Res(9, 960, 540, 60),
        Res(10, 848, 480, 30),
        Res(11, 848, 480, 60),
    ]

    def get_video_parameter(self):
        # audio_codec: LPCM:0x01, AAC:0x02, AC3:0x04
        # audio_sampling_frequency: 44.1khz:1, 48khz:2
        # LPCM: 44.1kHz, 16b; 48 kHZ,16b
        # AAC: 48 kHz, 16b, 2 channels; 48kHz,16b, 4 channels, 48 kHz,16b,6 channels
        # AAC 00000001 00  : 2 ch AAC 48kHz
        msg = 'wfd_audio_codecs: AAC 00000001 00, LPCM 00000002 00\r\n'
        # wfd_video_formats: <native_resolution: 0x20>, <preferred>, <profile>, <level>,
        #                    <cea>, <vesa>, <hh>, <latency>, <min_slice>, <slice_enc>, <frame skipping support>
        #                    <max_hres>, <max_vres>
        # native: index in CEA support.
        # preferred-display-mode-supported: 0 or 1
        # profile: Constrained High Profile: 0x02, Constraint Baseline Profile: 0x01
        # level: H264 level 3.1: 0x01, 3.2: 0x02, 4.0: 0x04,4.1:0x08, 4.2=0x10
        #   3.2: 720p60,  4.1: FullHD@24, 4.2: FullHD@60
        native = 0x08
        preferred = 0
        profile = 0x02 | 0x01
        level = 0x10
        cea = 0x0001FFFF
        vesa = 0x07FFFFFF
        hh = 0xFFF
        msg += 'wfd_video_formats: {0:02X} {1:02X} {2:02X} {3:02X} {4:08X} {5:08X} {6:08X}' \
               ' 00 0000 0000 00 none none\r\n'.format(native, preferred, profile, level, cea, vesa, hh)
        msg += 'wfd_3d_video_formats: none\r\n' \
               'wfd_coupled_sink: none\r\n' \
               'wfd_display_edid: none\r\n' \
               'wfd_connector_type: 05\r\n' \
               'wfd_uibc_capability: none\r\n' \
               'wfd_standby_resume_capability: none\r\n' \
               'wfd_content_protection: none\r\n'
        return msg


class PiCastException(Exception):
    pass


class WpaCli:
    """
    Wraps the wpa_cli command line interface.
    """

    def __init__(self):
        self.logger = getLogger("PiCast")
        pass

    def cmd(self, arg):
        command_str = "sudo wpa_cli"
        command_list = command_str.split(" ") + arg.split(" ")
        p = subprocess.Popen(command_list, stdout=subprocess.PIPE)
        stdout = p.communicate()[0]
        return stdout.decode('UTF-8').splitlines()

    def start_p2p_find(self):
        self.logger.debug("wpa_cli p2p_find type=progressive")
        status = self.cmd("p2p_find type=progressive")
        if 'OK' not in status:
            raise PiCastException("Fail to start p2p find.")

    def stop_p2p_find(self):
        self.logger.debug("wpa_cli p2p_stop_find")
        status = self.cmd("p2p_stop_find")
        if 'OK' not in status:
            raise PiCastException("Fail to stop p2p find.")

    def set_device_name(self, name):
        self.logger.debug("wpa_cli set device_name {}".format(name))
        status = self.cmd("set device_name {}".format(name))
        if 'OK' not in status:
            raise PiCastException("Fail to set device name {}".format(name))

    def set_device_type(self, type):
        self.logger.debug("wpa_cli set device_type {}".format(type))
        status = self.cmd("set device_type {}".format(type))
        if 'OK' not in status:
            raise PiCastException("Fail to set device type {}".format(type))

    def set_p2p_go_ht40(self):
        self.logger.debug("wpa_cli set p2p_go_ht40 1")
        status = self.cmd("set p2p_go_ht40 1")
        if 'OK' not in status:
            raise PiCastException("Fail to set p2p_go_ht40")

    def wfd_subelem_set(self, val):
        self.logger.debug("wpa_cli wfd_subelem_set {}".format(val))
        status = self.cmd("wfd_subelem_set {}".format(val))
        if 'OK' not in status:
            raise PiCastException("Fail to wfd_subelem_set.")

    def p2p_group_add(self, name):
        self.logger.debug("wpa_cli p2p_group_add {}".format(name))
        self.cmd("p2p_group_add {}".format(name))

    def set_wps_pin(self, interface, pin, timeout):
        self.logger.debug("wpa_cli -i {} wps_pin any {} {}".format(interface, pin, timeout))
        status = self.cmd("-i {} wps_pin any {} {}".format(interface, pin, timeout))
        return status

    def get_interfaces(self):
        selected = None
        interfaces = []
        status = self.cmd("interface")
        for ln in status:
            if ln.startswith("Selected interface"):
                selected = re.match(r"Selected interface\s\'(.+)\'$", ln).group(1)
            elif ln.startswith("Available interfaces:"):
                pass
            else:
                interfaces.append(str(ln))
        return selected, interfaces

    def get_p2p_interface(self):
        sel, interfaces = self.get_interfaces()
        for it in interfaces:
            if it.startswith("p2p-wl"):
                return it
        return None

    def check_p2p_interface(self):
        if self.get_p2p_interface() is not None:
            return True
        return False


class PiCast:

    def __init__(self, window):
        self.logger = getLogger("PiCast")
        self.window = window
        self.port = 1028
        self.player = GstPlayer(port=self.port)
        self.watchdog = 0
        self.csnum = 0

    def cast_seq_m1(self, sock):
        logger = getLogger("PiCast.m1")
        data = (sock.recv(1000))
        logger.debug("<-{}".format(data))
        s_data = 'RTSP/1.0 200 OK\r\nCSeq: 1\r\nPublic: org.wfa.wfd1.0, SET_PARAMETER, GET_PARAMETER\r\n\r\n'
        logger.debug("->{}".format(s_data))
        sock.sendall(s_data.encode("UTF-8"))

    def cast_seq_m2(self, sock):
        logger = getLogger("PiCast.m2")
        s_data = 'OPTIONS * RTSP/1.0\r\nCSeq: 100\r\nRequire: org.wfa.wfd1.0\r\n\r\n'
        logger.debug("<-{}".format(s_data))
        sock.sendall(s_data.encode("UTF-8"))
        data = (sock.recv(1000))
        logger.debug("->{}".format(data))

    def cast_seq_m3(self, sock):
        logger = getLogger("PiCast.m3")
        data = (sock.recv(1000))
        logger.debug("->{}".format(data))
        msg = "wfd_client_rtp_ports: RTP/AVP/UDP;unicast {} 0 mode=play\r\n".format(self.port)
        msg = msg + WfdVideoParameters().get_video_parameter()
        m3resp = 'RTSP/1.0 200 OK\r\nCSeq: 2\r\n' + 'Content-Type: text/parameters\r\nContent-Length: ' + str(
            len(msg)) + '\r\n\r\n' + msg
        logger.debug("<-{}".format(m3resp))
        sock.sendall(m3resp.encode("UTF-8"))

    def cast_seq_m4(self, sock):
        logger = getLogger("PiCast.m4")
        data = (sock.recv(1000)).decode("UTF-8")
        logger.debug("->{}".format(data))
        s_data = 'RTSP/1.0 200 OK\r\nCSeq: 3\r\n\r\n'
        logger.debug("<-{}".format(s_data))
        sock.sendall(s_data.encode("UTF-8"))

    def cast_seq_m5(self, sock):
        logger = getLogger("PiCast.m5")
        data = (sock.recv(1000))
        logger.debug("->{}".format(data))
        s_data = 'RTSP/1.0 200 OK\r\nCSeq: 4\r\n\r\n'
        logger.debug("<-{}".format(s_data))
        sock.sendall(s_data.encode("UTF-8"))

    def cast_seq_m6(self, sock):
        logger = getLogger("PiCast.m6")
        m6req = 'SETUP rtsp://{}/wfd1.0/streamid=0 RTSP/1.0\r\n'.format(Settings.peeraddress)
        m6req += 'CSeq: 101\r\n' \
                 + "Transport: RTP/AVP/UDP;unicast;client_port={}\r\n\r\n".format(self.port)
        logger.debug("<-{}".format(m6req))
        sock.sendall(m6req.encode("UTF-8"))
        data = (sock.recv(1000))
        logger.debug("->{}".format(data))
        paralist = data.decode("UTF-8").split(';')
        serverport = [x for x in paralist if 'server_port=' in x]
        logger.debug("server port {}".format(serverport))
        serverport = serverport[-1]
        serverport = serverport[12:17]
        logger.debug("server port {}".format(serverport))
        paralist = data.decode("UTF-8").split()
        position = paralist.index('Session:') + 1
        sessionid = paralist[position]
        return sessionid

    def cast_seq_m7(self, sock, sessionid):
        logger = getLogger("PiCast.m7")
        m7req = 'PLAY rtsp://{}/wfd1.0/streamid=0 RTSP/1.0\r\n'.format(Settings.peeraddress)
        m7req += 'CSeq: 102\r\n' \
                 + 'Session: {}\r\n\r\n'.format(str(sessionid))
        logger.debug("<-{}".format(m7req))
        sock.sendall(m7req.encode("UTF-8"))
        data = (sock.recv(1000))
        logger.debug("->{}".format(data))

    def handle_recv_err(self, e, sock, idrsock, csnum):
        logger = getLogger("PiCast.daemon.error")
        err = e.args[0]
        if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
            try:
                (idrsock.recv(1000))
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    sleep(0.01)
                    self.watchdog += 1
                    if self.watchdog >= 70 / 0.01:
                        self.player.stop()
                        sleep(1)
                else:
                    logger.debug("socket error.")
            else:
                csnum = csnum + 1
                msg = 'wfd-idr-request\r\n'
                idrreq = 'SET_PARAMETER rtsp://localhost/wfd1.0 RTSP/1.0\r\n' \
                         + 'Content-Length: ' + str(len(msg)) + '\r\n' \
                         + 'Content-Type: text/parameters\r\n' \
                         + 'CSeq: ' + str(csnum) + '\r\n\r\n' \
                         + msg
                logger.debug("idreq: {}".format(idrreq))
                sock.sendall(idrreq.encode("UTF-8"))
        else:
            logger.debug("Exit becuase of socket error.")
        return csnum

    def negotiate(self, conn):
        logger = getLogger("Picast.daemon")
        logger.debug("---- Start negotiation ----")
        self.cast_seq_m1(conn)
        self.cast_seq_m2(conn)
        self.cast_seq_m3(conn)
        self.cast_seq_m4(conn)
        self.cast_seq_m5(conn)
        sessionid = self.cast_seq_m6(conn)
        self.cast_seq_m7(conn, sessionid)
        logger.debug("---- Negotiation successful ----")

    def rtspsrv(self, conn, idrsock):
        logger = getLogger("PiCast.rtspsrv")
        csnum = 102
        while True:
            try:
                data = (conn.recv(1000)).decode("UTF-8")
            except socket.error as e:
                watchdog, csnum = self.handle_recv_err(e, conn, idrsock, csnum)
            else:
                logger.debug("data: {}".format(data))
                self.watchdog = 0
                if len(data) == 0 or 'wfd_trigger_method: TEARDOWN' in data:
                    self.player.stop()
                    sleep(1)
                    break
                elif 'wfd_video_formats' in data:
                    logger.info('start player')
                    self.player.start()
                messagelist = data.splitlines()
                singlemessagelist = [x for x in messagelist if ('GET_PARAMETER' in x or 'SET_PARAMETER' in x)]
                logger.debug(singlemessagelist)
                for singlemessage in singlemessagelist:
                    entrylist = singlemessage.splitlines()
                    for entry in entrylist:
                        if re.match(r'CSeq:', entry):
                            cseq = entry
                            resp = 'RTSP/1.0 200 OK\r' + cseq + '\r\n\r\n'  # cseq contains \n
                            logger.debug("Response: {}".format(resp))
                            conn.sendall(resp.encode("UTF-8"))
                            continue

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            server_address = (Settings.peeraddress, Settings.rtp_port)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(server_address)
            sock.listen(1)
            while True:
                conn, addr = sock.accept()
                with conn:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as idrsock:
                        idrsock_address = ('127.0.0.1', 0)
                        idrsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        idrsock.bind(idrsock_address)
                        addr, idrsockport = idrsock.getsockname()
                        self.idrsockport = str(idrsockport)
                        self.negotiate(conn)
                        fcntl.fcntl(conn, fcntl.F_SETFL, os.O_NONBLOCK)
                        fcntl.fcntl(idrsock, fcntl.F_SETFL, os.O_NONBLOCK)
                        self.rtspsrv(conn, idrsock)


class WifiP2PServer:

    def start(self):
        self.set_p2p_interface()
        self.start_dhcpd()
        self.start_wps()

    def start_wps(self):
        wpacli = WpaCli()
        wpacli.set_wps_pin(self.wlandev, Settings.pin, Settings.timeout)

    def start_dhcpd(self):
        dhcpd = Dhcpd(self.wlandev)
        dhcpd.start()
        sleep(0.5)

    def wfd_devinfo(self, port):
        type = 0b01  # PRIMARY_SINK
        session = 0b01 << 4
        wsd = 0b01 << 6
        pc = 0  # P2P
        cp_support = 0
        ts = 0
        devinfo = type | session | wsd | pc | cp_support | ts
        control = port
        max_tp = 300  # Mbps
        return '0006{0:04x}{1:04x}{2:04x}'.format(devinfo, control, max_tp)

    def wfd_bssid(self, bssid):
        return '0006{0:012x}'.format(bssid)

    def wfd_sink_info(self, status, mac):
        return '0007{0:02x}{1:012x}'.format(status, mac)

    def create_p2p_interface(self):
        wpacli = WpaCli()
        wpacli.start_p2p_find()
        wpacli.set_device_name(Settings.device_name)
        wpacli.set_device_type("7-0050F204-1")
        wpacli.set_p2p_go_ht40()
        wpacli.wfd_subelem_set("0 {}".format(self.wfd_devinfo(port=Settings.control_port)))
        wpacli.wfd_subelem_set("1 {}".format(self.wfd_bssid(0)))
        wpacli.wfd_subelem_set("6 {}".format(self.wfd_sink_info(0, 0)))
        wpacli.p2p_group_add(Settings.wifi_p2p_group_name)

    def set_p2p_interface(self):
        logger = getLogger("PiCast")
        wpacli = WpaCli()
        if wpacli.check_p2p_interface():
            logger.info("Already set a p2p interface.")
            p2p_interface = wpacli.get_p2p_interface()
        else:
            self.create_p2p_interface()
            sleep(3)
            p2p_interface = wpacli.get_p2p_interface()
            if p2p_interface is None:
                raise PiCastException("Can not create P2P Wifi interface.")
            logger.info("Start p2p interface: {}".format(p2p_interface))
            os.system("sudo ifconfig {} {}".format(p2p_interface, Settings.myaddress))
        self.wlandev = p2p_interface


class GstPlayer(Gtk.Window):
    def __init__(self, port, scale=False):
        self.logger = getLogger("PiCast:GstPlayer")
        width = 640
        height = 400
        gstcommand = "udpsrc port={0:d} caps=\"application/x-rtp, media=video\" ".format(port)
        gstcommand += "! rtpjitterbuffer latency=100 ! rtpmp2tdepay ! tsdemux name=demuxer demuxer. " \
                      "! queue max-size-buffers=0 max-size-time=0 ! h264parse ! omxh264dec ! videoconvert ! "
        if scale:
            gstcommand += "videoscale method=1 ! video/x-raw,width={0:d},height={1:d} ! ".format(width, height)
        gstcommand += "autovideosink demuxer. ! queue max-size-buffers=0 max-size-time=0 " \
                      "! aacparse ! avdec_aac ! audioconvert ! audioresample ! autoaudiosink "
        self.pipeline = Gst.parse_launch(gstcommand)
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::eos', self.on_eos)
        self.bus.connect('message::error', self.on_error)

        self.bus.enable_sync_message_emission()
        self.bus.connect('sync-message::element', self.on_sync_message)
        self.bus.connect('message', self.on_message)

    def on_message(self, bus, message):
        pass

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)

    def on_sync_message(self, bus, msg):
        if msg.get_structure().get_name() == 'prepare-window-handle':
            if hasattr(self, 'xid'):
                msg.src.set_window_handle(self.xid)

    def on_eos(self, bus, msg):
        self.logger.debug('on_eos(): seeking to start of video')
        self.pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            0
        )

    def on_error(self, bus, msg):
        self.logger.debug('on_error():{}'.format(msg.parse_error()))


def get_display_resolutions():
    output = subprocess.Popen("xrandr | egrep -oh '[0-9]+x[0-9]+'", shell=True, stdout=subprocess.PIPE).communicate()[0]
    resolutions = output.split()
    return resolutions


def setup_logger():
    logger = getLogger("PiCast")
    handler = StreamHandler()
    handler.setLevel(DEBUG)
    logger.setLevel(DEBUG)
    logger.addHandler(handler)
    logger.propagate = True


def app_main():
    setup_logger()
    WifiP2PServer().start()
    window = Gtk.Window()
    window.set_name('PiCast')
    window.connect('destroy', Gtk.main_quit)

    def picast_target():
        picast = PiCast(window)
        picast.run()
        Gtk.main_quit()

    window.show_all()

    thread = threading.Thread(target=picast_target)
    thread.daemon = True
    thread.start()


if __name__ == '__main__':
    Gst.init(None)
    app_main()
    Gtk.main()
