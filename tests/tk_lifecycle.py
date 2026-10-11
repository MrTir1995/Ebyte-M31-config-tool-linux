"""Dispose completed desktop fixtures on the interpreter's owning thread."""

import gc
import threading
from unittest.mock import Mock

from m31tool.app import tk


def release_tk_fixture(fixture):
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Tk fixtures must be disposed on the main thread.")
    # Mock call histories can form cycles containing dialog parent/root objects.
    # Run after patch cleanups, release fixture owners, then collect on Tk's thread.
    for name in list(vars(fixture)):
        value = getattr(fixture, name)
        if isinstance(value, Mock):
            value.reset_mock(return_value=True, side_effect=True)
        if isinstance(value, (tk.Misc, tk.Variable)):
            delattr(fixture, name)
        del value
    gc.collect()
