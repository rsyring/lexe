from pathlib import Path

import click

from lexe.config import LexeConfig
from lexe.provision import Destroy, Provision


@click.group()
def main() -> None:
    pass


@main.command()
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
)
def provision(config_fpath: Path) -> None:
    config = LexeConfig.find_lexe(config_fpath)
    Provision(config=config).run()


@main.command()
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
)
def destroy(config_fpath: Path) -> None:
    config = LexeConfig.find_lexe(config_fpath)
    Destroy(config=config).run()
