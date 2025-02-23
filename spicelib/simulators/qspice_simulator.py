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
# Name:        qspice_simulator.py
# Purpose:     Represents QSPICE
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     26-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import sys
import os

from pathlib import Path
from typing import Union
import logging
from ..sim.simulator import Simulator, run_function, SpiceSimulatorError
import subprocess

_logger = logging.getLogger("spicelib.QSpiceSimulator")


class Qspice(Simulator):
    """Stores the simulator location and command line options and is responsible for generating netlists and running
    simulations."""
    
    raw_extension = '.qraw'
    """:meta private:"""
    
    #
    # In QSPICE all traces have double precision. This means that qraw files are not compatible
    # with LTSPICE
    
    # windows paths (that are also valid for wine)
    # Please note that os.path.expanduser and os.path.join are sensitive to the style of slash.
    # Placed in order of preference. The first to be found will be used.
    _spice_exe_win_paths = ["~/Qspice/QSPICE64.exe",
                            "~/AppData/Local/Programs/Qspice/QSPICE64.exe",
                            "C:/Program Files/QSPICE/QSPICE64.exe"]
    
    # the default lib paths, as used by get_default_library_paths
    _default_lib_paths = ["C:/Program Files/QSPICE",
                          "~/Documents/QSPICE"]

    """Searches on the any usual locations for a simulator"""
    # defaults:
    spice_exe = []
    process_name = None  
        
    if sys.platform == "linux" or sys.platform == "darwin":
        # status mid 2024: Qspice has limited support for running under linux+wine, and none for MacOS+wine
        # TODO: when the situation gets more mature, add support for wine. See LTspice for an example.
        spice_exe = []
        process_name = None
    else:  # Windows (well, also aix, wasi, emscripten,... where it will fail.)
        for exe in _spice_exe_win_paths:
            if exe.startswith("~"):
                # expand here, as I use _spice_exe_win_paths also for linux, and expanding earlier will fail
                exe = os.path.expanduser(exe)
            if os.path.exists(exe):
                spice_exe = [exe]
                break        

    # fall through        
    if len(spice_exe) == 0:
        spice_exe = []
        process_name = None
    else:
        process_name = Simulator.guess_process_name(spice_exe[0])        
        _logger.debug(f"Found Qspice installed in: '{spice_exe}' ")

    qspice_args = {
        '-ASCII'     : ['-ASCII'],  # Use ASCII file format for the output data(.qraw) file.
        '-ascii'     : ['-ASCII'],  # lowercase also works. Not sure about the others, so keep it this way.
        '-binary'    : ['-binary'],  # Use binary file format for the output data(.qraw) file.
        '-BSIM1'    : ['-BSIM1'],  # Use the charge-conserving BSIM1 charge model for MOS1, MOS2, and MOS3.
        '-Meyer'    : ['-Meyer'],  # Use the Meyer Capacitance model for MOS1, MOS2, and MOS3.
        '-o'         : ['-o', '<path>'],  # Specify the name of a file for the console output.
        # '-p'         : ['-p'],  # Take the netlist piped from stdin. >> Not used in this implementation.
        '-ProtectSelections': ['-ProtectSelections', '<path>'],  # Protect sections marked with .prot/.unprot with encryption.
        '-ProtectSubcircuits': ['-ProtectSubcircuits', '<path>'],  # Protect the body of subcircuits with encryption.
        '-r'       : ['-r', '<path>'],  # Specify the name of the output data(.qraw) file.
    }
    """:meta private:"""
    
    _default_run_switches = ['-o']
    

    @classmethod
    def valid_switch(cls, switch: str, path: str = '') -> list:
        """
        Validates a command line switch. The following options are available for QSPICE:
        
        * `-ASCII`: Use ASCII file format for the output data(.qraw) file.
        * `-binary`: Use binary file format for the output data(.qraw) file.
        * `-BSIM1`: Use the charge-conserving BSIM1 charge model for MOS1, MOS2, and MOS3.
        * `-Meyer`: Use the Meyer Capacitance model for MOS1, MOS2, and MOS3.
        * `-ProtectSelections <path>`: Protect sections marked with .prot/.unprot with encryption.
        * `-ProtectSubcircuits <path>`: Protect the body of subcircuits with encryption.
        * `-r <path>`: Specify the name of the output data(.qraw) file.
        
        The following parameters will already be filled in by spicelib, and cannot be set:

        * `-o <path>`: Specify the name of a file for the console output.
        
        :param switch: switch to be added.
        :type switch: str
        :param path: path to the file related to the switch being given.
        :type path: str, optional
        :return: Nothing
        """
        
        # format check
        if switch is None:
            return []
        switch = switch.strip()
        if len(switch) == 0:
            return []
        if switch[0] != '-':
            switch = '-' + switch
        
        # will be set anyway?
        if switch in cls._default_run_switches:
            _logger.info(f"Switch {switch} is already in the default switches")
            return []        
        
        # read from the dictionary
        if switch in cls.qspice_args:
            switches = cls.qspice_args[switch]
            switches = [switch.replace('<path>', path) for switch in switches]
            return switches
        else:
            raise ValueError(f"Invalid Switch '{switch}'")

    @classmethod
    def run(cls, netlist_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None, 
            stdout=None, stderr=None,
            exe_log: bool = False) -> int:
        """Executes a Qspice simulation run.
        
        A raw file and a log file will be generated, with the same name as the netlist file, 
        but with `.qraw` and `.log` extension. You can however change the raw file name using the `-r` switch.

        :param netlist_file: path to the netlist file
        :type netlist_file: Union[str, Path]
        :param cmd_line_switches: additional command line options. Best to have been validated by valid_switch(), defaults to None
        :type cmd_line_switches: list, optional
        :param timeout: If timeout is given, and the process takes too long, a TimeoutExpired exception will be raised, defaults to None
        :type timeout: float, optional
        :param stdout: control redirection of the command's stdout. Valid values are None, subprocess.PIPE, subprocess.DEVNULL, an existing file descriptor (a positive integer), 
            and an existing file object with a valid file descriptor. 
            With the default settings of None, no redirection will occur. Also see `exe_log` for a simpler form of control.
        :type stdout: _FILE, optional
        :param stderr: Like stdout, but affecting the command's error output. Also see `exe_log` for a simpler form of control.
        :type stderr: _FILE, optional
        :param exe_log: If True, stdout and stderr will be ignored, and the simulator's execution console messages will be written to a log file 
            (named ...exe.log) instead of console. This is especially useful when running under wine or when running simultaneous tasks.
        :type exe_log: bool, optional            
        :raises SpiceSimulatorError: when the executable is not found.
        :raises NotImplementedError: when the requested execution is not possible on this platform.
        :return: return code from the process
        :rtype: int
        """
        if not cls.is_available():
            _logger.error("================== ALERT! ====================")
            _logger.error("Unable to find the QSPICE executable.")
            _logger.error("A specific location of the QSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")
        
        if cmd_line_switches is None:
            cmd_line_switches = []
        elif isinstance(cmd_line_switches, str):
            cmd_line_switches = [cmd_line_switches]
        netlist_file = Path(netlist_file).absolute()  # need absolute path, as early 2025 qspice has a strange repetition bug
                
        log_file = Path(netlist_file).with_suffix('.log').as_posix()
        cmd_run = cls.spice_exe + ['-o', log_file] + [netlist_file.as_posix()] + cmd_line_switches
        # start execution
        if exe_log:
            log_exe_file = netlist_file.with_suffix('.exe.log')
            with open(log_exe_file, "w") as outfile:
                error = run_function(cmd_run, timeout=timeout, stdout=outfile, stderr=subprocess.STDOUT)
        else:        
            error = run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
        return error
