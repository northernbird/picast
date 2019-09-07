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
import tkinter as Tk
from logging import DEBUG, StreamHandler, getLogger
from time import sleep


class Settings:
    device_name = 'picast'
    wifi_p2p_group_name = 'persistent'
    pin = '12345678'
    timeout = 300
    control_port = 7236
    myaddress = '192.168.173.1'
    leaseaddress = '192.168.173.80'
    netmask = '255.255.255.0'


class Dhcpd():

    def __init__(self, interface):
        self.dhcpd = None
        self.interface = interface

    def start(self):
        fd, self.conf_path = tempfile.mkstemp(suffix='.conf')
        conf = "start  {}\nend {}\ninterface {}\noption subnet {}\noption lease {}\n".format(
            Settings.leaseaddress, Settings.leaseaddress, self.interface, Settings.netmask, Settings.timeout)
        with open(self.conf_path, 'w') as c:
            c.write(conf)
        self.dhcpd = subprocess.Popen(["sudo", "udhcpd", self.conf_path])

    def stop(self):
        if self.dhcpd is not None:
            self.dhcpd.terminate()
            self.conf_path.unlink()


class Player():

    def __init__(self):
        self.player = None

    def start(self):
        logger = getLogger("PiCast:Play")
        logger.info("Start omxplayer")
        self.player = subprocess.Popen(["omxplayer", 'rtp://0.0.0.0:1028', '-n 1', '--live', '-hw'])

    def stop(self):
        if self.player is not None:
            self.player.terminate()


