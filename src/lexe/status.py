from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import click

from lexe.config import LexeConfig
from lexe.procs import docker_ssh_command, sub_run
from lexe.provision import ExeDev


@dataclass
class Status:
    config: LexeConfig
    app_dpath: Path
    exe_dev: ExeDev = field(default_factory=ExeDev)
    healthcheck_timeout_seconds: float = 3.0

    @property
    def remote_host(self) -> str:
        return f'{self.config.vm_host_name}.exe.xyz'

    def run(self) -> None:
        click.echo(f'App: {self.config.app_name}')
        click.echo(f'VM host: {self.config.vm_host_name}')

        vm_reachable = self.is_vm_reachable()
        click.echo(f'VM reachable: {self.yes_no(vm_reachable)}')

        compose_status = self.compose_status(vm_reachable)
        click.echo(f'Compose project running: {self.yes_no(compose_status is not None)}')
        if compose_status:
            click.echo('Compose status details:')
            click.echo(compose_status)

        latest_log_entry = self.latest_log_entry()
        if latest_log_entry:
            click.echo(f'Latest log entry: {latest_log_entry}')
        else:
            click.echo('Latest log entry: none')

        if self.config.healthcheck_url:
            click.echo(self.healthcheck_summary())
        else:
            click.echo('Healthcheck: not configured')

    def is_vm_reachable(self) -> bool:
        result = self.exe_dev.host_ssh(
            self.config.vm_host_name,
            'true',
            capture=True,
            check=False,
        )
        return result.returncode == 0

    def compose_status(self, vm_reachable: bool) -> str | None:
        if not vm_reachable:
            return None

        result = sub_run(
            'docker',
            'compose',
            '-f',
            'compose.yaml',
            '-f',
            'compose.server.yaml',
            'ps',
            capture=True,
            check=False,
            cwd=self.app_dpath,
            env=self.compose_env(),
        )
        output = result.stdout.strip()
        if result.returncode != 0 or not output or output.count('\n') < 1:
            return None
        return output

    def compose_env(self) -> dict[str, str]:
        env = {
            'COMPOSE_PROJECT_NAME': self.config.app_name,
            'DOCKER_HOST': f'ssh://{self.remote_host}',
        }
        if ssh_command := docker_ssh_command():
            env['DOCKER_SSH_COMMAND'] = ssh_command
        return env

    def latest_log_entry(self) -> str | None:
        logs_fpath = self.app_dpath / 'lexe-logs.md'
        if not logs_fpath.exists():
            return None

        lines = [line.strip() for line in logs_fpath.read_text().splitlines() if line.strip()]
        if not lines:
            return None
        return lines[-1]

    def healthcheck_summary(self) -> str:
        try:
            response = urlopen(self.config.healthcheck_url, timeout=self.healthcheck_timeout_seconds)
            status_code = response.getcode()
            if 200 <= status_code < 300:
                return f'Healthcheck: healthy ({status_code}) {self.config.healthcheck_url}'
            return f'Healthcheck: unhealthy ({status_code}) {self.config.healthcheck_url}'
        except HTTPError as exc:
            return f'Healthcheck: unhealthy ({exc.code}) {self.config.healthcheck_url}'
        except URLError as exc:
            return f'Healthcheck: error ({exc.reason}) {self.config.healthcheck_url}'

    def yes_no(self, value: bool) -> str:
        return 'yes' if value else 'no'