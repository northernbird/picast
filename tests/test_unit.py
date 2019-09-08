import picast
import pytest


@pytest.mark.unit
def test_get_video_parameter():
    expected = "wfd_audio_codecs: LPCM 00000002 00\r\n" \
               "wfd_video_formats: 10 00 02 10 0001FFFF 07FFFFFF 00000FFF 00 0000 0000 00 none none\r\n" \
               "wfd_3d_video_formats: none\r\nwfd_coupled_sink: none\r\nwfd_display_edid: none\r\n" \
               "wfd_connector_type: 05\r\nwfd_uibc_capability: none\r\nwfd_standby_resume_capability: none\r\n" \
               "wfd_content_protection: none\r\n"
    wp = picast.WfdParameters()
    assert wp.get_video_parameter() == expected

@pytest.mark.unit
def test_wpacli_start_p2p_find(monkeypatch):

    def mockreturn(self, arg):
        if arg == "p2p_find type=progressive":
            return "OK"
        else:
            return "NG"

    monkeypatch.setattr(picast.WpaCli, "cmd", mockreturn)
    wpacli = picast.WpaCli()
    wpacli.start_p2p_find()


@pytest.mark.unit
def test_wpacli_stop_p2p_find(monkeypatch):

    def mockreturn(self, arg):
        if arg == "p2p_stop_find":
            return "OK"
        else:
            return "NG"

    monkeypatch.setattr(picast.WpaCli, "cmd", mockreturn)
    wpacli = picast.WpaCli()
    wpacli.stop_p2p_find()


@pytest.mark.unit
def test_wpacli_set_device_name(monkeypatch):

    def mockreturn(self, arg):
        if arg == "set device_name foo":
            return "OK"
        else:
            return "NG"

    monkeypatch.setattr(picast.WpaCli, "cmd", mockreturn)
    wpacli = picast.WpaCli()
    wpacli.set_device_name("foo")


@pytest.mark.unit
def test_wpacli_set_device_type(monkeypatch):

    def mockreturn(self, arg):
        if arg == "set device_type foo":
            return "OK"
        else:
            return "NG"

    monkeypatch.setattr(picast.WpaCli, "cmd", mockreturn)
    wpacli = picast.WpaCli()
    wpacli.set_device_type("foo")


@pytest.mark.unit
def test_wpacli_set_p2p_go_ht40(monkeypatch):

    def mockreturn(self, arg):
        if arg == "set p2p_go_ht40 1":
            return "OK"
        else:
            return "NG"

    monkeypatch.setattr(picast.WpaCli, "cmd", mockreturn)
    wpacli = picast.WpaCli()
    wpacli.set_p2p_go_ht40()