class WfdParameters:

    resolutions_cea = [
        (0,   640,  480, 60),  # p60
        (1,   720,  480, 60),  # p60
        (2,   720,  480, 60),  # i60
        (3,   720,  480, 50),  # p50
        (4,   720,  576, 50),  # i50
        (5,  1280,  720, 30),  # p30
        (6,  1280,  720, 60),  # p60
        (7,  1280, 1080, 30),  # p30
        (8,  1920, 1080, 60),  # p60
        (9,  1920, 1080, 60),  # i60
        (10, 1280,  720, 25),  # p25
        (11, 1280,  720, 50),  # p50
        (12, 1920, 1080, 25),  # p25
        (13, 1920, 1080, 50),  # p50
        (14, 1920, 1080, 50),  # i50
        (15, 1280,  720, 24),  # p24
        (16, 1920, 1080, 24),  # p24
        (17, 3840, 2160, 30),  # p30
        (18, 3840, 2160, 60),  # p60
        (19, 4096, 2160, 30),  # p30
        (20, 4096, 2160, 60),  # p60
        (21, 3840, 2160, 25),  # p25
        (22, 3840, 2160, 50),  # p50
        (23, 4096, 2160, 25),  # p25
        (24, 4086, 2160, 50),  # p50
        (25, 4096, 2160, 24),  # p24
        (26, 4096, 2160, 24),  # p24
    ]

    resolutions_vesa = [
        (0,   800,  600, 30),  # p30
        (1,   800,  600, 60),  # p60
        (2,  1024,  768, 30),  # p30
        (3,  1024,  768, 60),  # p60
        (4,  1152,  854, 30),  # p30
        (5,  1152,  854, 60),  # p60
        (6,  1280,  768, 30),  # p30
        (7,  1280,  768, 60),  # p60
        (8,  1280,  800, 30),  # p30
        (9,  1280,  800, 60),  # p60
        (10, 1360,  768, 30),  # p30
        (11, 1360,  768, 60),  # p60
        (12, 1366,  768, 30),  # p30
        (13, 1366,  768, 60),  # p60
        (14, 1280, 1024, 30),  # p30
        (15, 1280, 1024, 60),  # p60
        (16, 1440, 1050, 30),  # p30
        (17, 1440, 1050, 60),  # p60
        (18, 1440,  900, 30),  # p30
        (19, 1440,  900, 60),  # p60
        (20, 1600,  900, 30),  # p30
        (21, 1600,  900, 60),  # p60
        (22, 1600, 1200, 30),  # p30
        (23, 1600, 1200, 60),  # p60
        (24, 1680, 1024, 30),  # p30
        (25, 1680, 1024, 60),  # p60
        (26, 1680, 1050, 30),  # p30
        (27, 1680, 1050, 60),  # p60
        (28, 1920, 1200, 30),  # p30
        (29, 2560, 1440, 30),  # p30
        (30, 2560, 1440, 60),  # p60
        (31, 2560, 1600, 30),  # p30
        (32, 2560, 1600, 60),  # p60
    ]

    resolutions_hh = [
        (0, 800, 400, 30),
        (1, 800, 480, 60),
        (2, 854, 480, 30),
        (3, 854, 480, 60),
        (4, 864, 480, 30),
        (5, 864, 480, 60),
        (6, 640, 360, 30),
        (7, 640, 360, 60),
        (8, 960, 540, 30),
        (9, 960, 540, 60),
        (10, 848, 480, 30),
        (11, 848, 480, 60),
    ]

    def get_video_parameter(self):
        cea = 0x0001FFFF
        vesa = 0x07FFFFFF
        hh = 0xFFF
        # audio_codec: LPCM:0x01, AAC:0x02, AC3:0x04
        # audio_sampling_frequency: 44.1khz:1, 48khz:2
        # LPCM: 44.1kHz, 16b; 48 kHZ,16b
        # AAC: 48 kHz, 16b, 2 channels; 48kHz,16b, 4 channels, 48 kHz,16b,6 channels
        # AAC 00000001 00  : 2 ch AAC 48kHz
        msg = 'wfd_audio_codecs: LPCM 00000002 00\r\n'
        # wfd_video_formats: <native_resolution: 0x20>, <preferred>, <profile>, <level>,
        #                    <cea>, <vesa>, <hh>, <latency>, <min_slice>, <slice_enc>, <frame skipping support>
        #                    <max_hres>, <max_vres>
        # native: index in CEA support.
        # preferred-display-mode-supported: 0 or 1
        # profile: Constrained High Profile: 0x02, Constraint Baseline Profile: 0x01
        # level: H264 level 3.1: 0x01, 3.2: 0x02, 4.0: 0x04,4.1:0x08, 4.2=0x10
        #   3.2: 720p60,  4.1: FullHD@24, 4.2: FullHD@60
        #
        msg = msg + 'wfd_video_formats: 10 00 02 10 {0:08X} {1:08X} {2:08X} 00 0000 0000 00 none none\r\n'.format(
            cea, vesa, hh)
        msg = msg + 'wfd_3d_video_formats: none\r\n' \
                  + 'wfd_coupled_sink: none\r\n' \
                  + 'wfd_display_edid: none\r\n' \
                  + 'wfd_connector_type: 05\r\n' \
                  + 'wfd_uibc_capability: none\r\n' \
                  + 'wfd_standby_resume_capability: none\r\n' \
                  + 'wfd_content_protection: none\r\n'
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

    def __init__(self, log=False, loglevel=DEBUG):
        logger = getLogger("PiCast")
        handler = StreamHandler()
        handler.setLevel(DEBUG)
        logger.setLevel(loglevel)
        logger.addHandler(handler)
        logger.propagate = log
        WifiP2PServer().start()
        self.player = Player()
        self.logger = logger

    def wait_connection(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = ('192.168.173.80', Settings.control_port)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        connectcounter = 0
        while True:
            try:
                sock.connect(server_address)
            except socket.error as e:
                connectcounter = connectcounter + 1
                if connectcounter > 1024:
                    sock.close()
                    logger = getLogger("PiCast")
                    logger.debug("Exit because of caught maximum connection timeouts(1024 x 180sec ).")
                    return None, None
            else:
                break
        idrsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        idrsock_address = ('127.0.0.1', 0)
        idrsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        idrsock.bind(idrsock_address)
        addr, idrsockport = idrsock.getsockname()
        self.idrsockport = str(idrsockport)
        return sock, idrsock

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
        msg = 'wfd_client_rtp_ports: RTP/AVP/UDP;unicast 1028 0 mode=play\r\n'
        msg = msg + WfdParameters().get_video_parameter()
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
        m6req = 'SETUP rtsp://192.168.173.80/wfd1.0/streamid=0 RTSP/1.0\r\n' \
                + 'CSeq: 101\r\n' \
                + 'Transport: RTP/AVP/UDP;unicast;client_port=1028\r\n\r\n'
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
        m7req = 'PLAY rtsp://192.168.173.80/wfd1.0/streamid=0 RTSP/1.0\r\n' \
                + 'CSeq: 102\r\n' \
                + 'Session: ' + str(sessionid) + '\r\n\r\n'
        logger.debug("<-{}".format(m7req))
        sock.sendall(m7req.encode("UTF-8"))
        data = (sock.recv(1000))
        logger.debug("->{}".format(data))

    def run(self):
        logger = getLogger("PiCast.control")
        sock, idrsock = self.wait_connection()
        if sock is None:
            return
        self.cast_seq_m1(sock)
        self.cast_seq_m2(sock)
        self.cast_seq_m3(sock)
        self.cast_seq_m4(sock)
        self.cast_seq_m5(sock)
        sessionid = self.cast_seq_m6(sock)
        self.cast_seq_m7(sock, sessionid)
        logger.debug("---- Negotiation successful ----")
        fcntl.fcntl(sock, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(idrsock, fcntl.F_SETFL, os.O_NONBLOCK)
        csnum = 102
        watchdog = 0
        while True:
            try:
                data = (sock.recv(1000)).decode("UTF-8")
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    try:
                        (idrsock.recv(1000))
                    except socket.error as e:
                        err = e.args[0]
                        if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                            sleep(0.01)
                            watchdog = watchdog + 1
                            if watchdog == 70 / 0.01:
                                self.player.stop()
                                sleep(1)
                                break
                        else:
                            logger.debug("socket error.")
                            return
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
                    return
            else:
                logger.debug("data: {}".format(data))
                watchdog = 0
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
                            sock.sendall(resp.encode("UTF-8"))
                            break
        idrsock.close()
        sock.close()


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


def Tk_get_root():
    if not hasattr(Tk_get_root, "root"):
        Tk_get_root.root = Tk.Tk()
    return Tk_get_root.root


def _quit(self):
    root = Tk_get_root()
    root.quit()


def show_info():
    root = Tk_get_root()
    root.protocol("WM_DELETE_WINDOW", _quit)
    root.attributes("-fullscreen", True)
    root.update()
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    canvas = Tk.Canvas(root, width=w, height=h)
    canvas.pack()
    canvas.configure(background='linen')
    global tkImage
    tkImage = Tk.PhotoImage(file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pctablet.pgm"))
    canvas.create_image(500,  200, image=tkImage)
    canvas.create_text(80, 200, text="Welcome to 'picast'!")
    canvas.create_text(80, 300, text="PIN: 12345678")
    canvas.pack()
    root.update()


def get_display_resolutions():
    output = subprocess.Popen("xrandr | egrep -oh '[0-9]+x[0-9]+'", shell=True, stdout=subprocess.PIPE).communicate()[0]
    resolutions = output.split()
    return resolutions


if __name__ == '__main__':
    os.putenv('DISPLAY', ':0')

    picast = PiCast(log=True, loglevel=DEBUG)
    show_info()

    root = Tk_get_root()
    root.after(100, picast.run)
    root.mainloop()
