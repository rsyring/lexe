from contextlib import nullcontext
from subprocess import CompletedProcess
from unittest.mock import patch

from lexe.config import CLIOpts, ConfigOpts, LexeConfig
from lexe.status import Status


def make_config_opts(tmp_path, *, healthcheck_url=None):
    config_data = {
        'project': {'path': tmp_path, 'name': 'demo', 'vm-host': 'demo-vm'},
        'services': {'web': {}},
    }
    if healthcheck_url:
        config_data['public'] = {'healthcheck-url': healthcheck_url}

    return ConfigOpts(config=LexeConfig.model_validate(config_data), opts=CLIOpts())


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
        config_opts = make_config_opts(tmp_path, healthcheck_url='https://demo.exe.xyz/health')

        with (
            patch('lexe.status.docker_host_url', return_value=nullcontext('ssh://demo-vm.exe.xyz')),
            patch('lexe.status.docker_client_env', return_value=nullcontext({})),
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
            Status(config_opts=config_opts, exe_dev=exe_dev).run()

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
        config_opts = make_config_opts(tmp_path)

        with (
            patch('lexe.status.docker_host_url', return_value=nullcontext('ssh://demo-vm.exe.xyz')),
            patch('lexe.status.docker_client_env', return_value=nullcontext({})),
        ):
            Status(config_opts=config_opts, exe_dev=exe_dev).run()

        assert capsys.readouterr().out == (
            'App: demo\n'
            'VM host: demo-vm\n'
            'VM reachable: no\n'
            'Compose project running: no\n'
            'Latest log entry: none\n'
            'Healthcheck: not configured\n'
        )
