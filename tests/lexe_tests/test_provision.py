from dataclasses import dataclass, field
from subprocess import CompletedProcess

from lexe.config import LexeConfig
from lexe.provision import Destroy, ExeDev, Provision


@dataclass
class FakeExeDev:
    ensure_vm_result: bool = False
    destroy_vm_result: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def ensure_vm(self, vm_name: str) -> bool:
        self.calls.append(('ensure_vm', vm_name))
        return self.ensure_vm_result

    def wait_for_ssh(self, vm_name: str) -> None:
        self.calls.append(('wait_for_ssh', vm_name))

    def ensure_docker(self, vm_name: str) -> None:
        self.calls.append(('ensure_docker', vm_name))

    def make_public(self, vm_name: str) -> None:
        self.calls.append(('make_public', vm_name))

    def destroy_vm(self, vm_name: str) -> bool:
        self.calls.append(('destroy_vm', vm_name))
        return self.destroy_vm_result


def test_provision_run(capsys):
    config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service='web')
    exe_dev = FakeExeDev(ensure_vm_result=True)

    Provision(config=config, exe_dev=exe_dev).run()

    assert exe_dev.calls == [
        ('ensure_vm', 'demo-vm'),
        ('wait_for_ssh', 'demo-vm'),
        ('ensure_docker', 'demo-vm'),
        ('make_public', 'demo-vm'),
    ]
    assert capsys.readouterr().out == (
        'Loaded lexe config for demo (demo-vm).\n'
        'Created exe.dev VM: demo-vm\n'
        'Waiting for SSH reachability...\n'
        'Verifying Docker availability...\n'
        'Enabling public HTTP proxy for service: web\n'
        'Provision complete.\n'
    )


def test_destroy_run(capsys):
    config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service=None)
    exe_dev = FakeExeDev(destroy_vm_result=True)

    Destroy(config=config, exe_dev=exe_dev).run()

    assert exe_dev.calls == [('destroy_vm', 'demo-vm')]
    assert capsys.readouterr().out == (
        'Loaded lexe config for demo (demo-vm).\nDestroyed exe.dev VM: demo-vm\nDestroy complete.\n'
    )


def test_destroy_run_when_vm_missing(capsys):
    config = LexeConfig(app_name='demo', vm_host_name='demo-vm', public_service=None)
    exe_dev = FakeExeDev(destroy_vm_result=False)

    Destroy(config=config, exe_dev=exe_dev).run()

    assert exe_dev.calls == [('destroy_vm', 'demo-vm')]
    assert capsys.readouterr().out == (
        'Loaded lexe config for demo (demo-vm).\nNo exe.dev VM found: demo-vm\nDestroy complete.\n'
    )


def test_exe_dev_ensure_vm_creates_missing_vm(monkeypatch):
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


def test_exe_dev_wait_for_ssh_retries_until_success(monkeypatch):
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

    ExeDev(wait_timeout_seconds=1, wait_interval_seconds=0).wait_for_ssh('demo-vm')

    assert len(calls) == 2
    assert all(call[0] == ('exe.dev', 'ssh', 'demo-vm', 'true') for call in calls)


def test_exe_dev_destroy_vm_removes_existing_vm(monkeypatch):
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


def test_exe_dev_destroy_vm_is_noop_when_missing(monkeypatch):
    calls = []

    def fake_ssh(*args, **kwargs):
        calls.append((args, kwargs))
        return CompletedProcess(args, 0, stdout='{"vms": []}', stderr='')

    monkeypatch.setattr('lexe.provision.ssh', fake_ssh)

    assert ExeDev().destroy_vm('demo-vm') is False
    assert calls == [((('exe.dev', 'ls', '--json')), {'capture': True})]
