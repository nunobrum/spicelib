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
# Name:        ltspice_simulator.py
# Purpose:     Represents a LTspice tool and it's command line options
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import sys
import os

from pathlib import Path
from typing import Union
import logging
from ..sim.simulator import Simulator, run_function, SpiceSimulatorError
import subprocess

_logger = logging.getLogger("spicelib.LTSpiceSimulator")


class LTspice(Simulator):
    """Stores the simulator location and command line options and is responsible for generating netlists and running
    simulations."""

    """Searches on the any usual locations for a simulator"""
    # windows paths (that are also valid for wine)
    # Please note that os.path.expanduser and os.path.join are sensitive to the style of slash.
    # Placed in order of preference. The first to be found will be used.
    _spice_exe_win_paths = ["~/AppData/Local/Programs/ADI/LTspice/LTspice.exe",
                            "~/Local Settings/Application Data/Programs/ADI/LTspice/LTspice.exe",
                            "C:/Program Files/ADI/LTspice/LTspice.exe",
                            "C:/Program Files/LTC/LTspiceXVII/XVIIx64.exe",
                            "C:/Program Files (x86)/LTC/LTspiceXVII/XVIIx64.exe",
                            "C:/Program Files (x86)/LTC/LTspiceIV/scad3.exe"
                            ]
    
    # the default lib paths, as used by get_default_library_paths
    _default_lib_paths = ["~/AppData/Local/LTspice/lib",
                          "~/Documents/LTspiceXVII/lib/",
                          "~/Documents/LTspice/lib/",
                          "~/My Documents/LTspiceXVII/lib/",
                          "~/My Documents/LTspice/lib/",
                          "~/Local Settings/Application Data/LTspice/lib"]
    
    # defaults:
    spice_exe = []
    process_name = None       
    
    if sys.platform == "linux" or sys.platform == "darwin":
        # Linux: look for wine and ltspice under wine.
        # MacOS: give preference to wine. If not found: look for native LTspice
        
        # Anything specified in environment variables?
        spice_folder = os.environ.get("LTSPICEFOLDER")
        spice_executable = os.environ.get("LTSPICEEXECUTABLE")

        if spice_folder and spice_executable:
            spice_exe = ["wine", os.path.join(spice_folder, spice_executable)]
            process_name = spice_executable
        elif spice_folder:
            spice_exe = ["wine", os.path.join(spice_folder, "/XVIIx64.exe")]
            process_name = "XVIIx64.exe"
        elif spice_executable:
            default_folder = os.path.expanduser(
                "~/.wine/drive_c/Program Files/LTC/LTspiceXVII"
            )
            spice_exe = ["wine", os.path.join(default_folder, spice_executable)]
            process_name = spice_executable
        else:
            # This is still "linux or darwin"
            # no environment variables was given. Do a search.
            for exe in _spice_exe_win_paths:
                # make the file path wine compatible
                # Note that wine also accepts paths like 'C:\users\myuser\...'.
                # BUT, if I do that, I would not be able to check for the presence of the exe.
                # So: expand everything.                 
                # Linux would use this: 
                #    '/home/myuser/.wine/drive_c/users/myuser/AppData/...'  for _spice_exe_win_paths[0]
                # or '/home/myuser/.wine/drive_c/Program Files/...'         for _spice_exe_win_paths[2]
                # MacOS would use this: 
                #    '/Users/myuser/.wine/drive_c/users/myuser/AppData/...' for _spice_exe_win_paths[0]    
                # or '/Users/myuser/.wine/drive_c/Program Files/...'        for _spice_exe_win_paths[2]  
                # Note that in the user path versions (_spice_exe_win_paths[0] and [1]), I have 2 expansions of the user name.
                if exe.startswith("~"):
                    exe = "C:/users/" + os.path.expandvars("${USER}" + exe[1:])
                # Now I have a "windows" path (but with forward slashes). Make it into a path under wine.
                exe = os.path.expanduser(exe.replace("C:/", "~/.wine/drive_c/"))
                
                if os.path.exists(exe):
                    spice_exe = ["wine", exe]
                    # Note that one easy method of killing a wine process is to run "wineserver -k", 
                    # but we kill via psutil....kill(), as that would also fit non-wine executions.
                    
                    break
            else:
                # The else block will not be executed if the loop is stopped by a break statement.
                # in case of MacOS, try the native LTspice as last resort
                if sys.platform == "darwin":
                    exe = '/Applications/LTspice.app/Contents/MacOS/LTspice'
                    if os.path.exists(exe):
                        spice_exe = [exe]
                                
    else:  # Windows (well, also aix, wasi, emscripten,... where it will fail.)
        for exe in _spice_exe_win_paths:
            if exe.startswith("~"):
                # expand here, as I use _spice_exe_win_paths also for linux, and expanding earlier will fail
                exe = os.path.expanduser(exe)
            if os.path.exists(exe):
                spice_exe = [exe]
                break
    
    # The following variables are not needed anymore. This also makes sphinx not mention them in the documentation.
    del exe
    if sys.platform == "linux" or sys.platform == "darwin":
        del spice_folder
        del spice_executable
            
    # fall through        
    if len(spice_exe) == 0:
        spice_exe = []
        process_name = None
    else:
        process_name = Simulator.guess_process_name(spice_exe[0])
        _logger.debug(f"Found LTspice installed in: '{spice_exe}' ")

    ltspice_args = {
        '-alt'                : ['-alt'],  # Set solver to Alternate.
        '-ascii'              : ['-ascii'],  # Use ASCII.raw files. Seriously degrades program performance.
        # 'batch'            : ['-b <path>'], # Used by run command: Run in batch mode.E.g. "ltspice.exe-b deck.cir" will leave the data infile deck.raw
        '-big'                : ['-big'],  # Start as a maximized window.
        '-encrypt'            : ['-encrypt'],
        # Encrypt a model library.For 3rd parties wishing to allow people to use libraries without
        # revealing implementation details. Not used by AnalogDevices models.
        '-fastaccess'         : ['-FastAccess'],  # Batch conversion of a binary.rawfile to Fast Access format.
        '-FixUpSchematicFonts': ['-FixUpSchematicFonts'],
        # Convert the font size field of very old user - authored schematic text to the modern default.
        '-FixUpSymbolFonts'   : ['-FixUpSymbolFonts'],
        # Convert the font size field of very old user - authored symbols to the modern default.
        # See Changelog.txt for application hints.
        '-ini'                : ['- ini', '<path>'],  # Specify an .ini file to use other than %APPDATA%\LTspice.ini
        '-I'                  : ['-I<path>'],  # Specify a path to insert in the symbol and file search paths.
        # Must be the last specified option.
        # No space between "-I" and < path > is allowed.
        '-max'                : ['-max'],  # Synonym for -big
        '-netlist'            : ['-netlist'],  # Batch conversion of a schematic to a netlist.
        '-norm'               : ['-norm'],  # Set solver to Normal.
        '-PCBnetlist': ['-PCBnetlist'],  # Batch conversion of a schematic to a PCB format netlist.
        # 'run'              : ['-Run', '-b', '{path}'],  # Start simulating the schematic opened on the command line without
        # pressing the Run button.
        '-SOI'                : ['-SOI'],  # Allow MOSFET's to have up to 7 nodes even in subcircuit expansion.
        '-sync'               : ['-sync'],  # Update component libraries
        # '-uninstall'          : ['-uninstall'],  # Please don't. Executes one step of the uninstallation process. >> Not used in this implementation.
    }
    """:meta private:"""
    
    _default_run_switches = ['-Run', '-b']    

    @classmethod
    def using_macos_native_sim(cls) -> bool:
        """Tells if the simulator used is the MacOS native LTspice

        :return: True if the MacOS native LTspice is used, False otherwise (will also return False on Windows or Linux)
        :rtype: bool
        """
        return sys.platform == "darwin" and cls.spice_exe and "wine" not in cls.spice_exe[0].lower()

    @classmethod
    def valid_switch(cls, switch: str, path: str = '') -> list:
        """
        Validates a command line switch. The following options are available for Windows/wine LTspice:

        * `-alt`: Set solver to Alternate.
        * `-ascii`: Use ASCII.raw files. Seriously degrades program performance.
        * `-encrypt`: Encrypt a model library.For 3rd parties wishing to allow people to use libraries without revealing implementation details. Not used by AnalogDevices models.
        * `-fastaccess`: Batch conversion of a binary.rawfile to Fast Access format.
        * `-FixUpSchematicFonts`: Convert the font size field of very old user - authored schematic text to the modern default.
        * `-FixUpSymbolFonts`: Convert the font size field of very old user - authored symbols to the modern default. See Changelog.txt for application hints.
        * `-ini <path>`: Specify an .ini file to use other than %APPDATA%\\LTspice.ini
        * `-I<path>`: Specify a path to insert in the symbol and file search paths. Must be the last specified option.
        * `-netlist`: Batch conversion of a schematic to a netlist.
        * `-normal`: Set solver to Normal.
        * `-PCBnetlistBatch`: Conversion of a schematic to a PCB format netlist.
        * `-SOI`: Allow MOSFET's to have up to 7 nodes even in subcircuit expansion.
        * `-sync`: Update component libraries
            
        The following parameters will already be filled in by spicelib, and cannot be set:
        
        * `-Run`: Start simulating the schematic opened on the command line without pressing the Run button.
        * `-b`: Run in batch mode.
                
        MacOS native LTspice accepts no command line switches (yet), use it under wine for full support.

        :param switch: switch to be added.
        :type switch: str
        :param path: path to the file related to the switch being given.
        :type path: str, optional
        :return: Nothing
        """
        
        # See if the MacOS simulator is used. If so, check if I use the native simulator
        if cls.using_macos_native_sim():
            # this is the native LTspice. It has no useful command line switches (except '-b').
            raise ValueError("MacOS native LTspice does not support command line switches. Use it under wine for full support.")
            
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
            
        if switch in cls.ltspice_args:
            switches = cls.ltspice_args[switch]
            switches = [switch.replace('<path>', path) for switch in switches]
            return switches
        else:
            raise ValueError(f"Invalid Switch '{switch}'")

    @classmethod
    def run(cls, netlist_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None, 
            stdout=None, stderr=None,
            exe_log: bool = False) -> int:
        """Executes a LTspice simulation run.
        
        A raw file and a log file will be generated, with the same name as the netlist file, 
        but with `.raw` and `.log` extension.        

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
            _logger.error("Unable to find a LTspice executable.")
            _logger.error("A specific location of the LTSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")
        
        if cmd_line_switches is None:
            cmd_line_switches = []
        elif isinstance(cmd_line_switches, str):
            cmd_line_switches = [cmd_line_switches]
        netlist_file = Path(netlist_file)
        
        # cannot set raw and log file names or extensions. They are always '<netlist_file>.raw' and '<netlist_file>.log'
        
        if sys.platform == "linux" or sys.platform == "darwin":
            if cls.using_macos_native_sim():
                # native MacOS simulator, which has its limitations
                if netlist_file.suffix.lower().endswith(".asc"):
                    raise NotImplementedError("MacOS native LTspice cannot run simulations on '.asc' files. Simulate '.net' or '.cir' files or use LTspice under wine.")
                
                cmd_run = cls.spice_exe + ['-b'] + [netlist_file.as_posix()] + cmd_line_switches
            else:
                # wine
                # Drive letter 'Z' is the link from wine to the host platform's root directory. 
                # Z: is needed for netlists with absolute paths, but will also work with relative paths.
                cmd_run = cls.spice_exe + ['-Run'] + ['-b'] + ['Z:' + netlist_file.as_posix()] + cmd_line_switches
        else:
            # Windows (well, also aix, wasi, emscripten,... where it will fail.)
            cmd_run = cls.spice_exe + ['-Run'] + ['-b'] + [netlist_file.as_posix()] + cmd_line_switches
        # start execution
        if exe_log:
            log_exe_file = netlist_file.with_suffix('.exe.log')            
            with open(log_exe_file, "w") as outfile:
                error = run_function(cmd_run, timeout=timeout, stdout=outfile, stderr=subprocess.STDOUT)
        else:        
            error = run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
        return error

    @classmethod
    def create_netlist(cls, circuit_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None, 
                       stdout=None, stderr=None, 
                       exe_log: bool = False) -> Path:
        """Create a netlist out of the circuit file

        :param circuit_file: path to the circuit file
        :type circuit_file: Union[str, Path]
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
        :raises NotImplementedError: when the requested execution is not possible on this platform.
        :raises RuntimeError: when the netlist cannot be created
        :return: path to the netlist produced
        :rtype: Path
        """
        # prepare instructions, two stages used to enable edits on the netlist w/o open GUI
        # see: https://www.mikrocontroller.net/topic/480647?goto=5965300#5965300
        if cmd_line_switches is None:
            cmd_line_switches = []
        elif isinstance(cmd_line_switches, str):
            cmd_line_switches = [cmd_line_switches]
        circuit_file = Path(circuit_file)
        
        if cls.using_macos_native_sim():
            # native MacOS simulator
            raise NotImplementedError("MacOS native LTspice does not have netlist generation capabilities. Use LTspice under wine.")
        
        cmd_netlist = cls.spice_exe + ['-netlist'] + [circuit_file.as_posix()] + cmd_line_switches
        if exe_log:
            log_exe_file = circuit_file.with_suffix('.exe.log')            
            with open(log_exe_file, "w") as outfile:
                error = run_function(cmd_netlist, timeout=timeout, stdout=outfile, stderr=subprocess.STDOUT)
        else:
            error = run_function(cmd_netlist, timeout=timeout, stdout=stdout, stderr=stderr)

        if error == 0:
            netlist = circuit_file.with_suffix('.net')
            if netlist.exists():
                _logger.debug("OK")
                return netlist
        msg = "Failed to create netlist"
        _logger.error(msg)
        raise RuntimeError(msg)
