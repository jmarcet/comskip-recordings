#!env python3.7

import asyncio
import os
from asyncio.subprocess import DEVNULL, PIPE
from glob import glob

COMSKIP_INI = os.environ['HOME'] + '/comskip.ini'
RECORDINGS  = '/storage/recordings'

COMSKIP     = '/usr/local/bin/comskip'
INOTIFYWAIT = '/usr/bin/inotifywait'
MKVMERGE    = '/usr/bin/mkvmerge'

async def run(*args, _bg=False):
    if _bg:
        p = await asyncio.create_subprocess_exec(*args, stdout=DEVNULL, stderr=DEVNULL)
    else:
        p = await asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=PIPE)
        return await p.wait()

async def main():
    proc = await asyncio.create_subprocess_exec(INOTIFYWAIT, '-m', '-r', '-e', 'close_write',
                                                '--format', '%w%f', RECORDINGS, stdout=PIPE)

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
            await run(COMSKIP, '--ini=%s' % COMSKIP_INI, recording, _bg=True)
        elif recording.endswith('.mkvtoolnix.chapters'):
            chapters  = recording
            merged    = filename + '.mpeg-merged'
            recording = filename + '.mpeg'
            print('(2/3) Chapters FILENAME="%s" generated' % chapters)
            if os.path.getsize(chapters) == 132:
                print('    No commercials found, skipping...')
                [ os.remove(x) for x in glob(filename + '.*') if not x.endswith('.txt') and not x.endswith('.mpeg') ]
                continue
            print('    mkvmerge -o "%s" --chapters "%s" "%s"' % (merged, chapters, recording))
            await run(MKVMERGE, '-o', merged, '--chapters', chapters, recording, _bg=True)
        elif recording.endswith('.mpeg-merged'):
            chapters  = filename + '.mkvtoolnix.chapters'
            merged    = recording
            recording = filename + '.mpeg'
            print('(3/3) Commercial cutpoints FILENAME="%s" merged succesfully' % merged)
            print('    mv "%s" "%s"' % (merged, recording))
            try:
                os.rename(merged, recording)
            except:
                print('      -> FAILED: could not move "%s" to "%s"' % (merged, recording))
            [ os.remove(x) for x in glob(filename + '.*') if not x.endswith('.txt') and not x.endswith('.mpeg') ]

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print('Good bye!')
