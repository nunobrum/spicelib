#!/usr/bin/env python
# coding=utf-8

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        run_task.py
# Purpose:     Class used for a spice tool using a process call
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""
Internal classes not to be used directly by the user
"""
__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2023, Fribourg Switzerland"

from copy import copy
from pathlib import Path
import threading
import time
import traceback
from time import sleep
from typing import Callable, Union, Any, Type, Optional
import logging

from ..editor.updates import Updates, UpdateValueType

from .process_callback import ProcessCallback
from .simulator import Simulator

_logger = logging.getLogger("spicelib.RunTask")

END_LINE_TERM = '\n'


def format_time_difference(time_diff):
    """Formats the time difference in a human-readable format, stripping the hours or minutes if they are zero"""
    seconds_difference = int(time_diff)
    milliseconds = int((time_diff - seconds_difference) * 1000)
    hours, remainder = divmod(seconds_difference, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours == 0:
        if minutes == 0:
            return f"{int(seconds):02d}.{milliseconds:04d} secs"
        else:
            return f"{int(minutes):02d}:{int(seconds):02d}.{milliseconds:04d}"
    else:
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{milliseconds:04d}"


class RunTask(threading.Thread):
    """This is an internal Class and should not be used directly by the User."""

    def __init__(self, simulator: Type[Simulator], runno, netlist_file: Path,
                 callback: Optional[Union[Type[ProcessCallback], Callable[[Optional[Path], Optional[Path]], Any]]],
                 callback_args: Union[dict, None] = None,
                 switches: Any = None, timeout: Union[float, None] = None, verbose: bool = False,
                 cwd: Union[str, Path, None] = None,
                 callback_on_error: bool = False,
                 exe_log: bool = False):

        super().__init__(name=f"RunTask#{runno}")
        self.start_time = None
        self.stop_time = None
        self.verbose = verbose
        self.switches = switches
        self.timeout = timeout  # Thanks to Daniel Phili for implementing this
        self.simulator = simulator
        self.runno = runno
        self.netlist_file = netlist_file
        self.callback = callback
        self.callback_args = callback_args
        self.callback_on_error = callback_on_error
        self.cwd = cwd
        self.retcode = -1  # Signals an error by default
        self.raw_file = None
        self.log_file = None
        self.callback_return = None
        self.exe_log = exe_log
        self.exception_text = None
        self._edits = None

    @property
    def edits(self) -> Optional[Updates]:
        return self._edits

    @edits.setter
    def edits(self, netlist_updates: Updates):
        self._edits = copy(netlist_updates)

    def value(self, reference) -> UpdateValueType:
        if not self._edits:
            return None
        return self._edits.value(reference)

    def print_info(self, logger_fun: Callable[[str], None], message: str):
        message = f"RunTask #{self.runno}:{message}"
        logger_fun(message)
        if self.verbose:
            print(f"{time.asctime()} {logger_fun.__name__}: {message}{END_LINE_TERM}")

    def run(self):
        # Running the Simulation

        self.callback_return = None
        self.raw_file = None
        self.log_file = None
        
        self.start_time = time.time()
        self.print_info(_logger.info, ": Starting simulation %d: %s" % (self.runno, self.netlist_file))
        # start execution
        try:
            self.retcode = self.simulator.run(self.netlist_file.absolute().as_posix(), self.switches,
                                              self.timeout, cwd=self.cwd, exe_log=self.exe_log)
        except Exception as e:
            self.exception_text = f"{e.__class__.__name__}: {e}"
            self.retcode = -2
            self.print_info(_logger.error, f"Simulation Failed. {self.exception_text}")
        self.stop_time = time.time()
        # print simulation time with format HH:MM:SS.mmmmmm

        # Calculate the time difference
        sim_time = format_time_difference(self.stop_time - self.start_time)
        # Format the time difference
        self.log_file = self.netlist_file.with_suffix('.log')
        
        some_error = False

        # Cleanup everything
        if self.retcode == 0:
            self.raw_file = self.netlist_file.with_suffix(self.simulator.raw_extension)
            if self.raw_file.exists() and self.log_file.exists():
                # simulation successful
                self.print_info(_logger.info, "Simulation Successful. Time elapsed: %s" % sim_time)
            else:
                self.print_info(_logger.error, "Simulation Raw file or Log file were not found")
                some_error = True
        else:
            # simulation failed
            some_error = True
            self.print_info(_logger.error, "Simulation Aborted. Time elapsed: %s" % sim_time)
            if self.log_file.exists():
                self.log_file = self.log_file.replace(self.log_file.with_suffix('.fail'))

        # Do I need to use callback?
        if self.callback and (self.callback_on_error or not some_error):
            # If the callback function is defined and callback_on_error is True, call the callback function
            # even if the simulation failed
            if self.callback_args is not None:
                callback_print = ', '.join([f"{key}={value}" for key, value in self.callback_args.items()])
            else:
                callback_print = ''
            self.print_info(_logger.info, f"Simulation Finished. Calling...{self.callback.__name__}(rawfile, logfile{callback_print})")
            try:
                if self.callback_args is not None:
                    return_or_process = self.callback(self.raw_file, self.log_file, **self.callback_args)
                else:
                    return_or_process = self.callback(self.raw_file, self.log_file)
            except Exception:
                error = traceback.format_exc()
                self.print_info(_logger.error, error)
            else:
                if isinstance(return_or_process, ProcessCallback):
                    proc = return_or_process
                    proc.start()
                    self.callback_return = proc.queue.get()
                    proc.join()
                else:
                    self.callback_return = return_or_process
            finally:
                callback_start_time = self.stop_time
                self.stop_time = time.time()
                self.print_info(_logger.info, "Simulation Callback Finished. Time elapsed: %s" % format_time_difference(
                    self.stop_time - callback_start_time))
        else:
            self.print_info(_logger.debug, "Simulation Callback not called.")
            self.callback_return = None

    def get_results(self) -> Union[None, Any, tuple[str, str]]:
        """
        Returns the simulation outputs if the simulation and callback function has already finished.
        If the simulation is not finished, it simply returns None. If no callback function is defined, then
        it returns a tuple with (raw_file, log_file).
        If a callback function is defined, it returns whatever the callback function is returning, unless
        the simulation failed, and `callback_on_error` is False (default), in which case it returns None.

        :returns: Tuple with the path to the raw file and the path to the log file
        :rtype: tuple(str, str) or None
        """
        if self.is_alive() or self.start_time is None:  # running or not yet started
            return None

        if self.callback:
            return self.callback_return  # callback_return is guaranteed to be set correctly by `run()`
        else:
            return self.raw_file, self.log_file

    def wait_results(self) -> Union[Any, tuple[str, str]]:
        """
        Waits for the completion of the task and returns a tuple with the raw and log files.
        
        :returns: Tuple with the path to the raw file and the path to the log file. See get_results() for more details.
        :rtype: tuple(str, str)
        """
        while self.is_alive() or self.start_time is None or self.retcode == -1:
            sleep(0.1)
        return self.get_results()
