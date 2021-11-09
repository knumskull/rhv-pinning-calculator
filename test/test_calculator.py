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

    def test_host_added_vm(self):
        self.host.add_vm("4:18:2")
        self.assertEqual(len(self.host.virtual_machines), 1)

    def test_host_added_vm_architecture(self):
        self.host.add_vm("4:18:2")
        self.assertEqual(self.host.virtual_machines[0].sockets, 4)
        self.assertEqual(self.host.virtual_machines[0].cores, 18)
        self.assertEqual(self.host.virtual_machines[0].threads, 2)
        self.assertEqual(self.host.virtual_machines[0].vcpus, 144)

    def test_host_get_free_cores_for_vm(self):
        self.host.add_vm("2:10:2")
        expected_cores = [
            2, 4, 6, 8, 10, 12, 14, 16, 18, 20,      # numa0 - cores
            38, 40, 42, 44, 46, 48, 50, 52, 54, 56,  # numa0 - threads
            3, 5, 7, 9, 11, 13, 15, 17, 19, 21,      # numa1 - cores
            39, 41, 43, 45, 47, 49, 51, 53, 55, 57   # numa1 - threads
        ]

        vm = self.host.virtual_machines[0]
        self.assertEqual(len(self.host.numa.get_free_cores(vm)), 40)
        self.assertEqual(self.host.numa.get_free_cores(vm), expected_cores)

    def test_host_vm_pinning_string(self):
        self.host.add_vm("2:5:2")
        expected_string = "0#2,38_1#2,38_2#4,40_3#4,40_4#6,42_5#6,42_6#8,44_7#8,44_8#10,46_9#10,46_10#3,39_11#3,39_12#5,41_13#5,41_14#7,43_15#7,43_16#9,45_17#9,45_18#11,47_19#11,47"
        vm = self.host.virtual_machines[0]
        self.assertEqual(self.host.numa.pinning_string(vm), expected_string)

    def test_host_multiple_vm_pinning(self):
        
        self.host.add_vm("2:5:2") # vm_1
        self.host.add_vm("2:4:2") # vm_2

        expected_string_vm_1 = "0#2,38_1#2,38_2#4,40_3#4,40_4#6,42_5#6,42_6#8,44_7#8,44_8#10,46_9#10,46_10#3,39_11#3,39_12#5,41_13#5,41_14#7,43_15#7,43_16#9,45_17#9,45_18#11,47_19#11,47"
        expected_string_vm_2 = "0#12,48_1#12,48_2#14,50_3#14,50_4#16,52_5#16,52_6#18,54_7#18,54_8#13,49_9#13,49_10#15,51_11#15,51_12#17,53_13#17,53_14#19,55_15#19,55"

        vm_1 = self.host.virtual_machines[0]
        vm_2 = self.host.virtual_machines[1]
        self.assertEqual(self.host.numa.pinning_string(vm_1), expected_string_vm_1)
        self.assertEqual(self.host.numa.pinning_string(vm_2), expected_string_vm_2)

if __name__ == '__main__':
    unittest.main()
    