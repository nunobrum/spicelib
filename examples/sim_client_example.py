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
# Name:        sim_client.py
# Purpose:     Example of a client to the SimServer
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-02-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
# -- Start of SimClient Example --
import os
import zipfile
import logging
import sys


from spicelib.client_server.sim_client import SimClient

# In order for this, to work, you need to have a server running. To start a server, run the following command:
# python -m spicelib.scripts.run_server --port 9000 --parallel 4 --output ./temp LTSpice 300

_logger = logging.getLogger("spicelib.SimClient")
_logger.setLevel(logging.DEBUG)
_logger.addHandler(logging.StreamHandler(sys.stdout))


server = SimClient('http://localhost', 9000)
print(server.session_id)
runid = server.run("./testfiles/testfile.net")
print("Got Job id", runid)
for runid in server:  # May not arrive in the same order as runids were launched
    zip_filename = server.get_runno_data(runid)
    print(f"Received {zip_filename} from runid {runid}")
    if zip_filename is None:
        print(f"Run id {runid} has no data")
        continue
    # the zip file normally contains a `.raw` and a `.log` file, 
    # but it can also hold a `.fail` file in case of a simulation error.    
    with zipfile.ZipFile(zip_filename, 'r') as zipf:  # Extract the contents of the zip file
        for name in zipf.namelist():
            print(f"Extracting {name} from {zip_filename}")
            zipf.extract(name)
    os.remove(zip_filename)  # Remove the zip file

server.close_session()
# -- End of SimClient Example --
print("Finished")
# server.server.stop_server()  # This will terminate the server
