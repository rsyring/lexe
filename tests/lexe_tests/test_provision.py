from dataclasses import dataclass, field
import json
from pathlib import Path
from subprocess import CompletedProcess

from lexe.config import LexeConfig
from lexe.provision import Destroy, ExeDev, Provision


KNOWN_HOSTS_FPATH = Path('/tmp/lexe-known-hosts-test')


@dataclass
class FakeExeDev:
    ensure_vm_result: bool = False
    ensure_containerd_image_store_result: bool = False
    destroy_vm_result: bool = False
    ssh_known_hosts_fpath: Path | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    def ensure_vm(self, vm_name: str) -> bool:
        self.calls.append(('ensure_vm', vm_name))
        return self.ensure_vm_result

    def wait_for_ssh(self, vm_name: str) -> None:
        self.calls.append(('wait_for_ssh', vm_name))

    def ensure_docker(self, vm_name: str) -> None:
        self.calls.append(('ensure_docker', vm_name))

    def ensure_containerd_image_store(self, vm_name: str) -> bool:
        self.calls.append(('ensure_containerd_image_store', vm_name))
        return self.ensure_containerd_image_store_result

    def verify_containerd_image_store(self, vm_name: str) -> None:
        self.calls.append(('verify_containerd_image_store', vm_name))

    def make_public(self, vm_name: str) -> None:
        self.calls.append(('make_public', vm_name))

    def destroy_vm(self, vm_name: str) -> bool:
        self.calls.append(('destroy_vm', vm_name))
        return self.destroy_vm_result


class TestProvision:
    def test_run(self, capsys):
        config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service='web')
        exe_dev = FakeExeDev(ensure_vm_result=True, ensure_containerd_image_store_result=True)

        provision = Provision(config=config, app_dpath=Path('/repo/app'), exe_dev=exe_dev)

        provision.run()

        assert exe_dev.calls == [
            ('ensure_vm', 'demo-vm'),
            ('wait_for_ssh', 'demo-vm'),
            ('ensure_containerd_image_store', 'demo-vm'),
            ('ensure_docker', 'demo-vm'),
            ('verify_containerd_image_store', 'demo-vm'),
            ('make_public', 'demo-vm'),
        ]
        assert capsys.readouterr().out == (
            'Loaded lexe config for demo (demo-vm).\n'
            'Created exe.dev VM: demo-vm\n'
            'Waiting for SSH reachability...\n'
            'Ensuring Docker uses the containerd image store...\n'
            'Enabled Docker containerd image store.\n'
            'Verifying Docker availability...\n'
            'Verifying Docker containerd image store...\n'
            'Enabling public HTTP proxy for service: web\n'
            'Provision complete.\n'
        )
        assert provision.exe_dev.ssh_known_hosts_fpath == Path('/repo/app/deploy/ssh_known_hosts')

    def test_run_when_containerd_image_store_already_enabled(self, capsys):
        config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service=None)
        exe_dev = FakeExeDev(ensure_vm_result=False, ensure_containerd_image_store_result=False)

        Provision(config=config, app_dpath=Path('/repo/app'), exe_dev=exe_dev).run()

        assert exe_dev.calls == [
            ('ensure_vm', 'demo-vm'),
            ('wait_for_ssh', 'demo-vm'),
            ('ensure_containerd_image_store', 'demo-vm'),
            ('ensure_docker', 'demo-vm'),
            ('verify_containerd_image_store', 'demo-vm'),
        ]
        assert capsys.readouterr().out == (
            'Loaded lexe config for demo (demo-vm).\n'
            'Using existing exe.dev VM: demo-vm\n'
            'Waiting for SSH reachability...\n'
            'Ensuring Docker uses the containerd image store...\n'
            'Docker containerd image store already enabled.\n'
            'Verifying Docker availability...\n'
            'Verifying Docker containerd image store...\n'
            'Provision complete.\n'
        )


class TestDestroy:
    def test_run(self, capsys):
        config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service=None)
        exe_dev = FakeExeDev(destroy_vm_result=True)

        Destroy(config=config, exe_dev=exe_dev).run()

        assert exe_dev.calls == [('destroy_vm', 'demo-vm')]
        assert capsys.readouterr().out == (
            'Loaded lexe config for demo (demo-vm).\n'
            'Destroyed exe.dev VM: demo-vm\n'
            'Destroy complete.\n'
        )

    def test_run_when_vm_missing(self, capsys):
        config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service=None)
        exe_dev = FakeExeDev(destroy_vm_result=False)

        Destroy(config=config, exe_dev=exe_dev).run()

        assert exe_dev.calls == [('destroy_vm', 'demo-vm')]
        assert capsys.readouterr().out == (
            'Loaded lexe config for demo (demo-vm).\n'
            'No exe.dev VM found: demo-vm\n'
            'Destroy complete.\n'
        )


