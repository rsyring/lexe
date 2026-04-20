from datetime import datetime
from os import environ
from pathlib import Path


DATA_DPATH = Path('/home/pyapp/data')
EVENTS_LOG_FPATH = DATA_DPATH / 'events.log'


def main() -> None:
    hook_name = environ['LEXE_HOOK_NAME']
    DATA_DPATH.mkdir(parents=True, exist_ok=True)
    with EVENTS_LOG_FPATH.open('a', encoding='utf-8') as events_file:
        events_file.write(f'{datetime.now().isoformat()} {hook_name}\n')


if __name__ == '__main__':
    main()