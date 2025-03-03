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
# Name:        run_server.py
# Purpose:     A Command Line Interface to run the LTSpice Server
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     10-08-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import sys
import argparse
from spicelib.client_server.sim_server import SimServer
import time
import keyboard


def main():
    
    supported_sims = ["ltspice", "ngspice", "xyce"]
    parser = argparse.ArgumentParser(
        description="Run the LTSpice Server. This is a command line interface to the SimServer class."
                    "The SimServer class is used to run simulations in parallel using a server-client architecture."
                    "The server is a machine that runs the SimServer class and the client is a machine that runs the "
                    "SimClient class."
                    "The argument is the simulator to be used (LTSpice, NGSpice, XYCE, etc.)"
    )
    parser.add_argument('simulator', type=str.lower, nargs='?', default="ltspice", choices=supported_sims,
                        help="Simulator to be used (LTSpice, NGSpice, XYCE, etc.). Default is LTSpice")
    parser.add_argument("-p", "--port", type=int, default=9000,
                        help="Port to run the server. Default is 9000")
    parser.add_argument("-o", "--output", type=str, default=".",
                        help="Output folder for the results. Default is the current folder")
    parser.add_argument("-l", "--parallel", type=int, default=4,
                        help="Maximum number of parallel simulations. Default is 4")
    parser.add_argument('timeout', type=int, nargs='?', default=300,
                        help="Timeout for the simulations. Default is 300 seconds (5 minutes)")

    args = parser.parse_args()
    if args.parallel < 1:
        args.parallel = 1

    mysim = args.simulator.lower()
    if mysim == "ltspice":
        from spicelib.simulators.ltspice_simulator import LTspice
        simulator = LTspice
    elif mysim == "ngspice":
        from spicelib.simulators.ngspice_simulator import NGspiceSimulator
        simulator = NGspiceSimulator
    elif mysim == "xyce":
        from spicelib.simulators.xyce_simulator import XyceSimulator
        simulator = XyceSimulator
    else:
        raise ValueError(f"Simulator {args.simulator} is not supported")
        exit(-1)

    print(f"Starting {simulator.__name__} simulation server on port {args.port}.")
    server = SimServer(simulator, parallel_sims=args.parallel, output_folder=args.output,
                       port=args.port, timeout=args.timeout)
    print("Server Started. Press and hold 'q' to stop")
    while server.running():
        time.sleep(0.2)
        # Check whether a key was pressed
        if keyboard.is_pressed('q'):
            server.stop_server()
            break


if __name__ == "__main__":
    import logging
    log1 = logging.getLogger("spicelib.ServerSimRunner")
    log2 = logging.getLogger("spicelib.SimServer")
    log3 = logging.getLogger("spicelib.SimRunner")
    log4 = logging.getLogger("spicelib.RunTask")
    log1.setLevel(logging.INFO)
    log2.setLevel(logging.INFO)
    log3.setLevel(logging.INFO)
    log4.setLevel(logging.INFO)
    main()
