# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2016 Bitcraze AB
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA  02110-1301, USA.
#
# Modified by:
# Company:     University of Applied Sciences, Augsburg, Germany
# Author:      Thomas Izycki <thomas.izycki2@hs-augsburg.de>
#
# Description: - Allow adding and removing of Crazyflie objects
#              at any time
#              - Add Factory class for the
#              Crazyflie object used in simulations
#              - Add LocalCrazyflie instantiation and handling

from threading import Thread

from cflib.crazyflie import Crazyflie
from dynamicCrazyflie import SyncCrazyflie


class _Factory:
    """
    Default Crazyflie factory class.
    """

    def construct(self, uri):
        return SyncCrazyflie(uri), None

class CachedCfFactory:
    """
    Factory class that creates Crazyflie instances with TOC caching
    to reduce connection time.
    """

    def __init__(self, ro_cache=None, rw_cache=None):
        self.ro_cache = ro_cache
        self.rw_cache = rw_cache

    def construct(self, uri):
        cf = Crazyflie(ro_cache=self.ro_cache, rw_cache=self.rw_cache)
        return SyncCrazyflie(uri, cf=cf), None


class Swarm:
    """
    Runs a swarm of Crazyflies. It implements a functional-ish style of
    sequential or parallel actions on all individuals of the swarm.

    When the swarm is connected, a link is opened to each Crazyflie through
    SyncCrazyflie instances. The instances are maintained by the class and are
    passed in as the first argument in swarm wide actions.
    """

    def __init__(self):
        """
        Constructs a Swarm instance and instances used to connect to the
        Crazyflies

        :param uris: A set of uris to use when connecting to the Crazyflies in
        the swarm
        :param factory: A factory class used to create the instances that are
         used to open links to the Crazyflies. Mainly used for unit testing.
        """
        self._cfs = {}
        self._lcfs = {}
        self._is_open = False

    def addCf(self, uri, factory=_Factory()):
        if uri not in self._cfs:
            scf, lcf = factory.construct(uri)
            self._cfs[uri] = scf
            if lcf is not None:
                self._lcfs[uri] = lcf
            return True
        return False

    def removeCf(self, link_uri):
        '''
        Delete the Crazyflie Object and close
        the link, if it is still open.
        '''
        if link_uri in self._cfs:
            self.close_link(link_uri)
            self._cfs.pop(link_uri)
        if link_uri in self._lcfs:
            self.close_crazyflie_process(link_uri)
            self._lcfs.pop(link_uri)

    def getSwarmLinkStatus(self):
        return self._is_open

    def checkIfCfsConnected(self):
        return bool(self._cfs)

    def open_links(self):
        """
        Open links to all individuals in the swarm
        """
        if self._is_open:
            raise Exception('Already opened')

        try:
            self.parallel_safe(lambda scf: scf.open_link())
            self._is_open = True
        except Exception as e:
            self.close_links()
            raise e

    def close_links(self):
        """
        Close all open links
        """
        cfsCopy = self._cfs.copy()
        for uri, cf in cfsCopy.items():
            cf.close_link()

        self._cfs.clear()
        self._is_open = False

    def open_link(self, uri):
      if uri in self._cfs:
        if self._cfs[uri].getLinkStatus() == False:
          if self._cfs[uri].open_link():
            self._cfs[uri].cf.disconnected.add_callback(self._disconnected)
            return True
      else:
        print(f"Could not open link to Cf {uri}")
        return False

    def close_link(self, uri):
      if uri in self._cfs:
        if self._cfs[uri].getLinkStatus() == True:
          self._cfs[uri].close_link()
          print(f"Closed link to: {uri}")

    def close_crazyflie_process(self, uri):
        if uri in self._lcfs:
            self.terminateLocalCrazyflie(uri)
            print(f"Ended Crazyflie process for {uri}")

    # Remove the scf object from the dictionary when connection gets terminated
    def _disconnected(self, link_uri):
        if link_uri in self._cfs:
            del self._cfs[link_uri]
            print(f"Removed Cf: {link_uri}")
        if link_uri in self._lcfs:
            self.close_crazyflie_process(link_uri)
            del self._lcfs[link_uri]

    def __enter__(self):
        self.open_links()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_links()

    def single(self, uri, func, argsList=None):
      if uri in self._cfs:
        cf = self._cfs[uri]
        args = [cf]
        if argsList is not None:
            args.extend(argsList)
        func(*args)

    def sequential(self, func, args_dict=None):
        """
        Execute a function for all Crazyflies in the swarm, in sequence.

        The first argument of the function that is passed in will be a
        SyncCrazyflie instance connected to the Crazyflie to operate on.
        A list of optional parameters (per Crazyflie) may follow defined by
        the args_dict. The dictionary is keyed on URI.

        Example:
        def my_function(scf, optional_param0, optional_param1)
            ...

        args_dict = {
            URI0: [optional_param0_cf0, optional_param1_cf0],
            URI1: [optional_param0_cf1, optional_param1_cf1],
            ...
        }


        self.sequential(my_function, args_dict)

        :param func: the function to execute
        :param args_dict: parameters to pass to the function
        """
        for uri, cf in self._cfs.items():
            args = self._process_args_dict(cf, uri, args_dict)
            func(*args)

    def parallel(self, func, args_dict=None):
        """
        Execute a function for all Crazyflies in the swarm, in parallel.
        One thread per Crazyflie is started to execute the function. The
        threads are joined at the end. Exceptions raised by the threads are
        ignored.

        For a description of the arguments, see sequential()

        :param func:
        :param args_dict:
        """
        try:
            self.parallel_safe(func, args_dict)
        except Exception:
            pass

    def parallel_safe(self, func, args_dict=None):
        """
        Execute a function for all Crazyflies in the swarm, in parallel.
        One thread per Crazyflie is started to execute the function. The
        threads are joined at the end and if one or more of the threads raised
        an exception this function will also raise an exception.

        For a description of the arguments, see sequential()

        :param func:
        :param args_dict:
        """
        threads = []
        reporter = self.Reporter()

        for uri, scf in self._cfs.items():
            args = [func, reporter] + \
                self._process_args_dict(scf, uri, args_dict)

            thread = Thread(target=self._thread_function_wrapper, args=args)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if reporter.is_error_reported():
            first_error = reporter.errors[0]
            raise Exception('One or more threads raised an exception when '
                            'executing parallel task') from first_error

    def _thread_function_wrapper(self, *args):
        reporter = None
        try:
            func = args[0]
            reporter = args[1]
            func(*args[2:])
        except Exception as e:
            raise

    def _process_args_dict(self, scf, uri, args_dict):
        args = [scf]

        if args_dict:
            args += args_dict[uri]

        return args

    def parallelLocal(self, func, args_dict=None):
        """ See "parallel" method for information """
        try:
            self.parallel_safe_local(func, args_dict)
        except Exception:
            raise

    def parallel_safe_local(self, func, args_dict=None):
        """ See "parallel_safe" method for information """
        threads = []
        reporter = self.Reporter()

        for uri, lcf in self._lcfs.items():
            args = [func, reporter] + \
                self._process_args_dict(lcf, uri, args_dict)

            thread = Thread(target=self._thread_function_wrapper, args=args)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if reporter.is_error_reported():
            first_error = reporter.errors[0]
            raise Exception('One or more threads raised an exception when '
                            'executing parallel task') from first_error

    def singleLocal(self, uri, func, argsList=None):
      if uri in self._lcfs:
        lcf = self._lcfs[uri]
        args = [lcf]
        if argsList is not None:
            args.extend(argsList)
        func(*args)

    def terminateLocalCrazyflie(self, link_uri):
        self._lcfs[link_uri].terminateCrazyflie()

    class Reporter:
        def __init__(self):
            self.error_reported = False
            self._errors = []

        @property
        def errors(self):
            return self._errors

        def report_error(self, e):
            self.error_reported = True
            self._errors.append(e)

        def is_error_reported(self):
            return self.error_reported
