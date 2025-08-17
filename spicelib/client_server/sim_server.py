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
# Name:        sim_server.py
# Purpose:     A simulation server that can execute simulations by request of a client located in a different machine.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-02-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from xmlrpc.client import Binary
from xmlrpc.server import SimpleXMLRPCServer
import logging

import threading
from pathlib import Path
import zipfile
import io
from spicelib.client_server.srv_sim_runner import ServerSimRunner
import uuid

_logger = logging.getLogger("spicelib.SimServer")


class SimServer(object):
    """This class implements a server that can run simulations by request of a client located in a different machine.

    The server is implemented using the SimpleXMLRPCServer class from the xmlrpc.server module.

    The client can request the server to start a session, run a simulation, check the status of the simulations and
    retrieve the results of the simulations. The server can run multiple simulations in parallel, but the number of
    parallel simulations is limited by the parallel_sims parameter.

    The server can be stopped by the client by calling the stop_server method.

    :param simulator: The simulator to be used. It must be a class that derives from the BaseSimulator class.
    :type simulator: class
    :param parallel_sims: The maximum number of parallel simulations that the server can run. Default is 4.
    :type parallel_sims: int
    :param output_folder: The folder where the results of the simulations will be stored. Default is './temp'
    :type output_folder: str
    :param timeout: The maximum time that a simulation can run. Default is None, which means that there is no timeout.
    :type timeout: float
    :param port: The port where the server will listen for requests. Default is 9000
    :type port: int
    :param host: The IP address where the server will listen for requests. 
                 Default is 'localhost', which might mean that the server will only accept requests from the local machine.
                 Use '0.0.0.0' to accept requests from any IP address (if your firewall allows it).
    :type host: str
    """

    def __init__(self, simulator, parallel_sims=4, output_folder='./temp', timeout: float = 300, port=9000,
                 host='localhost'):
        self.output_folder = output_folder
        self.simulation_manager = ServerSimRunner(parallel_sims=parallel_sims, timeout=timeout, verbose=False,
                                                  output_folder=output_folder, simulator=simulator)
        self.server = SimpleXMLRPCServer((host, port), 
                                         # requestHandler=RequestHandler
                                         )
        self.server.register_introspection_functions()
        self.server.register_instance(self)
        self.sessions = {}  # this will contain the session_id ids hashing their respective list of sim_tasks
        self.simulation_manager.start()
        self.server_thread = threading.Thread(target=self.server.serve_forever, name="ServerThread")
        self.server_thread.start()

    def add_sources(self, session_id: str, zip_data: Binary) -> bool:
        """Add sources to the simulation. The sources are contained in a zip file will be added to the simulation
        folder.
        
        :return: True if the sources were added, False otherwise
        :rtype: bool
        """
        _logger.info(f"Server: Add sources {session_id}")
        if session_id not in self.sessions:
            return False  # This indicates that no job is started
        # Create a buffer from the zip data
        zip_buffer = io.BytesIO(zip_data.data)
        _logger.debug("Server: Created the buffer")
        # Extract the contents of the zip file
        answer = False
        with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
            for name in zip_file.namelist():
                _logger.debug(f"Server: Writing {name} to zip file")
            if len(zip_file.namelist()) >= 0:
                zip_file.extractall(self.output_folder)
                answer = True
        return answer

    def run(self, session_id: str, circuit_name: str, zip_data: Binary) -> int:
        """Runs a simulation for the given circuit.

        :param session_id: The ID of the session to run the simulation in
        :type session_id: str
        :param circuit_name: The name of the circuit to simulate
        :type circuit_name: str
        :param zip_data: The zip file containing the circuit files
        :type zip_data: bytes
        :return: The run number of the simulation
        :rtype: int
        """
        _logger.info(f"Server: Run {session_id} : {circuit_name}")
        if not self.add_sources(session_id, zip_data):
            return -1

        my_circuit_name = Path(self.output_folder) / circuit_name
        _logger.info(f"Server: Running simulation of {my_circuit_name}")
        runno = self.simulation_manager.add_simulation(my_circuit_name)
        if runno != -1:
            self.sessions[session_id].append(runno)
        return runno

    def start_session(self) -> str:
        """Returns an unique key that represents the session. It will be later used to sort the sim_tasks belonging
        to the session.

        :return: A unique key that represents the session
        :rtype: str
        """
        session_id = str(uuid.uuid4())  # Needs to be a string, otherwise the rpc client can't handle it
        _logger.info(f"Server: Starting session {session_id}")
        self.sessions[session_id] = []
        return session_id

    def status(self, session_id: str) -> list[int]:
        """
        Returns a list with the task numbers that are completed for that session

        :param session_id: The ID of the session to check
        :type session_id: str
        :return: A list of completed task numbers for the session
        :rtype: list[int]
        """
        _logger.debug(f"Server: status({session_id})")
        ret = []
        for task_info in self.simulation_manager.completed_tasks:
            runno = task_info['runno']
            if runno in self.sessions[session_id]:
                _logger.debug(f"Server: status({session_id}) will return task {task_info}")
                ret.append(runno)  # transfers the dictionary from the simulation_manager completed task
                # to the return dictionary 
        _logger.debug(f"Server: status({session_id}) returns {ret}")
        return ret

    def get_files(self, session_id: str, runno: int) -> tuple[str, Binary]:
        """Returns the files associated with a specific run number of a completed task in a session.

        :param session_id: The ID of the session to check
        :type session_id: str
        :param runno: The run number to check
        :type runno: int
        :return: file name and content of the file
        :rtype: tuple[str, Binary]
        """
        _logger.debug(f"Server: get_files({session_id}, {runno})")
        if runno in self.sessions[session_id]:
            for task_info in self.simulation_manager.completed_tasks:
                if runno == task_info['runno']:
                    # Create a buffer to store the zip file in memory
                    zip_file = task_info['zipfile']
                    if not zip_file:
                        _logger.error(f"Server: get_files({session_id}, {runno}) no zip file found. Probably crashed.")
                        continue
                    zip = zip_file.open('rb')
                    # Read the zip file from the buffer and send it to the server
                    zip_data = zip.read()
                    zip.close()
                    self.simulation_manager.erase_files_of_runno(runno)
                    _logger.debug(f"Server: get_files({session_id}, {runno}) returns zip file name {zip_file.name}")
                    return zip_file.name, Binary(zip_data)

        _logger.debug(f"Server: get_files({session_id}, {runno}) returns no data")
        return "", Binary(b'')  # Returns and empty data

    def close_session(self, session_id: str) -> bool:
        """Cleans all the pending sim_tasks with the session_id.

        :return: True if the session was closed successfully, False otherwise
        :rtype: bool
        """
        _logger.info(f"Closing session {session_id}")
        if session_id not in self.sessions:
            _logger.info(f"Closing session {session_id} - not found")
            return False
        for runno in self.sessions[session_id]:
            _logger.info(f"Closing session {session_id}, erasing all files associated with run {runno}")
            try:
                self.simulation_manager.erase_files_of_runno(runno)
            except Exception as e:
                _logger.error(f"Closing session {session_id}: error erasing files for run {runno}: {e}")
        del self.sessions[session_id]
        _logger.info(f"Session {session_id} closed")
        return True  # Needs to return always something. None is not supported

    def stop_server(self) -> bool:
        """Stops the server and cleans up resources.

        :return: True if the server was stopped successfully, False otherwise
        :rtype: bool
        """
        _logger.debug("Server: stopping...ServerInterface")
        self.simulation_manager.stop()
        self.server.shutdown()
        _logger.info("Server: stopped...ServerInterface")
        return True  # Needs to return always something. None is not supported

    def running(self) -> bool:
        """Checks if the server is currently running.

        :return: True if the server is running, False otherwise
        :rtype: bool
        """
        return self.simulation_manager.running()
