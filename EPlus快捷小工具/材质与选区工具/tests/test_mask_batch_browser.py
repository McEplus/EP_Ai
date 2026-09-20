"""End-to-end file:// tool tests using installed Chrome and local Playwright."""
import io
import json
import sys
import zipfile
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.cache/pbr-tool-deps'),str(ROOT/'tools')]
from playwright.sync_api import sync_playwright
from pbr_mask_core import build, region, COLORS


def main():
    out=ROOT/'.cache/mask-tool'
    out.mkdir(parents=True,exist_ok=True)
    report=json.loads((ROOT/'docs/pbr-mask-audit/rollout.json').read_text(encoding='utf-8'))
    basp=next(r for r in report if Path(r['mask']).name=='basp_tf_color_mask.png')
    base=Path(basp['base'])
    # Region identity and alpha suffice to reconstruct a pure-color test input.
    original=Image.open(basp['mask']).convert('RGBA')
    pure=[]
    for rgba in original.getdata():
        r=region(rgba[:3])
        pure.append(tuple(255*c for c in COLORS[r])+(rgba[3],) if r>=0 else rgba)
    original.putdata(pure)
    mask=out/'basp_tf_color_mask.png'
    original.save(mask)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
        page.goto((ROOT/'pbr-mask-batch.html').as_uri())
        page.locator('#fileInput').set_input_files([str(mask)])
        page.wait_for_function("document.querySelector('#abnormal').textContent==='1'")
        assert page.locator('#run').is_disabled()
        page.locator('#fileInput').set_input_files([str(base)])
        page.wait_for_function("document.querySelector('#ready').textContent==='1'")
        page.locator('#run').click()
        page.wait_for_function("document.querySelector('#completed').textContent==='1' || document.querySelector('#abnormal').textContent==='1'",timeout=60000)
        assert page.locator('#completed').inner_text()=='1', page.evaluate('rows.map(r=>({status:r.status,error:r.error}))')
        page.wait_for_function("document.querySelector('#resultCanvas').width>1")
        page.wait_for_function('!busy')
        page.screenshot(path=str(out/'desktop.png'),full_page=True)
        with page.expect_download() as download:
            page.locator('#download').click()
        image_path=out/'browser_mask.png';download.value.save_as(image_path)
        actual=Image.open(image_path).convert('RGBA')
        expected=build(Image.open(base),Image.open(mask))[0]
        difference=max(abs(a-b) for a,b in zip(actual.tobytes(),expected.tobytes()))
        assert difference<=1, difference
        assert actual.getchannel('A').tobytes()==Image.open(mask).convert('RGBA').getchannel('A').tobytes()
        assert Image.open(image_path).info['EplusMaskVersion']=='detail-v1'
        with page.expect_download() as download:
            page.locator('#export').click()
        archive=out/'output.zip';download.value.save_as(archive)
        with zipfile.ZipFile(archive) as z:
            assert z.read('basp_tf_color_mask.png')==image_path.read_bytes()
            assert json.loads(z.read('_eplus_mask_report.json'))['algorithm']=='detail-v1'
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(out/'mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile horizontal overflow'
        # Re-import generated input: exact bytes are retained, no second bake.
        page.locator('#clear').click()
        page.locator('#fileInput').set_input_files([{'name':'basp_tf.png','mimeType':'image/png','buffer':base.read_bytes()},{'name':'basp_tf_color_mask.png','mimeType':'image/png','buffer':image_path.read_bytes()}])
        page.wait_for_function("document.querySelector('#ready').textContent==='1'")
        page.locator('#run').click()
        page.wait_for_function("document.querySelector('#rows').textContent.includes('已处理')")
        # Transparent RGB must survive decoder and encoder, not canvas conversion.
        source=Image.new('RGBA',(8,8),(100,100,100,255));source.save(out/'alpha.png')
        authored=Image.new('RGBA',(8,8),(255,0,0,0));authored.save(out/'alpha_color_mask.png')
        page.locator('#clear').click()
        page.locator('#fileInput').set_input_files([str(out/'alpha.png'),str(out/'alpha_color_mask.png')])
        page.wait_for_function("document.querySelector('#ready').textContent==='1'")
        page.locator('#run').click()
        page.wait_for_function("document.querySelector('#completed').textContent==='1'")
        with page.expect_download() as download:page.locator('#download').click()
        download.value.save_as(out/'alpha_result.png')
        assert Image.open(out/'alpha_result.png').getpixel((0,0))==(230,0,0,0)
        # Directory pairing retains separate relative paths and rejects flattened collisions.
        folder=out/'nested'
        for name in ('A','B'):
            (folder/name).mkdir(parents=True,exist_ok=True)
            source.save(folder/name/'part.png');authored.save(folder/name/'part_color_mask.png')
        page.locator('#clear').click()
        page.locator('#folderInput').set_input_files(str(folder))
        page.wait_for_function("document.querySelector('#ready').textContent==='2'")
        page.locator('#run').click()
        page.wait_for_function("document.querySelector('#completed').textContent==='2' && !busy")
        page.locator('#keepPaths').uncheck();page.locator('#export').click()
        page.wait_for_function("document.querySelector('#message').textContent.includes('同名')")
        page.locator('#keepPaths').check()
        with page.expect_download() as download:page.locator('#export').click()
        download.value.save_as(out/'nested.zip')
        with zipfile.ZipFile(out/'nested.zip') as z:
            assert len([n for n in z.namelist() if n.endswith('part_color_mask.png')])==2
        # Drop path: files supplied by a DataTransfer enter the same queue.
        page.locator('#clear').click()
        page.evaluate('''payload=>{const dt=new DataTransfer();for(const file of payload)dt.items.add(new File([new Uint8Array(file.data)],file.name,{type:'image/png'}));window.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));}''',
                      [{'name':'alpha.png','data':list((out/'alpha.png').read_bytes())},{'name':'alpha_color_mask.png','data':list((out/'alpha_color_mask.png').read_bytes())}])
        page.wait_for_function("document.querySelector('#ready').textContent==='1'")
        page.evaluate("document.querySelector('#run').click();document.querySelector('#cancel').click()")
        page.wait_for_function('!busy && worker===null')
        assert page.locator('#ready').inner_text()=='1'
        # Invalid PNG is contained as a row error.
        page.locator('#fileInput').set_input_files([{'name':'bad.png','mimeType':'image/png','buffer':b'bad'}, {'name':'bad_color_mask.png','mimeType':'image/png','buffer':b'bad'}])
        page.wait_for_function("document.querySelector('#abnormal').textContent==='1'")
        assert not errors, errors
        browser.close()
    print('Browser file pairing, PNG/Python parity, hidden RGB, ZIP, duplicate-bake guard, invalid input and desktop/mobile layout passed. Pixel difference=%d' % difference)


if __name__=='__main__':main()
