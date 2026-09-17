"""Reproduce native persistence disassembly from hash-verified G3 sources."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'g3-usb-descriptor'))
from inspect_usb import Elf


def main():
    selections = {
        'PExtBackup.so': ['xs_backup_flush'],
        'libAppBackupApi.so': ['Bkup_flush_async',
            '_ZN12BackupWorker9postEventEP11BackupEvent',
            '_ZN12BackupWorker13handleMessageEPv'],
        'libBackupCore.so': ['_ZN19BackupMessageThread11postMessageEPvj',
            '_ZN12CommonMethod5flushEj', '_ZN11BasicMethod5flushEjjj',
            '_Z11backupWriteiPKvj'],
    }
    result = []
    for library, symbols in selections.items():
        folder = 'fskrel1/dsc/fsk/' if library.startswith('PExt') else 'lib/lib/'
        relative = 'evidence/extracted_g3/archives_unpacked/' + folder + library
        elf = Elf(relative)
        result.append(relative)
        result.extend(elf.decode(symbol) for symbol in symbols)
    (HERE / 'native-trace.txt').write_text('\n\n'.join(result) + '\n', encoding='utf-8')
    print('Verified pinned inputs and reproduced native-trace.txt')


if __name__ == '__main__':
    main()
