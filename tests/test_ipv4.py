from __future__ import annotations

from makkuro.detectors.ipv4 import IPv4Detector


class TestIPv4Detector:
    def setup_method(self):
        self.det = IPv4Detector()

    def test_basic(self):
        hits = self.det.scan("server at 192.168.1.1 responded")
        assert len(hits) == 1
        assert hits[0].value == "192.168.1.1"
        assert hits[0].type == "IPV4_ADDRESS"

    def test_public_ip(self):
        hits = self.det.scan("access from 203.0.113.42")
        assert len(hits) == 1
        assert hits[0].value == "203.0.113.42"

    def test_multiple(self):
        hits = self.det.scan("src=10.0.0.1 dst=172.16.0.5")
        assert len(hits) == 2
        assert {h.value for h in hits} == {"10.0.0.1", "172.16.0.5"}

    def test_ignores_loopback(self):
        assert self.det.scan("localhost 127.0.0.1 is local") == []

    def test_ignores_link_local(self):
        assert self.det.scan("169.254.0.1 link-local") == []

    def test_ignores_broadcast(self):
        assert self.det.scan("broadcast 255.255.255.255") == []

    def test_ignores_zero_prefix(self):
        assert self.det.scan("0.0.0.0 unspecified") == []

    def test_boundary_max_octets(self):
        hits = self.det.scan("addr 255.255.255.254")
        assert len(hits) == 1
        assert hits[0].value == "255.255.255.254"

    def test_no_match_invalid_octet(self):
        assert self.det.scan("not an ip 999.999.999.999") == []

    def test_no_match_partial(self):
        assert self.det.scan("version 1.2.3") == []

    def test_embedded_in_text(self):
        hits = self.det.scan("ユーザーのIPは203.0.113.7です")
        assert len(hits) == 1
        assert hits[0].value == "203.0.113.7"

    def test_no_match_extra_dotted_segment(self):
        # "1.2.3.4.5" should not match as "1.2.3.4" (avoids version strings)
        assert self.det.scan("version 1.2.3.4.5") == []
