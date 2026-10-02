import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sidecar_runtime as runtime
import coder_schedule as schedule


class HostTests(unittest.TestCase):
    def setUp(self):
        self.rows={4:{'name':'python.exe','parent':3,'born':40},
                   3:{'name':'language_server.exe','parent':2,'born':30},
                   2:{'name':'language_server.exe','parent':1,'born':20},
                   1:{'name':'Antigravity.exe','parent':0,'born':10}}

    def test_live_sidecar_chain_is_accepted(self):
        self.assertTrue(runtime.valid_chain(self.rows,4))

    def test_orphan_or_reused_parent_is_rejected(self):
        for missing in (1,2,3,4):
            rows=copy.deepcopy(self.rows);del rows[missing]
            self.assertFalse(runtime.valid_chain(rows,4))
        for reused in (1,2,3):
            rows=copy.deepcopy(self.rows);rows[reused]['born']=50
            self.assertFalse(runtime.valid_chain(rows,4))

    def test_unreadable_or_unrelated_parent_is_rejected(self):
        rows=copy.deepcopy(self.rows);rows[2].pop('born')
        self.assertFalse(runtime.valid_chain(rows,4))
        rows=copy.deepcopy(self.rows);rows[3]['name']='powershell.exe'
        self.assertFalse(runtime.valid_chain(rows,4))

    def test_inactive_host_cannot_reserve_or_overwrite_live_heartbeat(self):
        with patch.object(schedule.argparse.ArgumentParser,'parse_args') as args, \
             patch.object(schedule.Path,'read_text',return_value='{"coordination_config":"local","conversation_id":"unused"}'), \
             patch.object(schedule,'Coordinator'),patch.object(schedule,'active_host',return_value=False), \
             patch.object(schedule.shutil,'which',return_value='agentapi'), \
             patch.object(schedule,'tick') as tick,patch.object(schedule,'heartbeat') as heartbeat:
            args.return_value.config=Path('config.json')
            schedule.main()
            tick.assert_not_called();heartbeat.assert_not_called()


if __name__=='__main__': unittest.main()
