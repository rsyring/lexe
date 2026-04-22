from contextlib import nullcontext
from datetime import date
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from lexe.config import CLIOpts, ConfigOpts, LexeConfig
from lexe.deploy import Deploy


class FakeDate:
    @staticmethod
    def today() -> date:
        return date(2026, 4, 19)


def make_config_opts(tmp_path, *, services=None) -> ConfigOpts:
    config = LexeConfig.model_validate(
        {
            'project': {'path': tmp_path, 'name': 'hello', 'vm-host': 'hello-vm'},
            'services': services or {'web': {}},
        },
    )
    return ConfigOpts(config=config, opts=CLIOpts())


def make_test_cli_opts(key_fpath) -> CLIOpts:
    return CLIOpts(
        ssh_ident_fpath=key_fpath,
        ssh_host_key_check=False,
        ssh_known_hosts_manage=False,
    )


class TestDeploy:
    def test_run(self, tmp_path, capsys):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        calls = []

        def fake_sub_run(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[-1] == 'ps':
                return CompletedProcess(
                    args,
                    0,
                    stdout='NAME SERVICE STATUS\nhello-web-1 web running(healthy)\n',
                    stderr='',
                )
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch('lexe.deploy.docker_client_env', return_value=nullcontext({})),
        ):
            Deploy(config_opts=make_config_opts(tmp_path)).run()

        image_ref = 'hello:v2026-04-19-abcdef1'
        compose_env = {
            'COMPOSE_PROJECT_NAME': 'hello',
            'DOCKER_HOST': 'ssh://hello-vm.exe.xyz',
            'LEXE_IMAGE': image_ref,
        }

        assert calls == [
            ((('git', 'status', '--short')), {'capture': True, 'cwd': tmp_path}),
            ((('git', 'rev-parse', 'HEAD')), {'capture': True, 'cwd': tmp_path}),
            ((('docker', 'build', '-t', image_ref, '.')), {'cwd': tmp_path}),
            ((('docker', 'pussh', image_ref, 'hello-vm.exe.xyz')), {'cwd': tmp_path, 'env': {}}),
            (
                (
                    (
                        'docker',
                        'compose',
                        '-f',
                        tmp_path.joinpath('compose.yaml').name,
                        '-f',
                        tmp_path.joinpath('compose.server.yaml').name,
                        'up',
                        '-d',
                        '--wait',
                        '--wait-timeout',
                        '90',
                        '--force-recreate',
                        '--remove-orphans',
                        'web',
                    )
                ),
                {'cwd': tmp_path, 'env': compose_env},
            ),
            (
                (
                    (
                        'docker',
                        'compose',
                        '-f',
                        tmp_path.joinpath('compose.yaml').name,
                        '-f',
                        tmp_path.joinpath('compose.server.yaml').name,
                        'ps',
                    )
                ),
                {'capture': True, 'cwd': tmp_path, 'env': compose_env},
            ),
        ]
        assert capsys.readouterr().out == (
            'Loaded lexe config for hello (hello-vm).\n'
            f'Deploying {image_ref} to hello-vm.exe.xyz.\n'
            'Building image locally...\n'
            'Transferring image to remote VM...\n'
            'Starting services on remote VM...\n'
            'Remote compose status:\n'
            'NAME SERVICE STATUS\n'
            'hello-web-1 web running(healthy)\n'
            'Deploy complete.\n'
        )

    def test_run_starts_contingent_services_before_always_services(self, tmp_path):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        calls = []

        def fake_sub_run(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[-1] == 'ps':
                return CompletedProcess(args, 0, stdout='', stderr='')
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch('lexe.deploy.docker_client_env', return_value=nullcontext({})),
        ):
            Deploy(
                config_opts=make_config_opts(
                    tmp_path,
                    services={
                        'db': {'deploy': 'contingent'},
                        'web': {},
                        'schedule': {},
                    },
                ),
            ).run()

        contingent_call = (
            (
                'docker',
                'compose',
                '-f',
                'compose.yaml',
                '-f',
                'compose.server.yaml',
                'up',
                '-d',
                '--wait',
                '--wait-timeout',
                '90',
                '--no-recreate',
                '--remove-orphans',
                'db',
            ),
            {
                'cwd': tmp_path,
                'env': {
                    'COMPOSE_PROJECT_NAME': 'hello',
                    'DOCKER_HOST': 'ssh://hello-vm.exe.xyz',
                    'LEXE_IMAGE': 'hello:v2026-04-19-abcdef1',
                },
            },
        )
        always_call = (
            (
                'docker',
                'compose',
                '-f',
                'compose.yaml',
                '-f',
                'compose.server.yaml',
                'up',
                '-d',
                '--wait',
                '--wait-timeout',
                '90',
                '--force-recreate',
                '--remove-orphans',
                'web',
                'schedule',
            ),
            {
                'cwd': tmp_path,
                'env': {
                    'COMPOSE_PROJECT_NAME': 'hello',
                    'DOCKER_HOST': 'ssh://hello-vm.exe.xyz',
                    'LEXE_IMAGE': 'hello:v2026-04-19-abcdef1',
                },
            },
        )

        assert contingent_call in calls
        assert always_call in calls
        assert calls.index(contingent_call) < calls.index(always_call)

    def test_run_restart_all_restarts_contingent_services(self, tmp_path):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        calls = []

        def fake_sub_run(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[-1] == 'ps':
                return CompletedProcess(args, 0, stdout='', stderr='')
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch('lexe.deploy.docker_client_env', return_value=nullcontext({})),
        ):
            Deploy(
                config_opts=make_config_opts(
                    tmp_path,
                    services={
                        'db': {'deploy': 'contingent'},
                        'web': {},
                    },
                ),
                restart_all=True,
            ).run()

        assert (
            (
                'docker',
                'compose',
                '-f',
                'compose.yaml',
                '-f',
                'compose.server.yaml',
                'up',
                '-d',
                '--wait',
                '--wait-timeout',
                '90',
                '--force-recreate',
                '--remove-orphans',
                'db',
            ),
            {
                'cwd': tmp_path,
                'env': {
                    'COMPOSE_PROJECT_NAME': 'hello',
                    'DOCKER_HOST': 'ssh://hello-vm.exe.xyz',
                    'LEXE_IMAGE': 'hello:v2026-04-19-abcdef1',
                },
            },
        ) in calls

    def test_run_requires_clean_git_worktree_by_default(self, tmp_path):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        def fake_sub_run(*args, **kwargs):
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout=' M Dockerfile\n', stderr='')
            raise AssertionError('unexpected command')

        with (
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            pytest.raises(Exception, match='Git working tree is dirty'),
        ):
            Deploy(config_opts=make_config_opts(tmp_path)).run()

    def test_run_requires_direct_deploy_service(self, tmp_path):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        def fake_sub_run(*args, **kwargs):
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            raise AssertionError('unexpected command')

        with (
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            pytest.raises(Exception, match='No services are configured for direct deploy'),
        ):
            Deploy(
                config_opts=make_config_opts(
                    tmp_path,
                    services={'db': {'deploy': 'contingent'}},
                ),
            ).run()

    def test_run_appends_dirty_suffix_when_allowed(self, tmp_path, capsys):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        calls = []

        def fake_sub_run(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout=' M Dockerfile\n', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[-1] == 'ps':
                return CompletedProcess(args, 0, stdout='', stderr='')
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch('lexe.deploy.docker_client_env', return_value=nullcontext({})),
        ):
            Deploy(config_opts=make_config_opts(tmp_path), allow_dirty=True).run()

        image_ref = 'hello:v2026-04-19-abcdef1-dirty'
        assert ('docker', 'build', '-t', image_ref, '.') in [call[0] for call in calls]
        assert f'Deploying {image_ref} to hello-vm.exe.xyz.\n' in capsys.readouterr().out

    def test_run_uses_test_key_for_docker_pussh(self, tmp_path):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')
        key_fpath = tmp_path / 'test-key'
        key_fpath.write_text('x')

        calls = []

        def fake_sub_run(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[-1] == 'ps':
                return CompletedProcess(args, 0, stdout='', stderr='')
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch(
                'lexe.deploy.docker_client_env',
                return_value=nullcontext({'PATH': '/tmp/test-bin'}),
            ),
        ):
            Deploy(
                ConfigOpts(
                    config=make_config_opts(tmp_path).config,
                    opts=make_test_cli_opts(key_fpath),
                ),
            ).run()

        assert calls[3] == (
            (
                'docker',
                'pussh',
                '--ssh-key',
                key_fpath,
                'hello:v2026-04-19-abcdef1',
                'hello-vm.exe.xyz',
            ),
            {
                'cwd': tmp_path,
                'env': {
                    'PATH': '/tmp/test-bin',
                    'SSH_STRICT_HOST_KEY_CHECKING': 'no',
                },
            },
        )

    def test_run_executes_hooks_for_direct_deploy_services_only(self, tmp_path, capsys):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        calls = []

        def fake_sub_run(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[-1] == 'ps':
                return CompletedProcess(args, 0, stdout='', stderr='')
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch('lexe.deploy.docker_client_env', return_value=nullcontext({})),
        ):
            Deploy(
                config_opts=make_config_opts(
                    tmp_path,
                    services={
                        'db': {
                            'deploy': 'contingent',
                            'hooks': {'start-pre': 'echo skip'},
                        },
                        'web': {'hooks': {'start-pre': 'echo pre'}},
                        'worker': {'hooks': {'start-post': [['python', '-c', 'print(1)']]}},
                    },
                ),
            ).run()

        hook_calls = [call[0] for call in calls if 'run' in call[0]]
        assert (
            'docker',
            'compose',
            '-f',
            'compose.yaml',
            '-f',
            'compose.server.yaml',
            'run',
            '--rm',
            '--env',
            'LEXE_HOOK_NAME=pre-start',
            '--entrypoint',
            'sh',
            'web',
            '-lc',
            'echo pre',
        ) in hook_calls
        assert (
            'docker',
            'compose',
            '-f',
            'compose.yaml',
            '-f',
            'compose.server.yaml',
            'run',
            '--rm',
            '--env',
            'LEXE_HOOK_NAME=post-start',
            '--entrypoint',
            'python',
            'worker',
            '-c',
            'print(1)',
        ) in hook_calls
        assert not any(call[-3] == 'db' for call in hook_calls)
        assert 'Running pre-start hook 1 on service web: echo pre\n' in capsys.readouterr().out

    def test_post_start_hook_failure_is_reported(self, tmp_path, capsys):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        def fake_sub_run(*args, **kwargs):
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout='', stderr='')
            if args == ('git', 'rev-parse', 'HEAD'):
                return CompletedProcess(args, 0, stdout='abcdef1234567890\n', stderr='')
            if args[:8] == (
                'docker',
                'compose',
                '-f',
                'compose.yaml',
                '-f',
                'compose.server.yaml',
                'run',
                '--rm',
            ):
                return CompletedProcess(args, 12, stdout='bad stdout\n', stderr='bad stderr\n')
            return CompletedProcess(args, 0, stdout='', stderr='')

        with (
            patch('lexe.deploy.date', FakeDate),
            patch('lexe.deploy.sub_run', side_effect=fake_sub_run),
            patch(
                'lexe.deploy.docker_host_url',
                return_value=nullcontext('ssh://hello-vm.exe.xyz'),
            ),
            patch('lexe.deploy.docker_client_env', return_value=nullcontext({})),
        ):
            Deploy(
                config_opts=make_config_opts(
                    tmp_path,
                    services={'web': {'hooks': {'start-post': 'echo post'}}},
                ),
            ).run()

        assert (
            'Post-start hook 1 failed on service web with exit code 12.\n'
            in capsys.readouterr().out
        )
