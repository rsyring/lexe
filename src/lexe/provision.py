from dataclasses import dataclass, field
import json
import time

import click

from lexe.config import CLIOpts, ConfigOpts, LexeConfig
from lexe.procs import ssh


CONTAINERD_SNAPSHOTTER_STATUS = 'io.containerd.snapshotter.v1'


@dataclass(frozen=True)
class ExeDevVm:
    vm_name: str
    status: str


@dataclass
class ExeDev:
    opts: CLIOpts = field(default_factory=CLIOpts)
    wait_timeout_seconds: int = 120
    wait_interval_seconds: int = 2

    def host_ssh_failure_message(self, vm_name: str, command: tuple[str, ...], result) -> str:
        message = [
            f'Command failed on {vm_name!r} with exit code {result.returncode}: '
            + ' '.join(command),
        ]
        if stdout := (result.stdout or '').strip():
            message.append(f'STDOUT: {stdout}')
        if stderr := (result.stderr or '').strip():
            message.append(f'STDERR: {stderr}')
        return '\n'.join(message)

    def list_vms(self) -> dict[str, ExeDevVm]:
        result = ssh('exe.dev', 'ls', '--json', capture=True, opts=self.opts)
        payload = json.loads(result.stdout)
        return {
            vm['vm_name']: ExeDevVm(vm_name=vm['vm_name'], status=vm['status'])
            for vm in payload['vms']
        }

    def ensure_vm(self, vm_name: str) -> bool:
        if vm_name in self.list_vms():
            return False

        ssh('exe.dev', 'new', '--name', vm_name, '--json', capture=True, opts=self.opts)
        return True

    def vm_ssh_dest(self, vm_name: str) -> str:
        return f'{vm_name}.exe.xyz'

    def host_ssh(self, vm_name: str, *args, **kwargs):
        return ssh(self.vm_ssh_dest(vm_name), *args, opts=self.opts, **kwargs)

    def wait_for_ssh(self, vm_name: str) -> None:
        deadline = time.monotonic() + self.wait_timeout_seconds

        while time.monotonic() < deadline:
            result = self.host_ssh(vm_name, 'true', capture=True, check=False)
            if result.returncode == 0:
                return
            time.sleep(self.wait_interval_seconds)

        raise click.ClickException(f'Timed out waiting for SSH reachability on {vm_name!r}.')

    def ensure_docker(self, vm_name: str) -> None:
        deadline = time.monotonic() + self.wait_timeout_seconds

        while time.monotonic() < deadline:
            result = self.host_ssh(
                vm_name,
                'docker',
                'info',
                '--format',
                '{{.ServerVersion}}',
                capture=True,
                check=False,
            )
            if result.returncode == 0:
                return
            time.sleep(self.wait_interval_seconds)

        raise click.ClickException(f'Timed out waiting for Docker availability on {vm_name!r}.')

    def docker_driver_status(self, vm_name: str, *, check: bool):
        return self.host_ssh(
            vm_name,
            'docker',
            'info',
            '--format',
            '{{.DriverStatus}}',
            capture=True,
            check=check,
        )

    def containerd_image_store_enabled(self, vm_name: str) -> bool:
        result = self.docker_driver_status(vm_name, check=False)
        return result.returncode == 0 and CONTAINERD_SNAPSHOTTER_STATUS in result.stdout

    def daemon_config(self, vm_name: str) -> dict:
        command = ('sudo', 'cat', '/etc/docker/daemon.json')
        result = self.host_ssh(vm_name, *command, capture=True, check=False)
        if result.returncode == 0:
            return json.loads(result.stdout)
        if 'No such file or directory' in result.stderr:
            return {}
        raise click.ClickException(self.host_ssh_failure_message(vm_name, command, result))

    def desired_daemon_config(self, current_config: dict) -> dict:
        features = current_config.get('features') or {}
        return current_config | {
            'features': features | {'containerd-snapshotter': True},
        }

    def containerd_image_store_daemon_config(self, current_config: dict) -> str:
        return (
            json.dumps(
                self.desired_daemon_config(current_config),
                indent=2,
                sort_keys=True,
            )
            + '\n'
        )

    def ensure_containerd_image_store(self, vm_name: str) -> bool:
        if self.containerd_image_store_enabled(vm_name):
            return False

        current_config = self.daemon_config(vm_name)
        desired_config = self.desired_daemon_config(current_config)
        if current_config == desired_config:
            return False

        self.host_ssh(vm_name, 'sudo', 'mkdir', '-p', '/etc/docker')
        self.host_ssh(
            vm_name,
            'sudo',
            'tee',
            '/etc/docker/daemon.json',
            capture=True,
            input=self.containerd_image_store_daemon_config(current_config),
        )
        self.host_ssh(vm_name, 'sudo', 'systemctl', 'restart', 'docker', capture=True)
        return True

    def verify_containerd_image_store(self, vm_name: str) -> None:
        command = ('docker', 'info', '--format', '{{.DriverStatus}}')
        result = self.host_ssh(vm_name, *command, capture=True, check=False)
        if result.returncode != 0:
            raise click.ClickException(self.host_ssh_failure_message(vm_name, command, result))
        if CONTAINERD_SNAPSHOTTER_STATUS not in result.stdout:
            driver_status = result.stdout.strip() or '<empty>'
            raise click.ClickException(
                f'Docker on {vm_name!r} is not using the containerd image store.\n'
                f'DriverStatus: {driver_status}',
            )

    def make_public(self, vm_name: str) -> None:
        ssh('exe.dev', 'share', 'set-public', vm_name, capture=True, opts=self.opts)

    def destroy_vm(self, vm_name: str) -> bool:
        if vm_name not in self.list_vms():
            return False

        ssh('exe.dev', 'rm', vm_name, capture=True, opts=self.opts)
        return True


