import base64
import json
import re

from reporepair.tasks.swebench import as_list, has_unselectable_ids, image_name, pytest_command


def test_as_list_parses_json_encoded_strings():
    assert as_list('["a::b", "c::d"]') == ["a::b", "c::d"]
    assert as_list("['a', 'b']") == ["a", "b"]
    assert as_list(["x"]) == ["x"]
    assert as_list("") == []


def test_image_name_encodes_double_underscores():
    assert image_name("astropy__astropy-12907") == "swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest"


def test_has_unselectable_ids_detects_truncated_ids():
    literal_backslash_n = "a::b[left-" + chr(92) + "n]"
    assert has_unselectable_ids({"FAIL_TO_PASS": [literal_backslash_n], "PASS_TO_PASS": []}) is True
    assert has_unselectable_ids({"FAIL_TO_PASS": ["a::b[l\n]"], "PASS_TO_PASS": []}) is True
    # Truncated mid-parameter: brackets never close.
    assert has_unselectable_ids({"FAIL_TO_PASS": ["a::b[(AttributeError,"], "PASS_TO_PASS": []}) is True
    assert has_unselectable_ids({"FAIL_TO_PASS": ["a::b[1]"], "PASS_TO_PASS": ["c::d"]}) is False


def test_pytest_command_roundtrips_node_ids_including_newlines():
    ids = ["t.py::test_a", "t.py::test_b[1-2]", "t.py::test_c[left0-right0-\n]"]
    command = pytest_command(ids)
    blob = re.search(r"b64decode\('([^']+)'\)", command).group(1)
    assert json.loads(base64.b64decode(blob).decode()) == ids
