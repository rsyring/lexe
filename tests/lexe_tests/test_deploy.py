from datetime import date
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from lexe.config import Hook, HookConfig, LexeConfig
from lexe.deploy import Deploy


class FakeDate:
    @staticmethod
    def today() -> date:
        return date(2026, 4, 19)


class TestDeploy:
    def test_run(self, tmp_path, monkeypatch, capsys):
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

        monkeypatch.setattr('lexe.deploy.date', FakeDate)
        monkeypatch.setattr('lexe.deploy.sub_run', fake_sub_run)

        config = LexeConfig(app_name='hello', vm_host_name='hello-vm', public_service=None)
        with patch('lexe.deploy.docker_ssh_command', return_value=None):
            Deploy(config=config, app_dpath=tmp_path).run()

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
            ((('docker', 'pussh', image_ref, 'hello-vm.exe.xyz')), {'cwd': tmp_path, 'env': None}),
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

    def test_run_requires_clean_git_worktree_by_default(self, tmp_path, monkeypatch):
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            (tmp_path / name).write_text('x')

        def fake_sub_run(*args, **kwargs):
            if args == ('git', 'status', '--short'):
                return CompletedProcess(args, 0, stdout=' M Dockerfile\n', stderr='')
            raise AssertionError('unexpected command')

        monkeypatch.setattr('lexe.deploy.sub_run', fake_sub_run)

        config = LexeConfig(app_name='hello', vm_host_name='hello-vm', public_service=None)

        with pytest.raises(Exception, match='Git working tree is dirty'):
            Deploy(config=config, app_dpath=tmp_path).run()

    def test_run_appends_dirty_suffix_when_allowed(self, tmp_path, monkeypatch, capsys):
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

        monkeypatch.setattr('lexe.deploy.date', FakeDate)
        monkeypatch.setattr('lexe.deploy.sub_run', fake_sub_run)

        config = LexeConfig(app_name='hello', vm_host_name='hello-vm', public_service=None)
        with patch('lexe.deploy.docker_ssh_command', return_value=None):
            Deploy(config=config, app_dpath=tmp_path, allow_dirty=True).run()

        image_ref = 'hello:v2026-04-19-abcdef1-dirty'
        assert ('docker', 'build', '-t', image_ref, '.') in [call[0] for call in calls]
        assert f'Deploying {image_ref} to hello-vm.exe.xyz.\n' in capsys.readouterr().out

    def test_run_uses_test_key_for_docker_pussh(self, tmp_path, monkeypatch):
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

        monkeypatch.setattr('lexe.deploy.date', FakeDate)
        monkeypatch.setattr('lexe.deploy.sub_run', fake_sub_run)
        monkeypatch.setattr('lexe.deploy.use_exe_dev_test_key', lambda: True)
        monkeypatch.setattr('lexe.deploy.exe_dev_test_key_fpath', lambda: key_fpath)

        config = LexeConfig(app_name='hello', vm_host_name='hello-vm', public_service=None)
        with patch('lexe.deploy.docker_ssh_command', return_value='ssh -i test-key'):
            Deploy(config=config, app_dpath=tmp_path).run()

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
                'env': {'SSH_STRICT_HOST_KEY_CHECKING': 'accept-new'},
            },
        )

    def test_run_executes_hooks(self, tmp_path, monkeypatch, capsys):
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

        monkeypatch.setattr('lexe.deploy.date', FakeDate)
        monkeypatch.setattr('lexe.deploy.sub_run', fake_sub_run)

        config = LexeConfig(
            app_name='hello',
            vm_host_name='hello-vm',
            hooks=HookConfig(
                pre_start=(Hook(service='web', command='echo pre'),),
                post_start=(Hook(service='worker', command=('python', '-c', 'print(1)')),),
            ),
        )

        with patch('lexe.deploy.docker_ssh_command', return_value=None):
            Deploy(config=config, app_dpath=tmp_path).run()

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
            '--no-deps',
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
            '--no-deps',
            '--env',
            'LEXE_HOOK_NAME=post-start',
            '--entrypoint',
            'python',
            'worker',
            '-c',
            'print(1)',
        ) in hook_calls
        assert 'Running pre-start hook 1 on service web: echo pre\n' in capsys.readouterr().out

    def test_post_start_hook_failure_is_reported(self, tmp_path, monkeypatch, capsys):
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

        monkeypatch.setattr('lexe.deploy.date', FakeDate)
        monkeypatch.setattr('lexe.deploy.sub_run', fake_sub_run)

        config = LexeConfig(
            app_name='hello',
            vm_host_name='hello-vm',
            hooks=HookConfig(post_start=(Hook(service='web', command='echo post'),)),
        )

        with patch('lexe.deploy.docker_ssh_command', return_value=None):
            Deploy(config=config, app_dpath=tmp_path).run()

        assert (
            'Post-start hook 1 failed on service web with exit code 12.\n'
            in capsys.readouterr().out
        )