class TestExeDev:
    def test_ensure_vm_creates_missing_vm(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('exe.dev', 'ls', '--json'):
                return CompletedProcess(args, 0, stdout='{"vms": []}', stderr='')
            return CompletedProcess(args, 0, stdout='{"vm_name": "demo-vm"}', stderr='')

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        assert ExeDev().ensure_vm('demo-vm') is True
        assert calls == [
            ((('exe.dev', 'ls', '--json')), {'capture': True}),
            ((('exe.dev', 'new', '--name', 'demo-vm', '--json')), {'capture': True}),
        ]

    def test_wait_for_ssh_retries_until_success(self, monkeypatch):
        results = [
            CompletedProcess(('ssh',), 255, stdout='', stderr='not ready'),
            CompletedProcess(('ssh',), 0, stdout='', stderr=''),
        ]
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            return results.pop(0)

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)
        monkeypatch.setattr('lexe.provision.time.sleep', int)

        ExeDev(
            wait_timeout_seconds=1,
            wait_interval_seconds=0,
            ssh_known_hosts_fpath=KNOWN_HOSTS_FPATH,
        ).wait_for_ssh('demo-vm')

        assert len(calls) == 2
        assert all(
            call[0]
            == (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'true',
            )
            for call in calls
        )

    def test_ensure_docker_retries_until_success(self, monkeypatch):
        results = [
            CompletedProcess(('ssh',), 1, stdout='', stderr='docker restarting'),
            CompletedProcess(('ssh',), 0, stdout='28.2.2', stderr=''),
        ]
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            return results.pop(0)

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)
        monkeypatch.setattr('lexe.provision.time.sleep', int)

        ExeDev(
            wait_timeout_seconds=1,
            wait_interval_seconds=0,
            ssh_known_hosts_fpath=KNOWN_HOSTS_FPATH,
        ).ensure_docker('demo-vm')

        assert len(calls) == 2
        assert all(
            call[0]
            == (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'docker',
                'info',
                '--format',
                '{{.ServerVersion}}',
            )
            for call in calls
        )
        assert all(call[1] == {'capture': True, 'check': False} for call in calls)

    def test_ensure_containerd_image_store_restarts_docker_when_changed(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            if args[-3:] == ('sudo', 'cat', '/etc/docker/daemon.json'):
                return CompletedProcess(
                    args,
                    1,
                    stdout='',
                    stderr='cat: /etc/docker/daemon.json: No such file or directory',
                )
            return CompletedProcess(args, 0, stdout='', stderr='')

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        assert ExeDev(ssh_known_hosts_fpath=KNOWN_HOSTS_FPATH).ensure_containerd_image_store(
            'demo-vm',
        )
        assert calls[0] == (
            (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'sudo',
                'cat',
                '/etc/docker/daemon.json',
            ),
            {'capture': True, 'check': False},
        )
        assert calls[1] == (
            (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'sudo',
                'mkdir',
                '-p',
                '/etc/docker',
            ),
            {},
        )
        assert calls[2] == (
            (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'sudo',
                'tee',
                '/etc/docker/daemon.json',
            ),
            {
                'capture': True,
                'input': '{\n  "features": {\n    "containerd-snapshotter": true\n  }\n}\n',
            },
        )
        assert calls[3] == (
            (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'sudo',
                'systemctl',
                'restart',
                'docker',
            ),
            {'capture': True},
        )

    def test_ensure_containerd_image_store_merges_existing_daemon_config(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            if args[-3:] == ('sudo', 'cat', '/etc/docker/daemon.json'):
                return CompletedProcess(
                    args,
                    0,
                    stdout='{"debug": true, "features": {"other": false}}',
                    stderr='',
                )
            return CompletedProcess(args, 0, stdout='', stderr='')

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        assert ExeDev(ssh_known_hosts_fpath=KNOWN_HOSTS_FPATH).ensure_containerd_image_store(
            'demo-vm',
        )
        assert calls[2] == (
            (
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                'demo-vm.exe.xyz',
                'sudo',
                'tee',
                '/etc/docker/daemon.json',
            ),
            {
                'capture': True,
                'input': json.dumps(
                    {
                        'debug': True,
                        'features': {
                            'containerd-snapshotter': True,
                            'other': False,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + '\n',
            },
        )

    def test_ensure_containerd_image_store_is_noop_when_unchanged(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            return CompletedProcess(
                args,
                0,
                stdout='{"features": {"containerd-snapshotter": true}}',
                stderr='',
            )

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        assert (
            ExeDev(ssh_known_hosts_fpath=KNOWN_HOSTS_FPATH).ensure_containerd_image_store('demo-vm')
            is False
        )
        assert calls == [
            (
                (
                    '-o',
                    'StrictHostKeyChecking=accept-new',
                    '-o',
                    f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                    'demo-vm.exe.xyz',
                    'sudo',
                    'cat',
                    '/etc/docker/daemon.json',
                ),
                {'capture': True, 'check': False},
            ),
        ]

    def test_verify_containerd_image_store(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            return CompletedProcess(
                args,
                0,
                stdout='[["driver-type","io.containerd.snapshotter.v1"]]',
                stderr='',
            )

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        ExeDev(ssh_known_hosts_fpath=KNOWN_HOSTS_FPATH).verify_containerd_image_store('demo-vm')
        assert calls == [
            (
                (
                    '-o',
                    'StrictHostKeyChecking=accept-new',
                    '-o',
                    f'UserKnownHostsFile={KNOWN_HOSTS_FPATH}',
                    'demo-vm.exe.xyz',
                    'docker',
                    'info',
                    '--format',
                    '{{.DriverStatus}}',
                ),
                {'capture': True},
            ),
        ]

    def test_destroy_vm_removes_existing_vm(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ('exe.dev', 'ls', '--json'):
                return CompletedProcess(
                    args,
                    0,
                    stdout='{"vms": [{"vm_name": "demo-vm", "status": "running"}]}',
                    stderr='',
                )
            return CompletedProcess(args, 0, stdout='', stderr='')

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        assert ExeDev().destroy_vm('demo-vm') is True
        assert calls == [
            ((('exe.dev', 'ls', '--json')), {'capture': True}),
            ((('exe.dev', 'rm', 'demo-vm')), {'capture': True}),
        ]

    def test_destroy_vm_is_noop_when_missing(self, monkeypatch):
        calls = []

        def fake_ssh(*args, **kwargs):
            calls.append((args, kwargs))
            return CompletedProcess(args, 0, stdout='{"vms": []}', stderr='')

        monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

        assert ExeDev().destroy_vm('demo-vm') is False
        assert calls == [((('exe.dev', 'ls', '--json')), {'capture': True})]
