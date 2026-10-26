"""Publish the addon into a checkout of the public repo (spec:
docs/superpowers/specs/2026-10-24-freecad-addon-design.md, "Publishing").

    scripts/fc.sh scripts/publish.py stamp VERSION   then commit the stamp
    scripts/fc.sh scripts/publish.py PUBLIC_CHECKOUT then push PUBLIC_CHECKOUT
"""
import datetime
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHITELIST = ["hwkan_gfbox", "scripts", "package.xml", "Init.py", "InitGui.py", "LICENSE", "README.md"]


class PublishError(Exception):
    pass


def _git(where, *args):
    return subprocess.run(["git", "-C", where, *args], check=True, capture_output=True, text=True).stdout


def _sub(path, pattern, repl):
    with open(path) as f:
        text = f.read()
    new, n = re.subn(pattern, repl, text)
    if n != 1:
        raise PublishError(f"{path}: expected one match of {pattern}, found {n}")
    with open(path, "w") as f:
        f.write(new)


def version(root=ROOT):
    with open(os.path.join(root, "hwkan_gfbox", "__init__.py")) as f:
        return re.search(r'__version__ = "([^"]*)"', f.read()).group(1)


def stamp(ver, root=ROOT, today=None):
    """Write ver (and today's date) into package.xml and hwkan_gfbox/__init__.py."""
    today = today or datetime.date.today().isoformat()
    _sub(os.path.join(root, "package.xml"), r"<version>[^<]*</version>", f"<version>{ver}</version>")
    _sub(os.path.join(root, "package.xml"), r"<date>[^<]*</date>", f"<date>{today}</date>")
    _sub(os.path.join(root, "hwkan_gfbox", "__init__.py"), r'__version__ = "[^"]*"', f'__version__ = "{ver}"')


def _check_maintainer(root):
    """Refuse to publish the private git address as the maintainer's."""
    with open(os.path.join(root, "package.xml")) as f:
        m = re.search(r'<maintainer\s+email="([^"]*)"', f.read())
    if not m:
        raise PublishError("package.xml has no <maintainer email=...>")
    private = subprocess.run(["git", "-C", root, "config", "user.email"], capture_output=True, text=True).stdout.strip()
    if private and m.group(1).strip().lower() == private.lower():
        raise PublishError("package.xml's maintainer email is the private git address: "
                           "put a public address in package.xml first")


def _check_identity(dest, root):
    """Refuse to commit in dest as the private git address (it would be published with the commit)."""
    private = subprocess.run(["git", "-C", root, "config", "user.email"], capture_output=True, text=True).stdout.strip()
    for var in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        ident = subprocess.run(["git", "-C", dest, "var", var], capture_output=True, text=True).stdout
        m = re.search(r"<([^>]*)>", ident)
        if private and m and m.group(1).strip().lower() == private.lower():
            raise PublishError(f"{dest} would commit as the private git address: "
                               f"set a public one there with git -C {dest} config user.email ADDRESS")


def publish(dest, root=ROOT):
    """Make dest (a git checkout of the public repo) hold exactly the
    whitelist from root's committed state, and commit it there. No push."""
    if not os.path.isdir(os.path.join(dest, ".git")):
        raise PublishError(f"{dest} is not a git checkout")
    if _git(root, "status", "--porcelain", "--", *WHITELIST).strip():
        raise PublishError("the private tree has uncommitted changes in published files: commit them first")
    _check_maintainer(root)
    _check_identity(dest, root)
    for name in os.listdir(dest):
        if name == ".git":
            continue
        path = os.path.join(dest, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    for name in WHITELIST:
        src = os.path.join(root, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, name), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, os.path.join(dest, name))
    sha = _git(root, "rev-parse", "--short", "HEAD").strip()
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", f"Release {version(root)} (private {sha})")


def main(args):
    try:
        if len(args) == 2 and args[0] == "stamp":
            stamp(args[1])
            print(f"stamped {args[1]}: commit it, then run publish.py PUBLIC_CHECKOUT")
        elif len(args) == 1:
            publish(os.path.abspath(args[0]))
            print(f"committed release {version()} in {args[0]}: push it from there")
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except (PublishError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
