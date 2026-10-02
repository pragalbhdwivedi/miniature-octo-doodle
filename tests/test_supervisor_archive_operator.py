import copy
from pathlib import Path
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import unittest
from unittest.mock import patch
import supervisor_archive as archive
import supervisor_archive_operator as operator
from test_supervisor_archive import fixture, NOW


class Store:
    def __init__(self,state): self.state=copy.deepcopy(state)
    def read(self): return {'value':copy.deepcopy(self.state)}
    def mutate(self,operation):
        candidate=copy.deepcopy(self.state)
        result=operation(candidate)
        self.state=candidate
        return result


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config={'enabled':True,'directory':str(Path(self.temp.name)/'private')}
        self.state=fixture();self.store=Store(self.state)

    def request(self): return {'action':'ongoing_archive','revision':self.state['supervision']['revision']}

    def test_operator_cas_archives_only_when_enabled_with_expected_revision(self):
        with patch.object(operator.archive,'archive_state', wraps=lambda s,d,retain: original_archive(s,d,retain=retain,now=NOW)):
            result=operator.run(self.store,self.request(),self.config)
        self.assertEqual(result['archived'],5)
        history=operator.run(self.store,{'action':'ongoing_archive_history','limit':2},{})
        self.assertEqual(history['total'],5)
        self.assertEqual(len(history['tasks']),2)
        with self.assertRaises(archive.ArchiveError):
            operator.run(self.store,self.request(),self.config)

    def test_disabled_path_injection_and_changed_revision_rejected(self):
        for request,config in [(self.request(),{}),({**self.request(),'directory':'/other'},self.config),
                               ({**self.request(),'revision':-1},self.config)]:
            with self.assertRaises(archive.ArchiveError): operator.run(self.store,request,config)
        self.assertEqual(self.store.state,self.state)

    def test_filter_catalog_preserves_remaining_scope_and_rejects_reused_key(self):
        compacted,_=archive.archive_state(self.state,self.config['directory'],now=NOW)
        # Runtime fields are excluded from immutable catalog scope hashing.
        catalog=[{k:v for k,v in j.items() if k not in ('state','supervisor_id','coding','publication','pr_observation','pr_observed_at')} for j in self.state['ongoing']['jobs']]
        filtered=operator.filter_catalog(compacted,catalog)
        self.assertEqual([x['id'] for x in filtered],[f'task-{n}' for n in range(6,26)])
        altered=copy.deepcopy(catalog);altered[0]['prompt']='different task'
        with self.assertRaises(archive.ArchiveError): operator.filter_catalog(compacted,altered)
        del compacted['supervision']['archive_index']
        with self.assertRaises(archive.ArchiveError): operator.filter_catalog(compacted,catalog)

    def test_rpc_does_not_accept_unbounded_history_or_external_file_paths(self):
        for req in [{'action':'ongoing_archive_history','limit':10000},
                    {'action':'ongoing_archive_history','path':'/private'}]:
            with self.assertRaises(archive.ArchiveError): operator.run(self.store,req,{})

    def test_noop_under_twenty_requires_no_archive_file(self):
        store=Store(fixture(6))
        result=operator.run(store,{'action':'ongoing_archive','revision':6},self.config)
        self.assertEqual(result['archived'],0)
        self.assertFalse(Path(self.config['directory']).exists())

    def test_catalog_above_one_hundred_is_reduced_only_by_verified_archives(self):
        state=fixture(125)
        compacted,_=archive.archive_state(state,self.config['directory'],now=NOW)
        filtered=operator.filter_catalog(compacted,state['ongoing']['jobs'])
        self.assertEqual(len(filtered),20)
        self.assertEqual(len(compacted['supervision']['by_key']),125)
        self.assertEqual(compacted['supervision']['next_id'],126)
        page=archive.history_index(compacted)
        self.assertEqual((page['total'],len(page['tasks']),page['omitted']),(105,100,5))


original_archive=archive.archive_state
if __name__=='__main__': unittest.main()
