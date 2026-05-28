from dataclasses import dataclass

from lexe.config import ConfigOpts, LexeConfig
from lexe.provision import ExeDev


@dataclass
class Exec:
    config_opts: ConfigOpts
    command: tuple[str, ...]
    tty: bool = False
    exe_dev: ExeDev | None = None

    def __post_init__(self) -> None:
        if self.exe_dev is None:
            self.exe_dev = ExeDev(opts=self.config_opts.opts)

    @property
    def config(self) -> LexeConfig:
        return self.config_opts.config

    @property
    def vm_host_name(self) -> str:
        return self.config.project.vm_host

    def run(self) -> None:
        assert self.command
        self.exe_dev.host_ssh(self.vm_host_name, *self.command, tty=self.tty)