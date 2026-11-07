import subprocess
import sys
import time
import unittest
from pathlib import Path

import psutil

import launcher


class LauncherTests(unittest.TestCase):
    def test_config_uses_selected_paths_and_tested_defaults(self):
        state = Path.cwd() / 'test state'
        model = state / 'tiel.gguf'
        cfg = launcher.config_for(state, model, '127.0.0.1', 131072, 12, 640, None)
        self.assertEqual(cfg['arch'], 'qwen35moe')
        self.assertEqual(cfg['context'], 131072)
        self.assertEqual(cfg['model_name'], 'tiel-coder')
        self.assertEqual(cfg['args'][0:2], ['--model', str(model)])
        self.assertEqual(cfg['args'][cfg['args'].index('--kv') + 1], 'q8_0')
        self.assertTrue(Path(cfg['cwd']).is_absolute())
        self.assertFalse(any('api_key' in key for key in cfg))

    def test_tailscale_reuses_only_its_own_target(self):
        target = 'http://127.0.0.1:8092'
        route = {'TCP': {'443': {'HTTPS': True}}, 'Web': {
            'host.example.ts.net:443': {'Handlers': {'/': {'Proxy': target}}}}}
        self.assertTrue(launcher.existing_serve_route(route, 443, target))
        self.assertFalse(launcher.existing_serve_route(route, 8443, target))
        with self.assertRaisesRegex(RuntimeError, 'already in use'):
            launcher.existing_serve_route(route, 443, 'http://127.0.0.1:9999')
        route['AllowFunnel'] = {'host.example.ts.net:443': True}
        with self.assertRaisesRegex(RuntimeError, 'Funnel'):
            launcher.existing_serve_route(route, 443, target)

    def test_omp_template_uses_an_environment_variable_for_the_key(self):
        template = (Path(launcher.__file__).parent / 'omp.models.yml').read_text()
        self.assertIn('apiKey: POLYSTRATA_API_KEY', template)
        self.assertIn('requiresReasoningContentForToolCalls: true', template)

    def test_forced_shutdown_cleans_up_the_owned_process_tree(self):
        command = ('import subprocess, sys, time; '
                   'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]); time.sleep(30)')
        with subprocess.Popen([sys.executable, '-c', command]) as server:
            root = psutil.Process(server.pid)
            deadline = time.monotonic() + 5
            children = []
            while len(children) < 2 and time.monotonic() < deadline:
                children = root.children(recursive=True)
                time.sleep(0.02)
            self.assertTrue(children)
            try:
                launcher.stop_server(server)
                self.assertIsNotNone(server.poll())
                self.assertTrue(all(not child.is_running() for child in children))
            finally:
                for child in children:
                    if child.is_running():
                        child.terminate()
                if server.poll() is None:
                    server.terminate()


if __name__ == '__main__':
    unittest.main()
