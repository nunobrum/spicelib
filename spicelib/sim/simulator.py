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
# Name:        simulator.py
# Purpose:     Creates a virtual class for representing all Spice Simulators
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

import sys
from abc import ABC, abstractmethod
from pathlib import Path, PureWindowsPath
from typing import Union, Optional, List
import subprocess
import os
import logging
import shutil
import shlex

_logger = logging.getLogger("spicelib.Simulator")

if sys.version_info.major >= 3 and sys.version_info.minor >= 6:
    def run_function(command, timeout=None, stdout=None, stderr=None):
        """Normalizing OS subprocess function calls between different platforms. This function is used for python 3.6
        and higher versions."""
        _logger.debug(f"Running command: {command}, with timeout: {timeout}")
        result = subprocess.run(command, timeout=timeout, stdout=stdout, stderr=stderr)
        return result.returncode

else:
    def run_function(command, timeout=None, stdout=None, stderr=None):
        """Normalizing OS subprocess function calls between different platforms. This is the old function that was used
        for python version prior to 3.6"""
        _logger.debug(f"Running command: {command}, with timeout: {timeout}")
        return subprocess.call(command, timeout=timeout, stdout=stdout, stderr=stderr)


class SpiceSimulatorError(Exception):
    """Generic Simulator Error Exceptions"""
    ...


