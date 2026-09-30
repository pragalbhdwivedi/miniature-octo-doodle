import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('refresh',Path(__file__).parents[1]/'scripts/linux-loopback-refresh.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LoopbackTests(unittest.TestCase):
    def containers(self):
        return [{'Config':{'Labels':{'com.docker.compose.project':'expected','com.docker.compose.service':s}},
                 'State':{'Health':{'Status':'healthy'}}} for s in module.core.SERVICES]

    def test_refresh_requires_all_three_healthy_owned_services(self):
        rows=self.containers()
        self.assertTrue(module.ready(rows,'expected'))
        self.assertFalse(module.ready(rows,'other'))
        self.assertFalse(module.ready(rows[:2],'expected'))
        rows[0]['State']['Health']['Status']='starting'
        self.assertFalse(module.ready(rows,'expected'))


if __name__=='__main__': unittest.main()
