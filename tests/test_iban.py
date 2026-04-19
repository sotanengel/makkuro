from __future__ import annotations

from makkuro.detectors.iban import IBANDetector, _iban_mod97


class TestIBANMod97:
    def test_valid_de(self):
        assert _iban_mod97("DE89370400440532013000")

    def test_valid_gb(self):
        assert _iban_mod97("GB29NWBK60161331926819")

    def test_valid_fr(self):
        assert _iban_mod97("FR7630006000011234567890189")

    def test_valid_with_spaces(self):
        assert _iban_mod97("DE89 3704 0044 0532 0130 00")

    def test_invalid_checksum(self):
        assert not _iban_mod97("DE00370400440532013000")

    def test_invalid_country(self):
        assert not _iban_mod97("XX89370400440532013000")

    def test_too_short(self):
        assert not _iban_mod97("DE891234")


class TestIBANDetector:
    def setup_method(self):
        self.det = IBANDetector()

    def test_detect_de(self):
        hits = self.det.scan("IBAN: DE89370400440532013000 bitte")
        assert len(hits) == 1
        assert hits[0].value == "DE89370400440532013000"
        assert hits[0].type == "IBAN"

    def test_detect_gb(self):
        hits = self.det.scan("account GB29NWBK60161331926819")
        assert len(hits) == 1
        assert hits[0].value == "GB29NWBK60161331926819"

    def test_detect_spaced(self):
        hits = self.det.scan("pay to DE89 3704 0044 0532 0130 00 now")
        assert len(hits) == 1

    def test_multiple(self):
        text = "from DE89370400440532013000 to GB29NWBK60161331926819"
        hits = self.det.scan(text)
        assert len(hits) == 2

    def test_rejects_invalid_checksum(self):
        assert self.det.scan("fake DE00370400440532013000 iban") == []

    def test_no_match_random_text(self):
        assert self.det.scan("this is just normal text") == []

    def test_score(self):
        hits = self.det.scan("DE89370400440532013000")
        assert hits[0].score == 0.97

    def test_nl_iban(self):
        hits = self.det.scan("NL91ABNA0417164300")
        assert len(hits) == 1
        assert hits[0].value == "NL91ABNA0417164300"
