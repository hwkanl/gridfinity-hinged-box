import os
import shutil
import stat
import subprocess
import tempfile

from hwkan_gfbox import publish

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}
PRIVATE_EMAIL = "private@example.invalid"
PUBLIC_EMAIL = "public@example.invalid"


def _git(where, *args):
    return subprocess.run(["git", "-C", where, *args], check=True, capture_output=True, text=True, env=ENV).stdout


def _rmtree(path):
    """shutil.rmtree that also removes git's read-only object files (Windows)."""
    def clear(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=clear)


def _package_xml(email, version="0.1.0", date="2026-01-01"):
    return f'<version>{version}</version><date>{date}</date><maintainer email="{email}">m</maintainer>'


def _private(root, maintainer_email=PUBLIC_EMAIL):
    """A fake private tree with every whitelisted name plus unpublished ones, committed."""
    os.makedirs(os.path.join(root, "hwkan_gfbox", "__pycache__"))
    os.makedirs(os.path.join(root, "scripts"))
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, "images"))
    files = {"hwkan_gfbox/__init__.py": '__version__ = "0.1.0"\n', "hwkan_gfbox/__pycache__/x.pyc": "",
             "scripts/a.py": "", "package.xml": _package_xml(maintainer_email),
             "Init.py": "", "InitGui.py": "", "LICENSE": "", "README.md": "", "DEVELOPING.md": "", "images/a.png": "",
             "CLAUDE.md": "", "docs/spec.md": ""}
    for name, text in files.items():
        with open(os.path.join(root, name), "w") as f:
            f.write(text)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", PRIVATE_EMAIL)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")


def _expect_error(text, *args):
    try:
        publish.publish(*args)
    except publish.PublishError as e:
        assert text in str(e), str(e)
    else:
        raise AssertionError("expected PublishError")


def test_stamp_writes_the_version_and_date():
    root = tempfile.mkdtemp()
    try:
        _private(root)
        publish.stamp("0.2.0", root, today="2026-11-01")
        with open(os.path.join(root, "package.xml")) as f:
            assert f.read() == _package_xml(PUBLIC_EMAIL, "0.2.0", "2026-11-01")
        with open(os.path.join(root, "hwkan_gfbox", "__init__.py")) as f:
            assert f.read() == '__version__ = "0.2.0"\n'
    finally:
        _rmtree(root)


def test_publish_mirrors_the_whitelist_and_commits():
    root, dest = tempfile.mkdtemp(), tempfile.mkdtemp()
    saved = dict(os.environ)
    try:
        _private(root)
        _git(dest, "init", "-q")
        with open(os.path.join(dest, "stale.py"), "w") as f:
            f.write("")
        os.environ.update({k: ENV[k] for k in ENV if k.startswith("GIT_")})  # publish's commit needs an identity
        publish.publish(dest, root)
        assert sorted(os.listdir(dest)) == sorted([".git"] + publish.WHITELIST)
        assert not os.path.exists(os.path.join(dest, "hwkan_gfbox", "__pycache__"))
        sha = _git(root, "rev-parse", "--short", "HEAD").strip()
        assert _git(dest, "log", "-1", "--format=%s").strip() == f"Release 0.1.0 (private {sha})"
    finally:
        os.environ.clear()
        os.environ.update(saved)
        _rmtree(root)
        _rmtree(dest)


def test_publish_refuses_a_dirty_tree_and_a_non_checkout():
    root, dest = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        _private(root)
        _expect_error("not a git checkout", dest, root)
        _git(dest, "init", "-q")
        with open(os.path.join(root, "scripts", "a.py"), "w") as f:
            f.write("changed")
        _expect_error("uncommitted changes", dest, root)
    finally:
        _rmtree(root)
        _rmtree(dest)


def test_publish_refuses_the_private_maintainer_email():
    root, dest = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        _private(root, maintainer_email=PRIVATE_EMAIL)
        _git(dest, "init", "-q")
        _expect_error("public address", dest, root)
        assert os.listdir(dest) == [".git"]
    finally:
        _rmtree(root)
        _rmtree(dest)


def test_publish_refuses_to_commit_as_the_private_address():
    root, dest = tempfile.mkdtemp(), tempfile.mkdtemp()
    saved = dict(os.environ)
    try:
        _private(root)
        _git(dest, "init", "-q")
        _git(dest, "config", "user.email", PRIVATE_EMAIL)
        for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
            os.environ.pop(k, None)
        _expect_error("would commit as the private git address", dest, root)
        assert os.listdir(dest) == [".git"]
    finally:
        os.environ.clear()
        os.environ.update(saved)
        _rmtree(root)
        _rmtree(dest)
