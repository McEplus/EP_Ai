"""Build a portable bundle from an explicit allowlist; no profiles or test outputs."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
output = root / 'EPlus模型导入工具-便携版.zip'
files = [
    'index.html', 'styles.css', 'converter.js', 'project.js', 'preview.js',
    'app.js', '启动工具.cmd', 'README.md',
]
samples = sorted((root / '模型素材').glob('*.bbmodel'))
with ZipFile(output, 'w', ZIP_DEFLATED) as bundle:
    for name in files:
        bundle.write(root / name, f'EPlus模型导入工具/{name}')
    for source in samples:
        bundle.write(source, f'EPlus模型导入工具/模型素材/{source.name}')
with ZipFile(output) as bundle:
    assert bundle.testzip() is None
    assert len(bundle.namelist()) == len(files) + len(samples)
print(f'Portable bundle: {output.name} ({output.stat().st_size:,} bytes)')
