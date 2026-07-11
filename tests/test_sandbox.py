import os
import tempfile
from pathlib import Path

import pytest
from opcode_cli.permission.sandbox import check_path


class TestSandbox:
    def test_path_inside_project(self, tmp_path):
        project_root = str(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        allowed, err = check_path(str(test_file), project_root)
        assert allowed
        assert err is None

    def test_path_outside_project(self):
        project_root = "/home/user/project"
        allowed, err = check_path("/etc/passwd", project_root)
        assert not allowed
        assert "outside workspace" in err

    def test_relative_path_resolves(self, tmp_path):
        project_root = str(tmp_path)
        test_file = tmp_path / "sub" / "file.txt"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("hi")
        relative = os.path.relpath(str(test_file), str(tmp_path))
        allowed, err = check_path(relative, project_root, cwd=str(tmp_path))
        assert allowed

    def test_path_not_exists_parent_dir_check(self, tmp_path):
        project_root = str(tmp_path)
        new_file = tmp_path / "new_dir" / "new_file.txt"
        allowed, err = check_path(str(new_file), project_root)
        assert allowed

    def test_path_not_exists_outside(self):
        project_root = "/home/user/project"
        allowed, err = check_path("/etc/new_file", project_root)
        assert not allowed

    @pytest.mark.skipif(os.name != "posix", reason="symlink test, POSIX only")
    def test_symlink_escape(self, tmp_path):
        project_root = str(tmp_path)
        symlink = tmp_path / "link"
        symlink.symlink_to("/etc")
        allowed, err = check_path(str(symlink), project_root)
        assert not allowed
        assert "outside workspace" in err

    def test_project_root_resolved(self, tmp_path):
        project_root = str(tmp_path)
        test_file = tmp_path / "data.txt"
        test_file.write_text("ok")
        allowed, _ = check_path(str(test_file), project_root)
        assert allowed

    @pytest.mark.skipif(os.name != "nt", reason="Windows drive test")
    def test_different_windows_drive(self):
        allowed, err = check_path("D:\\other\\file.txt", "C:\\project")
        assert not allowed
        assert "different drive" in err
