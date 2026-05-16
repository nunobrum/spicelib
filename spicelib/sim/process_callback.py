#!/usr/bin/env python

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        process_callback.py
# Purpose:     Being able to execute callback in a separate process
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-04-2023
# License:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""

"""
from __future__ import annotations

from multiprocessing import Process, Queue
from typing import Any, TypeAlias
from collections.abc import Callable
from pathlib import Path


class ProcessCallback(Process):
    """
    Wrapper for the callback function
    """
    def __init__(self, raw, log, group=None, name=None, *, daemon: bool | None = ...,
                 **kwargs) -> None:
        super().__init__(group=group, name=name, daemon=daemon)
        self.queue = Queue()
        self.raw_file = raw
        self.log_file = log
        self.kwargs = kwargs

    def run(self):
        ret = self.callback(self.raw_file, self.log_file, **self.kwargs)
        if ret is None:
            ret = "Callback doesn't return anything"
        self.queue.put(ret)

    @staticmethod
    def callback(raw_file, log_file, **kwargs) -> Any:
        """This function needs to be overridden"""
        ...


CallbackArgsType: TypeAlias = tuple | dict | None
# A callback can be:
# - any callable that accepts arbitrary positional/keyword args (Callable[..., Any])
#   which covers plain functions and callable class instances;
# - or a ProcessCallback class/type (kept for backward compatibility if code
#   expects to receive a ProcessCallback subclass/type);
# - or None when no callback is provided.
CallbackType: TypeAlias = Callable[..., Any] | type[ProcessCallback] | None
