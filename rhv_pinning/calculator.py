#!/usr/bin/env python3
"""
Purpose: calculate numa pinning for multiple virtual machines on a single host.

Trying to not overlap pinning.

usage: caluclator.py <vm1>:<vsocket1>:<vcpu1> <vm2>:<vsocket2>:<vcpu2> ... <vmN>:<vcpuN>
example: calculator.py 1:4:192 2:2:32

VM1: ==> 48vCPU per numa node ==> numa nodes in total: 4
VM2: ==> 16vCPU per numa node ==> numa-nodes in total: 2

- core0 of any numa node will be reserved for host
- 

1:4:64 2:4:128 3:4:96 4:4:144

"""

import re
import sys
from subprocess import check_output
from io import StringIO

class Hardware():

    def __init__(self):
        self.__lscpu_output = None
        self.__numactl_output = None

    @property
    def lscpu_output(self):
        return self.__lscpu_output

    @lscpu_output.setter
    def lscpu_output(self, payload):
        self.__lscpu_output = payload

    @property
    def numactl_output(self):
        return self.__numactl_output

    @numactl_output.setter
    def numactl_output(self, payload):
        self.__numactl_output = payload

    def gather_command_output(self):
        """ load command output """
        self.lscpu_output = check_output(["lscpu"]).decode("utf-8")
        self.numactl_output = check_output(["numactl", "--hardware"]).decode("utf-8")


class Cpu():

    def __init__(self):
        self.__cores = 0
        self.__numa_nodes = 0
        self.__sockets = 0
        self.__threads = 0
        self.__ht = False
        
    @property
    def cores(self):
        return self.__cores

    @cores.setter
    def cores(self, cores):
        self.__cores = cores

    @property
    def numa_nodes(self):
        return self.__numa_nodes

    @numa_nodes.setter
    def numa_nodes(self, numa_nodes):
        self.__numa_nodes = numa_nodes

    @property
    def sockets(self):
        return self.__sockets

    @sockets.setter
    def sockets(self, sockets):
        self.__sockets = sockets

    @property
    def ht(self):
        return self.__ht

    @ht.setter
    def ht(self, ht):
        self.__ht = ht

    @property
    def threads(self):
        return self.__threads

    @threads.setter
    def threads(self, threads):
        self.__threads = threads
    
    def update(self, lscpu_output):
        """ update CPU information based on given lscpu output """

        core_pattern = "^Core.s.\sper\ssocket:\s+(\d+)$"
        thread_pattern = '^Thread.s.\sper\score:\s+(\d+)$'
        socket_pattern = '^Socket.s.:\s+(\d+)$'
        numa_pattern = '^NUMA\snode.s.:\s+(\d+)$'

        for line in StringIO(lscpu_output).readlines():
            line = line.rstrip()
            if re.match(core_pattern, line):
                self.cores = int(re.search(core_pattern, line).group(1))
            if re.match(numa_pattern, line):
                self.numa_nodes = int(re.search(numa_pattern, line).group(1))
            if re.match(socket_pattern, line):
                self.sockets = int(re.search(socket_pattern, line).group(1))
            if re.match(thread_pattern, line):
                self.threads = int(re.search(thread_pattern, line).group(1))
                if self.threads > 1:
                    self.__ht = True 

class Core():
    def __init__(self, id) -> None:
        self.__id = int(id)
        self.__virtual_machines = list()

    @property
    def id(self) -> int:
        return self.__id

    def pin(self, vm) -> None:
        self.__virtual_machines.append(vm) 

    def unpin(self, vm) -> None:
        self.__virtual_machines.remove(vm)

    def status(self) -> int:
        """ return amount of VMs using this core """
        return len(self.__virtual_machines)

    def __str__(self) -> int:
        return int(self.__id)

