#!env python3.7

import asyncio
import os
from asyncio.subprocess import DEVNULL, PIPE
from glob import glob

COMSKIP_INI = os.environ['HOME'] + '/comskip.ini'
RECORDINGS = '/storage/recordings'

COMSKIP = '/usr/local/bin/comskip'
INOTIFYWAIT = '/usr/bin/inotifywait'
MKVMERGE = '/usr/bin/mkvmerge'


def cleanup(filename, _check=True):
    [os.remove(x) for x in glob(filename + '.*') if not x.endswith('.txt') and not x.endswith('.mpeg')]
    if _check and (not os.path.exists(filename + '.txt') or not os.path.getsize(filename + '.txt')):
        if os.path.exists(filename + '.mpeg'):
            print('[WARNING]: something went wrong analyzing %s.mpeg, marking as already processed' % filename)
            with open(filename + '.txt', 'w') as f:
                f.write('[WARNING]: something went wrong analyzing this video\n')
        else:
            print('[WARNING]: something went wrong analyzing %s.mpeg' % filename)


async def run(*args, _filename=None):
    if not _filename:
        return await asyncio.create_subprocess_exec(*args, stdout=PIPE)
    p = await asyncio.create_subprocess_exec(*args, stdout=DEVNULL, stderr=DEVNULL)
    await p.wait()
    if p.returncode != 0:
        cleanup(_filename)


async def main():
    proc = await run(INOTIFYWAIT, '-m', '-r', '-e', 'close_write', '--format', '%w%f', RECORDINGS)

    while True:
        recording = (await proc.stdout.readline()).decode().rstrip()

        if not os.path.exists(recording) or not os.path.isfile(recording):
            continue
        if recording.endswith('.mpeg') or recording.endswith('.mpeg-merged'):
            filename = os.path.splitext(recording)[0]
        elif recording.endswith('.mkvtoolnix.chapters'):
            filename = recording.rpartition('.mkvtoolnix.chapters')[0]
        else:
            continue

        if recording.endswith('.mpeg'):
            print('(1/3) Recording FILENAME="%s" ended' % recording)
            print('    comskip --ini=%s "%s"' % (COMSKIP_INI, recording))
            asyncio.create_task(run(COMSKIP, '--ini=%s' % COMSKIP_INI, recording, _filename=filename))

        elif recording.endswith('.mkvtoolnix.chapters'):
            chapters = recording
            merged = filename + '.mpeg-merged'
            recording = filename + '.mpeg'
            print('(2/3) Chapters FILENAME="%s" generated' % chapters)
            if os.path.getsize(chapters) == 132:
                print('    No commercials found, skipping...')
                cleanup(filename, _check=False)
                continue
            print('    mkvmerge -o "%s" --chapters "%s" "%s"' % (merged, chapters, recording))
            asyncio.create_task(run(MKVMERGE, '-o', merged, '--chapters', chapters, recording, _filename=filename))

        elif recording.endswith('.mpeg-merged'):
            merged = recording
            recording = filename + '.mpeg'
            print('(3/3) Commercial cutpoints FILENAME="%s" merged succesfully' % merged)
            print('    mv "%s" "%s"' % (merged, recording))
            try:
                os.rename(merged, recording)
            except:
                print('      -> FAILED: could not move "%s" to "%s"' % (merged, recording))
            cleanup(filename)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print('Good bye!')
