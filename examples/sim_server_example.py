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

import time
import logging
import signal
import os

from spicelib.client_server.sim_server import SimServer
from spicelib.simulators.ltspice_simulator import LTspice
simulator = LTspice

_logger = logging.getLogger("spicelib.SimServer")
_logger.setLevel(logging.DEBUG)
_logger.addHandler(logging.StreamHandler(sys.stdout))

kill_server_requested: bool = False


def signal_handler(sig, frame):
    global kill_server_requested
    if sig == signal.SIGINT:
        mysig = "SIGINT"
    else:
        mysig = "SIGTERM"
    print(f"Signal {mysig} received. Stopping server...")
    kill_server_requested = True


print("Starting Server")
server = SimServer(simulator, parallel_sims=4, output_folder='./temp_server', port=9000, host='localhost')
print(f"Server Started. Press Ctrl-C or send signal SIGINT or SIGTERM to process ID {os.getpid()} to stop.")
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
while server.running():
    time.sleep(0.2)
    # Check whether relevant signal was received
    if kill_server_requested:
        server.stop_server()
        break
