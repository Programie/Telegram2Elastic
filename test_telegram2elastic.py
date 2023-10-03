import pytest

from telegram2elastic import FileSize, DottedPathDict


class TestFileSize:
    def test_human_readable_to_bytes(self):
        assert FileSize.human_readable_to_bytes("1KB") == 1024
        assert FileSize.human_readable_to_bytes("1.5MB") == 1572864
        assert FileSize.human_readable_to_bytes("5G") == 5368709120
        assert FileSize.human_readable_to_bytes("12TB") == 13194139533312

    def test_bytes_to_human_readable(self):
        assert FileSize.bytes_to_human_readable(100) == "100.0B"
        assert FileSize.bytes_to_human_readable(1024) == "1.0KB"
        assert FileSize.bytes_to_human_readable(1572864) == "1.5MB"
        assert FileSize.bytes_to_human_readable(5368709120) == "5.0GB"
        assert FileSize.bytes_to_human_readable(13194139533312) == "12.0TB"


class TestDottedPathDict:
    def test(self):
        dotted_path_dict = DottedPathDict()
        dotted_path_dict.set("foo.bar", "hello")
        dotted_path_dict.set("hello", "world")

        assert dotted_path_dict.get("foo.bar") == "hello"
        assert dotted_path_dict.get("hello") == "world"

        with pytest.raises(TypeError):
            dotted_path_dict.set("foo.bar.baz", "other value")
