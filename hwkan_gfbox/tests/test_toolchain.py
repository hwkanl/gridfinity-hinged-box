import os

from hwkan_gfbox.fcmain import script_args


def _with_fc_args(value, fn):
    old = os.environ.pop("FC_ARGS", None)
    try:
        if value is not None:
            os.environ["FC_ARGS"] = value
        return fn()
    finally:
        os.environ.pop("FC_ARGS", None)
        if old is not None:
            os.environ["FC_ARGS"] = old


def test_script_args_splits_shell_quoting():
    # exactly what scripts/fc.sh produces for: --set gf_x=4 --part "lid x"
    got = _with_fc_args(r"--set gf_x=4 --part lid\ x ", script_args)
    assert got == ["--set", "gf_x=4", "--part", "lid x"], got


def test_script_args_empty_without_fc_args():
    assert _with_fc_args(None, script_args) == []
