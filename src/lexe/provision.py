from dataclasses import dataclass

from lexe.config import LexeConfig


@dataclass
class Provision:
    config: LexeConfig

    def run(self) -> None:
        print(
            f'Loaded lexe config for {self.config.app_name} ({self.config.vm_host_name}).',
        )