class Numa():

    def __init__(self):
        self.__node_count = 0
        self.__numa_nodes = list()

    @property
    def nodes(self) -> list:
        return self.__numa_nodes

    @staticmethod
    def __chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    @staticmethod
    def rotate(l, n):
        return l[n:] + l[:n]

    def add_node(self, node) -> None:
        if isinstance(node, NumaNode):
            self.__numa_nodes.append(node)
        else:
            # todo - add proper exception type
            raise TypeError

    def update(self, numactl_output) -> None:
        """
        available: 4 nodes (0-3)
        node 0 cpus: 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 112 113 114 115 116 117 118 119 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139
        node 0 size: 3094782 MB
        node 0 free: 1392668 MB
        
        """
        node_count_pattern = '^available:\s(\d+)\snodes.*$'
        node_cpu_pattern = '^node\s(\d+)\scpus:\s([0-9\s]+)$'
        memory_max_pattern = '^node\s(\d+)\ssize:\s(\d+)\s.*$'
        memory_free_pattern = '^node\s(\d+)\sfree:\s(\d+)\s.*$'

        for line in StringIO(numactl_output).readlines():
            line = line.rstrip()

            if re.match(node_count_pattern, line):
                self.__node_count = int(re.search(node_count_pattern, line).group(1))
                for i in range(0, self.__node_count):
                    self.add_node(NumaNode(id=i))
            if re.match(node_cpu_pattern, line):
                id, cpus = re.search(node_cpu_pattern, line).group(1, 2)
                cpu_list = cpus.split()

                # all values are required to be integer
                cpu_list = list(map(int, cpu_list))
                # create Core-objects out of list-values 
                for i in range(0, int(len(cpu_list))):
                    cpu_list[i] = Core(id=cpu_list[i])

                # create two identical lists
                tmp_list = list(self.__chunks(cpu_list, int(len(cpu_list)/2)))
                self.__numa_nodes[int(id)].cpus = {"cores": tmp_list[0], "threads": tmp_list[1]}

            if re.match(memory_max_pattern, line):
                id, memory_max = re.search(memory_max_pattern, line).group(1, 2)
                self.__numa_nodes[int(id)].memory = {"max": int(memory_max)}
            if re.match(memory_free_pattern, line):
                id, memory_free = re.search(memory_free_pattern, line).group(1, 2)
                self.__numa_nodes[int(id)].memory = {"free": int(memory_free)}

    def get_free_cores(self, vm) -> list:
        """ 
        
        """
        sockets = vm.sockets
        cores = vm.cores
        threads = vm.threads

        if sockets > len(self.nodes):
            """ the virtual machine architecture does not match host architecture """
            raise IndexError
        
        tmp_list = list()
        for i in range(0, sockets):
            if threads > 1:
                tmp_list.extend(self.nodes[i].cpus["cores"][1:cores+1])
                tmp_list.extend(self.nodes[i].cpus["threads"][1:cores+1])
            else:
                raise NotImplementedError

        return tmp_list

    def pinning_string(self, vm) -> str:
        """
        
        """
        sockets = vm.sockets
        cores = vm.cores
        threads = vm.threads

        amount_vcpus = sockets * cores * threads

        if sockets > len(self.nodes):
            """ the virtual machine architecture does not match host architecture """
            raise IndexError

        cores_list = list()
        threads_list = list()
        for i in range(0, sockets):
            if threads > 1:
                # todo - refactor to pin VM to core and rotate cores accordingly
                for core in self.nodes[i].cpus["cores"][1:cores+1]:
                    core.pin(vm)
                    cores_list.append(core.id)
                for thread in self.nodes[i].cpus["threads"][1:cores+1]:
                    thread.pin(vm)
                    threads_list.append(thread.id)
                # rotate lists by number of cores
                self.nodes[i].cpus = {"cores": self.rotate(self.nodes[i].cpus["cores"], cores), \
                    "threads": self.rotate(self.nodes[i].cpus["threads"], cores)}

            else:
                raise NotImplementedError

        cpu_pinning_string = str()
        string_separator = "_"
        tmp_pinning_string = list()

        cpu_pair_slot = 0
        for current_vcpu in range(0,amount_vcpus):
            tmp_pinning_string.append("{vcpu}#{core},{thread}".format(vcpu=current_vcpu, core=cores_list[cpu_pair_slot], thread=threads_list[cpu_pair_slot]))

            if (current_vcpu + 1) % 2 == 0:
                cpu_pair_slot += 1
                
        cpu_pinning_string = string_separator.join(tmp_pinning_string)
        return cpu_pinning_string


class NumaNode():
    def __init__(self, id) -> None:
        self.__node_id = id
        self.__cpu_cores = None
        self.__cpu_threads = None
        self.__memory_max = None
        self.__memory_free = None

    @property
    def id(self) -> int:
        return self.__node_id

    @property
    def cpus(self) -> dict:
        return {"cores": self.__cpu_cores, "threads": self.__cpu_threads}

    @cpus.setter
    def cpus(self, cpus) -> None:
        if isinstance(cpus, dict):
            for k in cpus.keys():
                if k=="cores":
                    self.__cpu_cores = cpus["cores"]
                if k=="threads":
                    self.__cpu_threads = cpus["threads"]

    @property
    def memory(self) -> dict:
        return {"max": self.__memory_max, "free": self.__memory_free}

    @memory.setter
    def memory(self, memory):
        if isinstance(memory, dict):
            for k in memory.keys():
                if k=="max":
                    self.__memory_max = memory["max"]
                if k=="free":
                    self.__memory_free = memory["free"]


class VirtualMachine():
    def __init__(self, socket, cores, threads, memory=None) -> None:
        self.__sockets = int(socket)
        self.__cores = int(cores)
        self.__threads = int(threads)
        self.__memory = memory
        self.__vcpus = self.__sockets * self.__cores * self.__threads

    @property
    def vcpus(self) -> int:
        return int(self.__vcpus)

    @property
    def cores(self) -> int:
        return int(self.__cores)
    
    @property
    def sockets(self) -> int:
        return int(self.__sockets)

    @property
    def threads(self) -> int:
        return int(self.__threads)

    @property
    def memory(self) -> int:
        return int(self.__memory)

    def update(self) -> None:
        pass


class Host():
    """ Class representing the virtualization host with CPU and NUMA 

    - gather hardware information by collection output from following commands
        - numactl --hardware
        - lscpu
    
    """
    def __init__(self) -> None:
        self.hardware = Hardware()
        self.hardware.gather_command_output()

        self.__numa = None
        self.__cpu = None

        self.__virtual_machines = list()

    def initialize(self):
        """ initialize hardware information from host
        
        """
        self.__numa = Numa()
        self.__numa.update(self.hardware.numactl_output)
        self.__cpu = Cpu()
        self.__cpu.update(self.hardware.lscpu_output)

    @property
    def numa(self) -> Numa:
        return self.__numa

    @property
    def cpu(self) -> Cpu:
        return self.__cpu

    @property
    def ht_enabled(self) -> bool:
        return self.cpu.ht

    @property
    def virtual_machines(self) -> VirtualMachine:
        return self.__virtual_machines

    def add_vm(self, config) -> None:
        """ will return a dictionary of vm-configuration
        
        config = sockets:cores:threads

        input example: 4:18:2
        """
        sockets, cores, threads = config.split(':')
        self.__virtual_machines.append(VirtualMachine(sockets, cores, threads))


def main(vm_configurations):
    host = Host()
    host.initialize()

    for config in vm_configurations:
        host.add_vm(config)


    for vm in host.virtual_machines:
        print(host.numa.pinning_string(vm))


if __name__ == '__main__':
    main(sys.argv[1:])
