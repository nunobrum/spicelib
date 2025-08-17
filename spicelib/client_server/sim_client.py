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
# Purpose:     Tool used to launch a Spice simulation in batch mode.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-02-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import os.path
import zipfile
import xmlrpc.client
import io
from pathlib import Path
import time
from collections import OrderedDict
from dataclasses import dataclass
import logging
from typing import Union, Iterable, Optional

_logger = logging.getLogger("spicelib.SimClient")


class SimClientInvalidRunId(LookupError):
    """Raised when asking for a run_no that doesn't exist"""
    ...


@dataclass
class JobInformation:
    """Contains information about pending simulation jobs"""
    run_number: int  # The run id that is returned by the Server and which identifies the server
    file_dir: Path

# class RunIterator(object):
#
#     def __init__(self, client, timeout):
#         self.client = client
#         self.timeout = timeout
#
#     def __iter__(self):
#         return self
#
#     def __next__(self):
#         return self.client.__next__()


class SimClient(object):
    """
    Class used for launching simulations in a Spice Simulation Server.
    A Spice Simulation Server is a machine running a script with an active SimServer object.

    This class only implement basic level handshaking with a single simulation Server.
    Upon instance, it will establish a connection with Simulation Server. This connection is kept
    alive during the whole live of this object.

    The run() method will transfer the netlist for the server, execute a simulation and transfer the simulation results
    back to the client.

    Data is returned from the server inside a zipfie which is copied into the directory defined when the job was
    created, /i.e./ run() method called.

    Two lists are kept by this class:

        * A list of started jobs (started_jobs) and,

        * a list with finished jobs on the server, but, which haven't been yet transferred to the client (stored_jobs).

    This distinction is important because the data is erased on the server side when the data is transferred.

    This class implements an iterator that is to be used for retrieving the job. See the example below.
    The iterator polls the server with a time interval defined by the attribute ``minimum_time_between_server_calls``.
    This attribute is set to 0.2 seconds by default, but it can be overriden.

    Usage:

    .. code-block:: python

        import zipfile
        from PySpice.sim.sim_client import SimClient

        server = SimClient('http://localhost', 9000)  # Use another computer address.
        print(server.session_id)
        runid = server.run("../../tests/testfile.net")
        print("Got Job id", runid)

        for runid in server:   # may not arrive in the same order as runids were launched
            zip_filename = server.get_runno_data(runid)
            print(f"Received {zip_filename} from runid {runid}")
            if zip_filename is None:
                print(f"Run id {runid} has no data")
                continue
            # the zip file normally contains a `.raw` and a `.log` file, 
            # but it can instead only hold a `.fail` file in case of a simulation error.
            with zipfile.ZipFile(zip_filename, 'r') as zipf:  # Extract the contents of the zip file
                for name in zipf.namelist():
                    print(f"Extracting {name} from {zip_filename}")
                    zipf.extract(name)
            os.remove(zip_filename)  # Remove the zip file

    NOTE: More elaborate algorithms such as managing multiple servers will be done on another class.
    """

    def __init__(self, host_address, port):
        self.server = xmlrpc.client.ServerProxy(f'{host_address}:{port}')
        self.session_id = self.server.start_session()
        _logger.info(f"Client: Started {self.session_id}")
        self.started_jobs = OrderedDict()  # This list keeps track of started jobs on the server
        self.stored_jobs = OrderedDict()  # This list keeps track of finished simulations that haven't yet been transferred.
        self.completed_jobs = 0
        self.minimum_time_between_server_calls = 0.2  # Minimum time between server calls
        self._last_server_call = time.time()

    def __del__(self):
        self.close_session()

    def add_sources(self, sources: Iterable) -> bool:
        """Add sources to the simulation environment. The sources are a list of file paths that are going to be
        transferred to the server. The server will add the sources to the simulation folder. Returns True if the sources
        were added and False if the session_id is not valid. """
        # Create a buffer to store the zip file in memory
        zip_buffer = io.BytesIO()

        # Create the zip file in memory
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for source in sources:
                dep_path = Path(source)
                if dep_path.exists():
                    zip_file.write(source, dep_path.name)

        # Reset the buffer position to the start
        zip_buffer.seek(0)

        # Read the zip file from the buffer and send it to the server
        zip_data = zip_buffer.read()
        # server side method signature: def add_sources(self, session_id: str, zip_data: Binary) -> bool
        return bool(self.server.add_sources(self.session_id, zip_data))

    def run(self, circuit: Union[str, Path], dependencies: Optional[list[Union[str, Path]]] = None) -> int:
        """
        Sends the netlist identified with the argument "circuit" to the server, and it receives a run identifier
        (runno). Since the server can receive requests from different machines, this identifier is not guaranteed to be
        sequential.

        :param circuit: path to the netlist file containing the simulation directives.
        :type circuit: pathlib.Path or str
        :param dependencies: list of files that the netlist depends on. This is used to ensure that the netlist is
         transferred to the server with all the necessary files.
        :type dependencies: list of pathlib.Path or str
        :returns: identifier on the server of the simulation.
        :rtype: int
        """
        circuit_path = Path(circuit)
        circuit_name = circuit_path.name
        if os.path.exists(circuit):
            # Create a buffer to store the zip file in memory
            zip_buffer = io.BytesIO()

            # Create the zip file in memory
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(circuit, circuit_name)  # Makes sure it writes it to the root of the zipfile
                if dependencies is not None:
                    for dep in dependencies:
                        dep_path = Path(dep)
                        if dep_path.exists():
                            zip_file.write(dep, dep_path.name)

            # Reset the buffer position to the start
            zip_buffer.seek(0)

            # Read the zip file from the buffer and send it to the server
            zip_data = zip_buffer.read()

            # server side method signature: def run(self, session_id: str, circuit_name: str, zip_data: Binary) -> int
            run_id = int(self.server.run(self.session_id, circuit_name, zip_data))  # type: ignore
            job_info = JobInformation(run_number=run_id, file_dir=circuit_path.parent)
            self.started_jobs[run_id] = job_info
            return run_id
        else:
            _logger.error(f"Client: Circuit {circuit} doesn't exit")
            return -1

    def get_runno_data(self, runno: int) -> Union[Path, None]:
        """
        Returns the simulation output data inside a zip file name.

        :return: The name of the zip file containing the simulation output data, or None if not found.
                 The zip file is not guaranteed to hold both a `.raw` file and a `.log` file.
                 It can hold a `.fail` file in case of a simulation error.
        :rtype: pathlib.Path
        """
        if runno not in self.stored_jobs:
            raise SimClientInvalidRunId(f"Invalid Job id {runno}")

        # server side method signature: def get_files(self, session_id, runno) -> tuple[str, Binary]
        zip_filename, zipdata = self.server.get_files(self.session_id, runno)  # type: ignore
        job = self.stored_jobs.pop(runno)  # Removes it from stored jobs
        self.completed_jobs += 1
        if zip_filename != '':
            store_path = job.file_dir / zip_filename
            with open(store_path, 'wb') as f:
                f.write(zipdata.data)  # type: ignore
            return store_path
        else:
            return None

    def __iter__(self):
        return self

    def __next__(self):
        while len(self.started_jobs) > 0:
            # server side method signature: def status(self, session_id: str) -> list[int]
            status: list[int] = self.server.status(self.session_id)  # type: ignore
            if len(status) > 0:
                runno = status.pop(0)
                self.stored_jobs[runno] = self.started_jobs.pop(runno)  # Job is taken out of the started jobs list and
                # is added to the stored jobs
                return runno
            else:
                now = time.time()
                delta = self.minimum_time_between_server_calls - (now - self._last_server_call)
                if delta > 0:
                    time.sleep(delta)  # Go asleep for a sec
                self._last_server_call = now

        # when there are no pending jobs left, exit the iterator
        raise StopIteration

    def close_session(self):
        """Closes the current session.
        """
        _logger.info(f"Client: Closing session {self.session_id}")
        self.server.close_session(self.session_id)
