"""Assemble the offline app into a single distributable HTML file."""
from pathlib import Path

root = Path(__file__).resolve().parent
source = root / 'mask-batch'
html = (source / 'template.html').read_text(encoding='utf-8')
scripts = [('PAKO','pako-lib','vendor/pako.min.js'),('UPNG','upng-lib','vendor/upng.js'),
           ('JSZIP','zip-lib','vendor/jszip.min.js'),('LUCIDE','icons-lib','vendor/lucide.min.js'),
           ('CORE','mask-core','core.js'),('APP','mask-app','app.js')]
for token, tag, filename in scripts:
    code=(source / filename).read_text(encoding='utf-8').replace('</script', '<\\/script')
    html=html.replace('<!--'+token+'-->','<script id="'+tag+'">\n'+code+'\n</script>')
target=root.parent/'pbr-mask-batch.html'
licenses='\n\n'.join(p.name+'\n'+p.read_text(encoding='utf-8') for p in sorted((source/'vendor').glob('*LICENSE*')))
html=html.replace('</body>', '<script type="text/plain" id="third-party-licenses">\n'+licenses.replace('</script','<\\/script')+'\n</script>\n</body>')
target.write_text(html,encoding='utf-8')
print(str(target))
