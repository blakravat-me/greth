from subprocess import CompletedProcess

import pytest
from pydantic import ValidationError

from greth.tools import policy
from greth.tools.filesystem._path import WORKSPACE, resolve
from greth.tools.process import proc


def test_container_list_dir_accepts_only_approved_read_only_directories():
    assert proc.ContainerListDirArgs(path="/usr/bin").path == "/usr/bin"

    with pytest.raises(ValidationError, match="Input should be"):
        proc.ContainerListDirArgs(path="/etc")


def test_container_list_dir_runs_ls_without_a_shell(monkeypatch):
    captured = {}

    def fake_exec(*args):
        captured["args"] = args
        return CompletedProcess(args, 0, stdout="bash\npython3\n", stderr="")

    monkeypatch.setattr("greth.runtime.docker.exec_in_container", fake_exec)

    assert proc.container_list_dir("/usr/bin") == "bash\npython3"
    assert captured["args"] == ("ls", "-1A", "--", "/usr/bin")


def test_container_list_dir_reports_container_errors(monkeypatch):
    def fail(*args):
        raise RuntimeError("sandbox is not running")

    monkeypatch.setattr("greth.runtime.docker.exec_in_container", fail)

    assert proc.container_list_dir("/usr/bin") == "[ERROR] Unable to list sandbox directory /usr/bin: sandbox is not running"


def test_container_list_dir_is_offered_to_read_only_phase():
    names = {schema["name"] for schema in policy.schemas("scout", "act")}

    assert "container_list_dir" in names


def test_container_list_dir_is_dispatched_through_tool_policy(monkeypatch):
    def fake_exec(*args):
        return CompletedProcess(args, 0, stdout="bash\n", stderr="")

    monkeypatch.setattr("greth.runtime.docker.exec_in_container", fake_exec)
    result = policy.dispatch("scout", "act", "container_list_dir", {"path": "/usr/bin"})

    assert result == "bash"


def test_workspace_path_rejection_suggests_the_sandbox_tool():
    with pytest.raises(ValueError, match="use container_list_dir"):
        resolve("/usr/bin")

    assert resolve(".") == WORKSPACE
