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

from pathlib import Path, PureWindowsPath
from typing import Union
import logging
from ..sim.simulator import Simulator, run_function, SpiceSimulatorError

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
                            "C:/Program Files (x86)/LTC/LTspiceIV/scad3.exe"
                            ]
    
    # the default lib paths, as used by get_library_paths
    _default_lib_paths = ["~/AppData/Local/LTspice/lib",
                          "~/Documents/LtspiceXVII/lib/",
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
                    # process_name is used for kill_all_spice()
                    if sys.platform == "darwin":
                        # For MacOS wine, there will be no process called "wine". Use "wine-preloader"
                        process_name = "wine-preloader"
                    else:
                        process_name = Path(exe).name  
                    # Note that one easy method of killing a wine process is to run "wineserver -k", 
                    # but we kill via psutil....kill(), as that would also fit non-wine executions.
                    
                    break
            else:
                # The else block will not be executed if the loop is stopped by a break statement.
                # in case of MacOS, try the native LTspice
                if sys.platform == "darwin":
                    exe = '/Applications/LTspice.app/Contents/MacOS/LTspice'
                    if os.path.exists(exe):
                        spice_exe = [exe]
                        process_name = "LTspice"
                                
    else:  # Windows (well, also aix, wasi, emscripten,... where it will fail.)
        for exe in _spice_exe_win_paths:
            if exe.startswith("~"):
                # expand here, as I use _spice_exe_win_paths also for linux, and expanding earlier will fail
                exe = os.path.expanduser(exe)
            if os.path.exists(exe):
                spice_exe = [exe]
                process_name = Path(exe).name
                break
            
    # fall through        
    if len(spice_exe) == 0:
        spice_exe = []
        process_name = None
    else:
        _logger.debug(f"Found LTspice installed in: '{spice_exe}' ")

    ltspice_args = {
        'alt'                : ['-alt'],  # Set solver to Alternate.
        'ascii'              : ['-ascii'],  # Use ASCII.raw files. Seriously degrades program performance.
        # 'batch'            : ['-b <path>'], # Used by run command: Run in batch mode.E.g. "ltspice.exe-b deck.cir" will leave the data infile deck.raw
        'big'                : ['-big'],  # Start as a maximized window.
        'encrypt'            : ['-encrypt'],
        # Encrypt a model library.For 3rd parties wishing to allow people to use libraries without
        # revealing implementation details. Not used by AnalogDevices models.
        'fastaccess'         : ['-FastAccess'],  # Batch conversion of a binary.rawfile to Fast Access format.
        'FixUpSchematicFonts': ['-FixUpSchematicFonts'],
        # Convert the font size field of very old user - authored schematic text to the modern default.
        'FixUpSymbolFonts'   : ['-FixUpSymbolFonts'],
        # Convert the font size field of very old user - authored symbols to the modern default.
        # See Changelog.txt for application hints.
        'ini'                : ['- ini', '<path>'],  # Specify an .ini file to use other than %APPDATA%\LTspice.ini
        'I'                  : ['-I<path>'],  # Specify a path to insert in the symbol and file search paths.
        # Must be the last specified option.
        # No space between "-I" and < path > is allowed.
        'max'                : ['-max'],  # Synonym for -big
        'netlist'            : ['-netlist'],  # Batch conversion of a schematic to a netlist.
        'norm'               : ['-norm'],  # Set solver to Normal.
        'PCBnetlist': ['-PCBnetlist'],  # Batch conversion of a schematic to a PCB format netlist.
        # 'run'              : ['-Run', '-b', '{path}'],  # Start simulating the schematic opened on the command line without
        # pressing the Run button.
        'SOI'                : ['-SOI'],  # Allow MOSFET's to have up to 7 nodes even in subcircuit expansion.
        'sync'               : ['-sync'],  # Update component libraries
        'uninstall'          : ['-uninstall'],  # Please don't. Executes one step of the uninstallation process.
    }

    @classmethod
    def using_macos_native_sim(cls) -> bool:
        return sys.platform == "darwin" and cls.spice_exe and "wine" not in cls.spice_exe[0].lower()

    @classmethod
    def valid_switch(cls, switch, path='') -> list:
        """
        Validates a command line switch. The following options are available for Windows/wine LTspice:

            * 'alt' : Set solver to Alternate.

            * 'ascii'     : Use ASCII.raw files. Seriously degrades program performance.

            * 'encrypt'   : Encrypt a model library.For 3rd parties wishing to allow people to use libraries without
                            revealing implementation details. Not used by AnalogDevices models.

            * 'fastaccess': Batch conversion of a binary.rawfile to Fast Access format.

            * 'FixUpSchematicFonts' : Convert the font size field of very old user - authored schematic text to the
                                    modern default.

            * 'FixUpSymbolFonts' : Convert the font size field of very old user - authored symbols to the modern
                default. See Changelog.txt for application hints.

            * 'ini <path>' : Specify an .ini file to use other than %APPDATA%\\LTspice.ini

            * 'I<path>' : Specify a path to insert in the symbol and file search paths. Must be the last specified
                option.

            * 'netlist'   :  Batch conversion of a schematic to a netlist.

            * 'normal'    :  Set solver to Normal.

            * 'PCBnetlist':  Batch conversion of a schematic to a PCB format netlist.

            * 'SOI'       :  Allow MOSFET's to have up to 7 nodes even in subcircuit expansion.

            * 'sync'      : Update component libraries

            * 'uninstall' :  Executes one step of the uninstallation process. Please don't.
            
            MacOS native LTspice accepts no command line switches (yet). 


        :param switch: switch to be added. If the switch is not on the list above, it should be correctly formatted with
                       the preceding '-' switch
        :type switch: str
        :param path: path to the file related to the switch being given.
        :type path: str, optional
        :return: Nothing
        :rtype: None
        """
        
        # See if the MacOS simulator is used. If so, check if I use the native simulator
        if cls.using_macos_native_sim():
            # this is the native LTspice. It has no useful command line switches (except '-b').
            raise ValueError("MacOS native LTspice does not support command line switches. Use it under wine for full support.")
            
        if switch in cls.ltspice_args:
            switches = cls.ltspice_args[switch]
            switches = [switch.replace('<path>', path) for switch in switches]
            return switches
        else:
            raise ValueError("Invalid switch for class ")

    @classmethod
    def run(cls, netlist_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None, stdout=None, stderr=None):
        """Executes a LTspice simulation run.

        :param netlist_file: path to the netlist file
        :type netlist_file: Union[str, Path]
        :param cmd_line_switches: additional command line options. Best to have been validated by valid_switch(), defaults to None
        :type cmd_line_switches: list, optional
        :param timeout: If timeout is given, and the process takes too long, a TimeoutExpired exception will be raised, defaults to None
        :type timeout: float, optional
        :param stdout: control redirection of the command's stdout. Valid values are None, subprocess.PIPE, subprocess.DEVNULL, an existing file descriptor (a positive integer), and an existing file object with a valid file descriptor. With the default settings of None, no redirection will occur. 
        :type stdout: _FILE, optional
        :param stderr: Like stdout, but affecting the command's error output.
        :type stderr: _FILE, optional
        :raises SpiceSimulatorError: when the executable is not found.
        :raises NotImplementedError: when the requested execution is not possible on this platform.
        :return: return code from the process
        :rtype: int
        """
        netlist_file = Path(netlist_file)
        
        if not cls.spice_exe:
            _logger.error("================== ALERT! ====================")
            _logger.error("Unable to find a LTspice executable.")
            _logger.error("A specific location of the LTSPICE can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")
        
        if sys.platform == "linux" or sys.platform == "darwin":
            if cls.using_macos_native_sim():
                # native MacOS simulator, which has its limitations
                if netlist_file.lower().endswith(".asc"):
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
        return run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)

    @classmethod
    def create_netlist(cls, circuit_file: Union[str, Path], cmd_line_switches: list = None, stdout=None, stderr=None) -> Path:
        """Create a netlist out of the circuit file

        :param circuit_file: path to the circuit file
        :type circuit_file: Union[str, Path]
        :param cmd_line_switches: additional command line options. Best to have been validated by valid_switch(), defaults to None
        :type cmd_line_switches: list, optional
        :param stdout: control redirection of the command's stdout. Valid values are None, subprocess.PIPE, subprocess.DEVNULL, an existing file descriptor (a positive integer), and an existing file object with a valid file descriptor. With the default settings of None, no redirection will occur. 
        :type stdout: _FILE, optional
        :param stderr: Like stdout, but affecting the command's error output.
        :type stderr: _FILE, optional
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
        error = run_function(cmd_netlist, stdout=stdout, stderr=stderr)

        if error == 0:
            netlist = circuit_file.with_suffix('.net')
            if netlist.exists():
                _logger.debug("OK")
                return netlist
        msg = "Failed to create netlist"
        _logger.error(msg)
        raise RuntimeError(msg)
