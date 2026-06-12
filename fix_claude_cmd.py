import sys
sys.stdout.reconfigure(encoding='utf-8')

OLD = 'CLAUDE_CMD = r"C:\\Users\\admin\\AppData\\Roaming\\npm\\claude.cmd"'
NEW = (
    'import shutil as _shutil\n'
    'CLAUDE_CMD = (_shutil.which("claude") or _shutil.which("claude.cmd")\n'
    '             or r"C:\\Users\\admin\\AppData\\Roaming\\npm\\claude.cmd")'
)

for fname in ['extract_tags_fire.py', 'extract_tags_police.py', 'compare_models.py', 'extract_tags.py']:
    txt = open(fname, encoding='utf-8').read()
    if OLD in txt:
        txt = txt.replace(OLD, NEW, 1)
        open(fname, 'w', encoding='utf-8').write(txt)
        print('고침:', fname)
    else:
        print('스킵(미매칭):', fname)