class Simulator(ABC):
    """Pure static class template for Spice simulators. This class only defines the interface of the subclasses.
    The variables below shall be overridden by the subclasses. Instantiating this class will raise a SpiceSimulatorError
    exception.

    A typical subclass for a Windows installation is:

    .. code-block:: python

        class MySpiceWindowsInstallation(Simulator):
            spice_exe = ['<path to the spice executable>']
            process_name = "<name of the process on Windows Task Manager>"


    or on a Linux distribution:

    .. code-block:: python

        class MySpiceLinuxInstallation(Simulator):
            spice_exe = ['<wine_command>', '<path to the spice executable>']
            process_name = "<name of the process within the system>"


    If you use MacOS, you can choose either one of the 2 above. If you are on Intel, running LTSpice under wine (therefore: like under Linux) is preferred.


    The subclasses should then implement at least the run() function as a classmethod.
    
    .. code-block:: python
        
        @classmethod
        def run(cls, netlist_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None, stdout=None, stderr=None):
            '''This method implements the call for the simulation of the netlist file. '''
            cmd_run = cls.spice_exe + ['-Run'] + ['-b'] + [netlist_file] + cmd_line_switches
            return run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)


    The ``run_function()`` can be imported from the simulator.py with
    ``from spicelib.sim.simulator import run_function`` instruction.
    """
    
    spice_exe: List[str] = []
    """ The executable. If using a loader (like wine), make sure that the last in the array is the real simulator.
    
    :meta hide-value:"""
    
    process_name: str = ""  
    """ the name of the process in the task manager
    
    :meta hide-value:"""
    
    raw_extension = '.raw'  
    """:meta private:"""
    
    # the default lib paths, as used by get_default_library_paths
    _default_lib_paths = []

    @classmethod
    def create_from(cls, path_to_exe, process_name=None):
        """
        Creates a simulator class from a path to the simulator executable
        
        :param path_to_exe:
        :type path_to_exe: pathlib.Path or str. If it is a string, it supports multiple sections, 
            allowing loaders like wine, but MUST be in posix format in that case, and 
            the last section MUST be the simulator executable.
        :param process_name: the process_name to be used for killing phantom processes. If not provided, it will be 
        :return: a class instance representing the Spice simulator
        :rtype: Simulator
        """
        plib_path_to_exe = None
        exe_parts = []
        if isinstance(path_to_exe, Path) or os.path.exists(path_to_exe):
            if isinstance(path_to_exe, Path):
                plib_path_to_exe = path_to_exe
            else:
                plib_path_to_exe = Path(path_to_exe)
            exe_parts = [plib_path_to_exe.as_posix()]
        else:
            if '\\' in path_to_exe:  # this probably a windows path. Don't be smart here.
                # make the path into a posix path. Rather complicated gymnastics, but it works.
                # I do not support multiple sections here, as it is not likely needed.
                plib_path_to_exe = Path(PureWindowsPath(path_to_exe).as_posix())
                exe_parts = [plib_path_to_exe.as_posix()]
            else:
                # try to extract the parts
                exe_parts = shlex.split(path_to_exe)
                if len(exe_parts) > 0:
                    plib_path_to_exe = Path(exe_parts[0])
                    exe_parts[0] = plib_path_to_exe.as_posix()
                
        if plib_path_to_exe.exists() or shutil.which(plib_path_to_exe):
            if process_name is None:
                cls.process_name = cls.guess_process_name(exe_parts[0])
            else:
                cls.process_name = process_name
            cls.spice_exe = exe_parts
            return cls
        else:
            raise FileNotFoundError(f"Provided exe file was not found '{path_to_exe}'")
        
    @staticmethod
    def guess_process_name(exe: str) -> str:
        """Guess the process name based on the executable path"""
        if not exe:
            return ""
        if sys.platform == 'darwin':
            if "wine" in exe:
                # For MacOS wine, there will be no process called "wine". Use "wine-preloader"
                return "wine-preloader"
            else:
                return Path(exe).stem
        else:
            return Path(exe).name

    def __init__(self):
        raise SpiceSimulatorError("This class is not supposed to be instanced.")

    @classmethod
    @abstractmethod
    def run(cls, netlist_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None,
            stdout=None, stderr=None, exe_log: bool = False) -> int:
        """This method implements the call for the simulation of the netlist file. This should be overriden by its
        subclass."""
        raise SpiceSimulatorError("This class should be subclassed and this function should be overridden.")

    @classmethod
    @abstractmethod
    def valid_switch(cls, switch, switch_param) -> list:
        """This method validates that a switch exist and is valid. This should be overriden by its subclass."""
        ...

    @classmethod
    def is_available(cls):
        """This method checks if the simulator exists in the system. It will return a boolean value indicating if the
        simulator is installed or not."""
        if cls.spice_exe and len(cls.spice_exe) > 0:
            # check if file exists
            if Path(cls.spice_exe[0]).exists():
                return True
            # check if file in path
            if shutil.which(cls.spice_exe[0]):
                return True
        return False
    
    @classmethod
    def get_default_library_paths(cls) -> List[str]:
        """
        Return the directories that contain the standard simulator's libraries, 
        as derived from the simulator's executable path and platform.
        spice_exe must be set before calling this method.
        
        This is companion with `set_custom_library_paths()`

        :return: the list of paths where the libraries should be located.
        :rtype: List[str]
        """
        paths = []
        myexe = None
        # get the executable
        if cls.spice_exe and len(cls.spice_exe) > 0:
            # TODO: this will fail if the simulator executable is not in the last element of the list. Maybe make this more robust.
            if os.path.exists(cls.spice_exe[-1]):            
                myexe = cls.spice_exe[-1]
        _logger.debug(f"Using Spice executable path '{myexe}' to determine the correct library paths.")
        for path in cls._default_lib_paths:
            _logger.debug(f"Checking if library path '{path}' exists.")
            p = cls.expand_and_check_local_dir(path, myexe)
            if p is not None:
                _logger.debug(f"Adding path '{p}' to the library path list")
                paths.append(p)
        return paths
    
    @staticmethod
    def expand_and_check_local_dir(path: str, exe_path: str = None) -> Optional[str]:
        """
        Expands a directory path to become an absolute path, while taking into account a potential use under wine (under MacOS and Linux). 
        Will also check if that directory exists.
        The path must either be an absolute path or start with ~. Relative paths are not supported.
        On MacOS or Linux, it will try to replace any reference to the virtual windows root under wine into a host OS path.
        
        Examples:
        
        * under windows:
        
          * C:/mydir -> C:/mydir
          
          * ~/mydir -> C:/Users/myuser/mydir
          
        * under linux, and if the executable is /mywineroot/.wine/drive_c/(something):

          * C:/mydir -> /mywineroot/.wine/drive_c/mydir
          
          * ~/mydir -> /mywineroot/.wine/drive_c/users/myuser/mydir
        
        :param path: The path to expand. Must be in posix format, use `PureWindowsPath(path).as_posix()` to transform a windows path to a posix path.
        :type path: str
        :param exe_path: path to a related executable that may or may not be under wine, defaults to None, ignored on Windows
        :type exe_path: str, optional
        :return: the fully expanded path, as posix path, will return None if the path does not exist.
        :rtype: Optional[str]
        """
        c_drive = None
        # See if I'm under wine
        if sys.platform == "linux" or sys.platform == "darwin":
            if exe_path and "/drive_c/" in exe_path:
                # this is very likely a wine path
                c_drive = exe_path.split("/drive_c/")[0] + "/drive_c/"
        # if so: Translate C drive to the wine root
        if c_drive is not None:
            # this must be linux or darwin, with wine
            if path.startswith("~"):
                # Normally, a large number of directories in the home directory of a user under wine are symlinked 
                # to the user's home directory in the host OS. That would mean, that "~/Documents" under wine is 
                # normally also "~/Documents" under the host OS. But this is not always the case, and not for all directories. 
                # The user can have modified this, via for example a winetricks sandbox.
                # Therefore, I make it an absolute path for Windows and do not try to optimise:
                path = "C:/users/" + os.path.expandvars("${USER}" + path[1:])  
                # If I were to do this expansion under Windows, I should use ${USERNAME} but we're not in Windows here. 
                # I also cannot use expanduser(), as that again would be for the wrong OS.
                # All lowercase "users" is correct, as it is the default path for the user's home directory in wine.
            # I now have a "windows" path (but in posix form, with forward slashes). Make it into a host OS path.
            if path.startswith("C:/") or path.startswith("c:/"):
                path = c_drive + path[3:]  # should start with C:. If not, something is wrong. 
            # note that in theory, the exe path can be relative to the user's home directory, so...
            
        # and in all cases (Windows, MacOS, linux,...):
        # terminate with the expansion of the ~
        if path.startswith("~"):
            path = os.path.expanduser(path)
            
        # check existance and if it is a directory
        if os.path.exists(path) and os.path.isdir(path):
            return path
        return None
