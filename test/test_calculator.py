# https://docs.python.org/3/library/unittest.html
# https://www.digitalocean.com/community/tutorials/how-to-use-unittest-to-write-a-test-case-for-a-function-in-python

import unittest

from rhv_pinning.calculator import Cpu, Host, Numa, Hardware


class TestHardware(Hardware):
    @staticmethod
    def getFileContent(filename):
        with open(filename, 'r') as fd:
            return fd.read()

    def __init__(self):
        super().__init__()
        self.__lscpu_output = None
        self.__numactl_output = None
        self.__numactl_test_file = self.getFileContent('/home/sfroemer/workspace/ovirt-stuff/numa-pinning/test/examples/numa_2-node_72-core_with-ht.txt')
        self.__lscpu_test_file = self.getFileContent('/home/sfroemer/workspace/ovirt-stuff/numa-pinning/test/examples/lscpu_2-node-72-core_with-ht.txt')
        
    def gather_command_output(self):
        """ load command output """
        self.lscpu_output = self.__lscpu_test_file
        self.numactl_output = self.__numactl_test_file


class TestHardwareCpu(unittest.TestCase):
   

    def setUp(self) -> None:
        self.hardware = TestHardware()
        self.hardware.gather_command_output()
        self.cpu = Cpu()
        self.cpu.update(self.hardware.lscpu_output)

    def test_amount_cores(self):
        self.assertEqual(self.cpu.cores, 18)

    def test_hyperthreading_enabled(self):
        self.assertTrue(self.cpu.ht)

    def test_amount_numa_nodes(self):
        self.assertEqual(self.cpu.numa_nodes, 2)

    def test_amount_sockets(self):
        self.assertEqual(self.cpu.sockets, 2)

    def test_amount_threads(self):
        self.assertEqual(self.cpu.threads, 2)

class TestHardwareNuma(unittest.TestCase):
    @staticmethod
    def getFileContent(filename):
        with open(filename, 'r') as fd:
            return fd.read()

    def setUp(self) -> None:
        self.hardware = TestHardware()
        self.hardware.gather_command_output()

        self.numa = Numa()
        self.numa.update(self.hardware.numactl_output)

    def test_amount_numa_nodes(self):
        self.assertEqual(len(self.numa.nodes), 2)

    def test_amount_cpu_cores(self):
        self.assertEqual(len(self.numa.nodes[0].cpus["cores"]), 18)
        self.assertEqual(len(self.numa.nodes[1].cpus["cores"]), 18)

    def test_amount_cpu_threads(self):
        self.assertEqual(len(self.numa.nodes[0].cpus["threads"]), 18)
        self.assertEqual(len(self.numa.nodes[1].cpus["threads"]), 18)

    def test_numa_node_memory_max(self):
        self.assertEqual(self.numa.nodes[0].memory["max"], 385326)
        self.assertEqual(self.numa.nodes[1].memory["max"], 387063)

    def test_numa_node_memory_free(self):
        self.assertEqual(self.numa.nodes[0].memory["free"], 379239)
        self.assertEqual(self.numa.nodes[1].memory["free"], 378385)
    

class TestHost(Host):

    def __init__(self) -> None:
        super().__init__()
        self.hardware = TestHardware()
        self.hardware.gather_command_output()

        self.__numa = None
        self.__cpu = None
        

class TestHostFunctions(unittest.TestCase):
    def setUp(self) -> None:
        self.host = TestHost()
        self.host.initialize()

    def test_host_ht_enabled(self):
        self.assertTrue(self.host.ht_enabled)


if __name__ == '__main__':
    unittest.main()
    