from dataclasses import dataclass, field
import json
import time

import click

from lexe.config import LexeConfig
from lexe.procs import ssh


@dataclass(frozen=True)
class ExeDevVm:
    vm_name: str
    status: str


@dataclass
class ExeDev:
    wait_timeout_seconds: int = 120
    wait_interval_seconds: int = 2

    def list_vms(self) -> dict[str, ExeDevVm]:
        result = ssh('exe.dev', 'ls', '--json', capture=True)
        payload = json.loads(result.stdout)
        return {
            vm['vm_name']: ExeDevVm(vm_name=vm['vm_name'], status=vm['status'])
            for vm in payload['vms']
        }

    def ensure_vm(self, vm_name: str) -> bool:
        if vm_name in self.list_vms():
            return False

        ssh('exe.dev', 'new', '--name', vm_name, '--json', capture=True)
        return True

    def wait_for_ssh(self, vm_name: str) -> None:
        deadline = time.monotonic() + self.wait_timeout_seconds

        while time.monotonic() < deadline:
            result = ssh('exe.dev', 'ssh', vm_name, 'true', capture=True, check=False)
            if result.returncode == 0:
                return
            time.sleep(self.wait_interval_seconds)

        raise click.ClickException(f'Timed out waiting for SSH reachability on {vm_name!r}.')

    def ensure_docker(self, vm_name: str) -> None:
        ssh(
            'exe.dev',
            'ssh',
            vm_name,
            'docker',
            'info',
            '--format',
            '{{.ServerVersion}}',
            capture=True,
        )

    def make_public(self, vm_name: str) -> None:
        ssh('exe.dev', 'share', 'set-public', vm_name, capture=True)

    def destroy_vm(self, vm_name: str) -> bool:
        if vm_name not in self.list_vms():
            return False

        ssh('exe.dev', 'rm', vm_name, capture=True)
        return True


@dataclass
class Provision:
    config: LexeConfig
    exe_dev: ExeDev = field(default_factory=ExeDev)

    def run(self) -> None:
        click.echo(f'Loaded lexe config for {self.config.app_name} ({self.config.vm_host_name}).')

        created = self.exe_dev.ensure_vm(self.config.vm_host_name)
        if created:
            click.echo(f'Created exe.dev VM: {self.config.vm_host_name}')
        else:
            click.echo(f'Using existing exe.dev VM: {self.config.vm_host_name}')

        click.echo('Waiting for SSH reachability...')
        self.exe_dev.wait_for_ssh(self.config.vm_host_name)

        click.echo('Verifying Docker availability...')
        self.exe_dev.ensure_docker(self.config.vm_host_name)

        if self.config.public_service:
            click.echo(f'Enabling public HTTP proxy for service: {self.config.public_service}')
            self.exe_dev.make_public(self.config.vm_host_name)

        click.echo('Provision complete.')


@dataclass
class Destroy:
    config: LexeConfig
    exe_dev: ExeDev = field(default_factory=ExeDev)

    def run(self) -> None:
        click.echo(f'Loaded lexe config for {self.config.app_name} ({self.config.vm_host_name}).')

        destroyed = self.exe_dev.destroy_vm(self.config.vm_host_name)
        if destroyed:
            click.echo(f'Destroyed exe.dev VM: {self.config.vm_host_name}')
        else:
            click.echo(f'No exe.dev VM found: {self.config.vm_host_name}')

        click.echo('Destroy complete.')
