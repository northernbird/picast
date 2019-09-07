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
        return "OK"
    monkeypatch.setattr(picast.WpaCli, "cmd", mockreturn)
    wpacli = picast.WpaCli()
    wpacli.start_p2p_find()
