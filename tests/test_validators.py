"""Tests for input validation module."""

from __future__ import annotations

import pytest

from mcp_cst_studio.types import SolverType
from mcp_cst_studio.validators import (
    ValidationError,
    validate_component_path,
    validate_enum_value,
    validate_file_path,
    validate_frequency,
    validate_name,
    validate_non_negative,
    validate_port_number,
    validate_positive,
    validate_range,
    validate_vba_input,
)


class TestValidateName:
    def test_valid_names(self):
        assert validate_name("Antenna") == "Antenna"
        assert validate_name("my_brick") == "my_brick"
        assert validate_name("Part 1") == "Part 1"
        assert validate_name("v2.0-patch") == "v2.0-patch"
        assert validate_name("_private") == "_private"

    def test_empty(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_name("")

    def test_starts_with_number(self):
        with pytest.raises(ValidationError, match="must start with"):
            validate_name("1brick")

    def test_special_chars(self):
        with pytest.raises(ValidationError):
            validate_name("brick@#$")

    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_name("a" * 101)


class TestValidateComponentPath:
    def test_valid(self):
        assert validate_component_path("Antenna:Patch") == "Antenna:Patch"
        assert validate_component_path("comp1") == "comp1"

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_component_path("")

    def test_invalid_chars(self):
        with pytest.raises(ValidationError):
            validate_component_path("comp/solid")


class TestValidateVBAInput:
    def test_safe_code(self):
        code = 'With Brick\n  .Reset\n  .Name "box"\n  .Create\nEnd With'
        assert validate_vba_input(code) == code

    def test_shell_blocked(self):
        with pytest.raises(ValidationError, match="Shell"):
            validate_vba_input("Shell \"cmd.exe\"")

    def test_createobject_blocked(self):
        with pytest.raises(ValidationError, match="CreateObject"):
            validate_vba_input('Set obj = CreateObject("WScript.Shell")')

    def test_kill_blocked(self):
        with pytest.raises(ValidationError, match="Kill"):
            validate_vba_input('Kill "C:\\file.txt"')

    def test_sendkeys_blocked(self):
        with pytest.raises(ValidationError, match="SendKeys"):
            validate_vba_input('SendKeys "{ENTER}"')

    def test_file_io_blocked(self):
        with pytest.raises(ValidationError, match="Open"):
            validate_vba_input('Open "file.txt" For Output As #1')

    def test_declare_blocked(self):
        with pytest.raises(ValidationError, match="Declare"):
            validate_vba_input('Declare Sub Sleep Lib "kernel32"')

    def test_cmd_blocked(self):
        with pytest.raises(ValidationError, match="cmd"):
            validate_vba_input('cmd /c dir')

    def test_case_insensitive(self):
        with pytest.raises(ValidationError):
            validate_vba_input("SHELL \"calc.exe\"")

    def test_safe_line_continuation_allowed(self):
        code = 'With Brick\n  .Name _\n  "box"\n  .Create\nEnd With'
        assert validate_vba_input(code) == code

    def test_line_continued_shell_blocked(self):
        with pytest.raises(ValidationError, match="Shell"):
            validate_vba_input('Shell _\n"cmd.exe"')

    def test_line_continued_createobject_blocked(self):
        with pytest.raises(ValidationError, match="CreateObject"):
            validate_vba_input('Set obj = CreateObject _\n("WScript.Shell")')

    def test_line_continued_open_for_blocked(self):
        with pytest.raises(ValidationError, match="Open"):
            validate_vba_input('Open _\n"file.txt" For Output As #1')

    def test_line_continued_declare_blocked(self):
        with pytest.raises(ValidationError, match="Declare"):
            validate_vba_input('Declare _\nSub Sleep Lib "kernel32"')

    def test_callbyname_blocked(self):
        with pytest.raises(ValidationError, match="CallByName"):
            validate_vba_input('CallByName obj, "Quit", VbMethod')

    def test_line_continued_callbyname_blocked(self):
        with pytest.raises(ValidationError, match="CallByName"):
            validate_vba_input('CallByName _\nobj, "Quit", VbMethod')


class TestValidateFilePath:
    def test_valid(self):
        assert validate_file_path("project.cst") == "project.cst"
        assert validate_file_path(r"C:\cst\project.cst") == r"C:\cst\project.cst"

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_file_path("")

    def test_traversal(self):
        with pytest.raises(ValidationError, match="traversal"):
            validate_file_path("../../etc/passwd")

    def test_outside_workdir(self):
        with pytest.raises(ValidationError, match="work directory"):
            validate_file_path("/etc/passwd", work_dir="/home/user/cst")


class TestValidateNumeric:
    def test_positive(self):
        assert validate_positive(1.5) == 1.5
        with pytest.raises(ValidationError):
            validate_positive(0)
        with pytest.raises(ValidationError):
            validate_positive(-1)

    def test_non_negative(self):
        assert validate_non_negative(0) == 0
        assert validate_non_negative(1.5) == 1.5
        with pytest.raises(ValidationError):
            validate_non_negative(-0.1)

    def test_range(self):
        assert validate_range(5, 0, 10) == 5
        with pytest.raises(ValidationError):
            validate_range(11, 0, 10)

    def test_frequency(self):
        assert validate_frequency(2.45) == 2.45
        with pytest.raises(ValidationError):
            validate_frequency(0)
        with pytest.raises(ValidationError):
            validate_frequency(1001)

    def test_port_number(self):
        assert validate_port_number(1) == 1
        assert validate_port_number(999) == 999
        with pytest.raises(ValidationError):
            validate_port_number(0)
        with pytest.raises(ValidationError):
            validate_port_number(1000)


class TestValidateEnum:
    def test_valid(self):
        assert validate_enum_value("Time Domain", SolverType) == "Time Domain"

    def test_invalid(self):
        with pytest.raises(ValidationError, match="Invalid"):
            validate_enum_value("Bad Solver", SolverType)
