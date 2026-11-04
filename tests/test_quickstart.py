import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('quickstart', Path(__file__).resolve().parents[1] / 'tools/quickstart.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class QuickstartTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory) / 'source'; root.mkdir()
        host = Path(directory) / 'host'; host.mkdir()
        return root, host, Path(directory) / 'data'

    def test_check_is_read_only_and_uses_no_subprocesses(self):
        with tempfile.TemporaryDirectory() as directory:
            root, host, runtime = self.fixture(directory); run = Mock()
            before = sorted(str(p) for p in Path(directory).rglob('*'))
            result = module.setup(root, host, runtime, check=True, run=run)
            self.assertTrue(result['check_only']); run.assert_not_called()
            self.assertEqual(before, sorted(str(p) for p in Path(directory).rglob('*')))

    def test_host_must_be_closed_before_any_command(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.fixture(directory); run = Mock()
            with self.assertRaisesRegex(ValueError, 'Exit Stream Dock'):
                module.setup(*paths, running=True, run=run)
            run.assert_not_called()

    def test_existing_public_plugin_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root, host, runtime = self.fixture(directory)
            plugin = host / 'plugins' / module.NAMESPACE; plugin.mkdir(parents=True)
            sentinel = plugin / 'sentinel'; sentinel.write_text('keep')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                module.setup(root, host, runtime)
            self.assertEqual(sentinel.read_text(), 'keep')

    def test_existing_runtime_and_environment_are_preserved(self):
        for kind in ('runtime', 'venv'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root, host, runtime = self.fixture(directory)
                selected = runtime if kind == 'runtime' else root / '.venv'
                selected.mkdir(); sentinel = selected / 'sentinel'; sentinel.write_text('keep')
                with self.assertRaises(ValueError): module.setup(root, host, runtime)
                self.assertEqual(sentinel.read_text(), 'keep')

    def test_commands_are_argument_lists_and_stop_on_failure(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix='quickstart space ') as directory:
            paths = self.fixture(directory); run = Mock()
            result = module.setup(*paths, run=run)
            self.assertEqual(run.call_count, 4)
            self.assertEqual(result['commands'][-1][-1], str(paths[0] / '.venv/Scripts/pythonw.exe'))
            self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))
            run = Mock(side_effect=subprocess.CalledProcessError(1, 'pip'))
            with self.assertRaises(subprocess.CalledProcessError): module.setup(*paths, run=run)
            self.assertEqual(run.call_count, 1)
