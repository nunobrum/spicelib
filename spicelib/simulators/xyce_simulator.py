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
# Name:        xyce_simulator.py
# Purpose:     Tool used to launch xyce simulations in batch mode.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     14-03-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------

from pathlib import Path
from typing import Union
import logging
from ..sim.simulator import Simulator, run_function, SpiceSimulatorError
import os
import subprocess
import shutil

_logger = logging.getLogger("spicelib.XYCESimulator")


class XyceSimulator(Simulator):
    """Stores the simulator location and command line options and runs simulations."""
    # Placed in order of preference. The first to be found will be used.
    _spice_exe_paths = ["C:/Program Files/Xyce 7.9 NORAD/bin/xyce.exe",  # Windows
                        "xyce",  # linux, when in path
                        ]
    
    # the default lib paths, as used by get_default_library_paths
    # none
    _default_lib_paths = []
    
    # defaults:
    spice_exe = []
    process_name = None      
    
    # determine the executable to use
    for exe in _spice_exe_paths:
        if exe.startswith("~"):
            exe = os.path.expanduser(exe)
        if os.path.exists(exe):
            spice_exe = [exe]
            break
        else:
            # check if file in path
            if shutil.which(exe):
                spice_exe = [exe]
                break

    # The following variables are not needed anymore. This also makes sphinx not mention them in the documentation.
    del exe

    # fall through        
    if len(spice_exe) == 0:
        spice_exe = []
        process_name = None
    else:
        process_name = Simulator.guess_process_name(spice_exe[0])
        _logger.debug(f"Found xyce installed in: '{spice_exe}' ")
            
    xyce_args = {
        # '-b'                : ['-b'],  # batch mode flag for spice compatibility (ignored)
        # '-h'                : ['-h'],  # print usage and exit
        # '-v'                : ['-v'],  # print version info and exit
        '-capabilities'     : ['-capabilities'],  # print compiled-in options and exit
        '-license'          : ['-license'],  # print license and exit
        '-param'            : ['-param', '<param_options>'],
        # [device [level [<inst|mod>]]] print a terse summary of model and/or device parameters
        '-doc'              : ['-doc', '<param_options>'],
        # [device [level [<inst|mod>]]] output latex tables of model and device parameters to files
        '-doc_cat'          : ['-doc_cat', '<param_options>'],
        # [device [level [<inst|mod>]]] output latex tables of model and device parameters to files
        '-count'            : ['-count'],  # device count without netlist syntax or topology check
        '-syntax'           : ['-syntax'],  # check netlist syntax and exit
        '-norun'            : ['-norun'],  # netlist syntax and topology and exit
        '-namesfile'        : ['-namesfile', '<path>'],  # output internal names file to <path> and exit
        '-noise_names_file' : ['-noise_names_file', '<path>'],  # output noise source names file to <path> and exit
        '-quiet'            : ['-quiet'],  # suppress some of the simulation-progress messages sent to stdout
        '-jacobian_test'    : ['-jacobian_test'],  # jacobian matrix diagnostic
        '-hspice-ext'       : ['-hspice-ext', '<hsext_options>'],
        # apply hspice compatibility features during parsing.  option=all applies them all
        '-redefined_params' : ['-redefined_params', '<redef_param_option>'],
        # set option for redefined .params as ignore (use last), usefirst, warn or error
        '-subckt_multiplier': ['-subckt_multiplier', '<truefalse_option>'],
        # set option to true(default) or false to apply implicit subcircuit multipliers
        '-delim'            : ['-delim', '<delim_option>'],  # <TAB|COMMA|string>   set the output file field delimiter
        '-o'                : ['-o', '<basename>'],  # <basename> for the output file(s)
        # '-l'                : ['-l', '<path>'],  # place the log output into <path>, "cout" to log to stdout
        '-per-processor'    : ['-per-processor'],  # create log file for each processor, add .<n>.<r> to log path
        '-remeasure'        : ['-remeasure', '<path>'],
        # [existing Xyce output file] recompute .measure() results with existing data
        '-nox'              : ['-nox', 'onoff_option'],  # <on|off>               NOX nonlinear solver usage
        '-linsolv'          : ['-linsolv', '<solver>'],  # <solver>           force usage of specific linear solver
        '-maxord'           : ['-maxord', '<int_option>'],  # <1..5>              maximum time integration order
        '-max-warnings'     : ['-max-warnings', '<int_option>'],  # <#>           maximum number of warning messages
        '-prf'              : ['-prf', '<path>'],  # <param file name>      specify a file with simulation parameters
        '-rsf'              : ['-rsf', '<path>'],  # specify a file to save simulation responses functions.
        # '-r'                : ['-r', '<path>'],  # <file>   generate a rawfile named <file> in binary format
        '-a'                : ['-a'],  # use with -r <file> to output in ascii format
        '-randseed'         : ['-randseed', '<int_option>'],
        # <number>          seed random number generator used by expressions and sampling methods
        '-plugin'           : ['-plugin', '<plugin_list>'],  # load device plugin libraries (comma-separated list)
    }
    """:meta private:"""

    _default_run_switches = ['-l', '-r']
    

    @classmethod
    def valid_switch(cls, switch: str, parameter: str = '') -> list:
        """
        Validates a command line switch. The following options are available for Xyce:
        
        * `-capabilities`: print compiled-in options and exit
        * `-license`: print license and exit
        * `-param [device [level [<inst|mod>]]]`: print a terse summary of model and/or device parameters
        * `-doc [device [level [<inst|mod>]]]`: output latex tables of model and device parameters to files
        * `-doc_cat [device [level [<inst|mod>]]]`: output latex tables of model and device parameters to files
        * `-count`: device count without netlist syntax or topology check
        * `-syntax`: check netlist syntax and exit
        * `-norun`: netlist syntax and topology and exit
        * `-namesfile <path>`: output internal names file to <path> and exit
        * `-noise_names_file <path>`: output noise source names file to <path> and exit
        * `-quiet`: suppress some of the simulation-progress messages sent to stdout
        * `-jacobian_test`: jacobian matrix diagnostic
        * `-hspice-ext  <option>`: apply hspice compatibility features during parsing.  option=all applies them all
        * `-redefined_params <option>`: set option for redefined .params as ignore (use last), usefirst, warn or error
        * `-subckt_multiplier <option>`: set option to true(default) or false to apply implicit subcircuit multipliers
        * `-local_variation <option>`: set option to true(default) or false to enable local variation in UQ analysis
        * `-delim <TAB|COMMA|string>`: set the output file field delimiter
        * `-o <basename>`: <basename> for the output file(s)
        * `-per-processor`: create log file for each procesor, add .<n>.<r> to log path
        * `-remeasure [existing Xyce output file]`: recompute .measure() results with existing data
        * `-nox <on|off>`: NOX nonlinear solver usage
        * `-linsolv <solver>`: force usage of specific linear solver
        * `-maxord <1..5>`: maximum time integration order
        * `-max-warnings <#>`: maximum number of warning messages
        * `-prf <param file name>`: specify a file with simulation parameters
        * `-rsf <response file name>`: specify a file to save simulation responses functions.
        * `-a`: output in ascii format
        * `-randseed <number>`: seed random number generator used by expressions and sampling methods
        * `-plugin <plugin list>`: load device plugin libraries (comma-separated list)
        
        The following parameters will already be filled in by spicelib, and cannot be set:
        
        * `-l <path>`: place the log output into <path>, "cout" to log to stdout
        * `-r <file>`: generate a rawfile named <file> in binary format

        :param switch: switch to be added.
        :type switch: str
        :param parameter: parameter for the switch
        :type parameter: str, optional
        :return: the correct formatting for the switch
        :rtype: list
        """
        ret = []  # This is an empty switch
        
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
        
        if switch in cls.xyce_args:
            switch_list = cls.xyce_args[switch]
            if len(switch_list) == 2:
                param_token = switch_list[1]
                if param_token == '<path>':
                    ret = [switch_list[0], parameter]
                elif param_token == '<param_options>':
                    # Check for [device [level [<inst|mod>]]] syntax ??
                    ret = [switch_list[0], parameter]  # TODO: this will probably not work, need to separate the parameters
                elif param_token == '<hsext_options>':
                    ret = [switch_list[0], parameter]
                elif param_token == '<redef_param_option>':
                    if parameter in ('ignore', 'uselast', 'usefirst', 'warn', 'error'):
                        ret = [switch_list[0], parameter]
                elif param_token == '<truefalse_option>':
                    if parameter.lower() in ('true', 'false'):
                        ret = [switch_list[0], parameter]
                elif param_token == '<delim_option>':
                    ret = [switch_list[0], parameter]
                elif param_token == '<onoff_option>':
                    if parameter.lower() in ('on', 'off'):
                        ret = [switch_list[0], parameter]
                elif param_token == '<int_option>':
                    try:
                        int(parameter)
                    except ValueError:
                        pass
                    else:
                        ret = [switch_list[0], parameter]
                elif param_token == '<plugin_list>':
                    ret = [switch_list[0], parameter]
                else:
                    _logger.warning(f"Invalid parameter {parameter} for switch '{switch}'")
            else:
                ret = switch_list
        else:
            raise ValueError(f"Invalid Switch '{switch}'")
        return ret

    @classmethod
    def run(cls, netlist_file: Union[str, Path], cmd_line_switches: list = None, timeout: float = None, 
            stdout=None, stderr=None,
            exe_log: bool = False) -> int:
        """Executes a Xyce simulation run.
        
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
            _logger.error("Unable to find the Xyce executable.")
            _logger.error("A specific location of the Xyce can be set")
            _logger.error("using the create_from(<location>) class method")
            _logger.error("==============================================")
            raise SpiceSimulatorError("Simulator executable not found.")
        
        if cmd_line_switches is None:
            cmd_line_switches = []
        elif isinstance(cmd_line_switches, str):
            cmd_line_switches = [cmd_line_switches]
        netlist_file = Path(netlist_file)
        
        logfile = netlist_file.with_suffix('.log').as_posix()
        rawfile = netlist_file.with_suffix('.raw').as_posix()        
        
        cmd_run = cls.spice_exe + cmd_line_switches + ['-l'] + [logfile] + ['-r'] + [rawfile] + [netlist_file.as_posix()]
        # start execution
        if exe_log:
            log_exe_file = netlist_file.with_suffix('.exe.log')
            with open(log_exe_file, "w") as outfile:
                error = run_function(cmd_run, timeout=timeout, stdout=outfile, stderr=subprocess.STDOUT)
        else:        
            error = run_function(cmd_run, timeout=timeout, stdout=stdout, stderr=stderr)
        return error