@dataclass
class Provision:
    config_opts: ConfigOpts
    exe_dev: ExeDev | None = None

    def __post_init__(self) -> None:
        if self.exe_dev is None:
            self.exe_dev = ExeDev(opts=self.config_opts.opts)

    @property
    def config(self) -> LexeConfig:
        return self.config_opts.config

    @property
    def app_name(self) -> str:
        return self.config.project.name

    @property
    def vm_host_name(self) -> str:
        return self.config.project.vm_host

    def run(self) -> None:
        click.echo(f'Loaded lexe config for {self.app_name} ({self.vm_host_name}).')

        created = self.exe_dev.ensure_vm(self.vm_host_name)
        if created:
            click.echo(f'Created exe.dev VM: {self.vm_host_name}')
        else:
            click.echo(f'Using existing exe.dev VM: {self.vm_host_name}')

        click.echo('Waiting for SSH reachability...')
        self.exe_dev.wait_for_ssh(self.vm_host_name)

        click.echo('Ensuring Docker uses the containerd image store...')
        changed = self.exe_dev.ensure_containerd_image_store(self.vm_host_name)
        if changed:
            click.echo('Enabled Docker containerd image store.')
        else:
            click.echo('Docker containerd image store already enabled.')

        click.echo('Verifying Docker availability...')
        self.exe_dev.ensure_docker(self.vm_host_name)

        click.echo('Verifying Docker containerd image store...')
        self.exe_dev.verify_containerd_image_store(self.vm_host_name)

        if self.config.public:
            click.echo('Enabling public HTTP proxy.')
            self.exe_dev.make_public(self.vm_host_name)

        click.echo('Provision complete.')


@dataclass
class Destroy:
    config_opts: ConfigOpts
    exe_dev: ExeDev | None = None

    def __post_init__(self) -> None:
        if self.exe_dev is None:
            self.exe_dev = ExeDev(opts=self.config_opts.opts)

    @property
    def config(self) -> LexeConfig:
        return self.config_opts.config

    @property
    def app_name(self) -> str:
        return self.config.project.name

    @property
    def vm_host_name(self) -> str:
        return self.config.project.vm_host

    def run(self) -> None:
        click.echo(f'Loaded lexe config for {self.app_name} ({self.vm_host_name}).')

        destroyed = self.exe_dev.destroy_vm(self.vm_host_name)
        if destroyed:
            click.echo(f'Destroyed exe.dev VM: {self.vm_host_name}')
        else:
            click.echo(f'No exe.dev VM found: {self.vm_host_name}')

        click.echo('Destroy complete.')
