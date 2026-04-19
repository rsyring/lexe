from subprocess import CompletedProcess
from unittest.mock import patch

from lexe.config import LexeConfig
from lexe.status import Status


class FakeExeDev:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.calls = []

    def host_ssh(self, vm_name, *args, **kwargs):
        self.calls.append((vm_name, args, kwargs))
        return CompletedProcess(('ssh',), self.returncode, stdout='', stderr='')


class TestStatus:
    def test_run(self, tmp_path, capsys):
        (tmp_path / 'lexe-logs.md').write_text('old\nlatest entry\n')
        exe_dev = FakeExeDev(returncode=0)
        config = LexeConfig(
            app_name='demo',
            vm_host_name='demo-vm',
            healthcheck_url='https://demo.exe.xyz/health',
        )

        with (
            patch('lexe.status.docker_ssh_command', return_value=None),
            patch(
                'lexe.status.sub_run',
                return_value=CompletedProcess(
                    ('docker',),
                    0,
                    stdout='NAME SERVICE STATUS\ndemo-web-1 web running(healthy)\n',
                    stderr='',
                ),
            ),
            patch('lexe.status.urlopen') as mock_urlopen,
        ):
            mock_urlopen.return_value.getcode.return_value = 200
            Status(config=config, app_dpath=tmp_path, exe_dev=exe_dev).run()

        assert exe_dev.calls == [('demo-vm', ('true',), {'capture': True, 'check': False})]
        assert capsys.readouterr().out == (
            'App: demo\n'
            'VM host: demo-vm\n'
            'VM reachable: yes\n'
            'Compose project running: yes\n'
            'Compose status details:\n'
            'NAME SERVICE STATUS\n'
            'demo-web-1 web running(healthy)\n'
            'Latest log entry: latest entry\n'
            'Healthcheck: healthy (200) https://demo.exe.xyz/health\n'
        )

    def test_run_when_unreachable(self, tmp_path, capsys):
        exe_dev = FakeExeDev(returncode=255)
        config = LexeConfig(app_name='demo', vm_host_name='demo-vm', healthcheck_url=None)

        with patch('lexe.status.docker_ssh_command', return_value=None):
            Status(config=config, app_dpath=tmp_path, exe_dev=exe_dev).run()

        assert capsys.readouterr().out == (
            'App: demo\n'
            'VM host: demo-vm\n'
            'VM reachable: no\n'
            'Compose project running: no\n'
            'Latest log entry: none\n'
            'Healthcheck: not configured\n'
        )