"""Compile and exercise the shared GLSL helper in a hidden Windows GL context.

This does not replace the game's shader compiler or mobile GLES verification.
"""
import ctypes as c
import json
import sys
from ctypes import wintypes as w
from pathlib import Path
from tool_paths import MOD_ROOT, TOOL_ROOT


class PFD(c.Structure):
    _fields_ = [('size', w.WORD), ('version', w.WORD), ('flags', w.DWORD),
                ('type', c.c_ubyte), ('color', c.c_ubyte),
                ('channels', c.c_ubyte * 8), ('accum', c.c_ubyte * 5),
                ('depth', c.c_ubyte), ('stencil', c.c_ubyte), ('aux', c.c_ubyte),
                ('layer', c.c_ubyte), ('reserved', c.c_ubyte),
                ('layerMask', w.DWORD), ('visibleMask', w.DWORD), ('damageMask', w.DWORD)]


def main():
    user, gdi, gl = c.WinDLL('user32'), c.WinDLL('gdi32'), c.WinDLL('opengl32')
    user.CreateWindowExW.restype = w.HWND
    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                    c.c_int, c.c_int, c.c_int, c.c_int,
                                    w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
    user.GetDC.argtypes, user.GetDC.restype = [w.HWND], w.HDC
    user.ReleaseDC.argtypes = [w.HWND, w.HDC]
    user.DestroyWindow.argtypes = [w.HWND]
    gdi.ChoosePixelFormat.argtypes = [w.HDC, c.POINTER(PFD)]
    gdi.SetPixelFormat.argtypes = [w.HDC, c.c_int, c.POINTER(PFD)]
    gl.wglCreateContext.argtypes, gl.wglCreateContext.restype = [w.HDC], c.c_void_p
    gl.wglMakeCurrent.argtypes = [w.HDC, c.c_void_p]
    gl.wglDeleteContext.argtypes = [c.c_void_p]
    gl.wglGetProcAddress.argtypes, gl.wglGetProcAddress.restype = [c.c_char_p], c.c_void_p
    window = user.CreateWindowExW(0, 'STATIC', 'PBR shader check', 0, 0, 0, 4, 4, None, None, None, None)
    assert window, 'Hidden window creation failed'
    dc, context = user.GetDC(window), None
    try:
        pfd = PFD()
        pfd.size, pfd.version, pfd.flags, pfd.color = c.sizeof(PFD), 1, 0x24, 32
        pixel_format = gdi.ChoosePixelFormat(dc, c.byref(pfd))
        assert pixel_format and gdi.SetPixelFormat(dc, pixel_format, c.byref(pfd))
        context = gl.wglCreateContext(dc)
        assert context and gl.wglMakeCurrent(dc, context)

        def fn(name, restype, *args):
            address = gl.wglGetProcAddress(name.encode('ascii'))
            assert address, name
            return c.WINFUNCTYPE(restype, *args)(address)

        create_shader = fn('glCreateShader', c.c_uint, c.c_uint)
        source = fn('glShaderSource', None, c.c_uint, c.c_int, c.POINTER(c.c_char_p), c.c_void_p)
        compile_shader = fn('glCompileShader', None, c.c_uint)
        shader_status = fn('glGetShaderiv', None, c.c_uint, c.c_uint, c.POINTER(c.c_int))
        shader_log = fn('glGetShaderInfoLog', None, c.c_uint, c.c_int, c.c_void_p, c.c_char_p)

        def shader(kind, text):
            handle = create_shader(kind)
            data = c.c_char_p(text.encode('utf-8'))
            source(handle, 1, c.byref(data), None)
            compile_shader(handle)
            ok = c.c_int()
            shader_status(handle, 0x8B81, c.byref(ok))
            log = c.create_string_buffer(8192)
            shader_log(handle, len(log), None, log)
            assert ok.value, log.value.decode('utf-8', 'replace')
            return handle

        root = Path(MOD_ROOT)
        reports = Path(TOOL_ROOT) / 'docs/pbr-mask-audit'
        helper = (root / 'resource_pack_EP_JXK_0/shaders/glsl/eplusMaskMaterial.h').read_text(encoding='utf-8')
        mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ('fast', 'balance') else 'default'
        header, preset = {'default': ('eplusPBR.h', 'pbrPresetEnvSurface'),
                          'fast': ('eplusPBRFast.h', 'pbrPresetFastEnvSurface'),
                          'balance': ('eplusPBRBalance.h', 'pbrPreset')}[mode]
        pbr = (root / 'resource_pack_EP_JXK_0/shaders/glsl' / header).read_text(encoding='utf-8')
        # Engine-only includes are replaced by the explicit fog stub for this harness.
        pbr = '\n'.join(line for line in pbr.splitlines() if not line.lstrip().startswith('#include')) + '\n'
        surface = (root/'resource_pack_EP_JXK_0/shaders/glsl/eplusSurfaceLighting.h').read_text(encoding='utf-8')
        prelude = 'void applyFog(inout vec4 color,vec4 fog){color.rgb=mix(color.rgb,fog.rgb,fog.a);}\n' + surface
        fragment = '#version 120\n' + prelude + pbr + helper + '''
uniform vec3 testSource;
uniform vec4 testMask;
uniform float testOutput;
uniform vec3 testNormal;
uniform vec3 testLight;
uniform vec3 testShaded;
uniform vec4 testFog;
uniform float testCorrection;
uniform sampler2D testEnv;
void main() {
    vec3 albedo; vec2 mr; float tintWeight;
    epMaskMaterial(testSource, testMask, albedo, mr, tintWeight);
    if (testOutput > 2.5) {
        gl_FragColor=vec4(epMaskPaintExposure(testShaded,albedo,testLight),1.0);
        return;
    }
    if (testOutput > 1.5) {
        vec4 fog=testFog;
        if(testCorrection>0.5 && tintWeight>0.5) fog.a=0.0;
        vec4 color=PRESET(vec4(0,0,0,1),vec4(testNormal,0),normalize(vec3(.3,.8,.5)),
                         vec3(0,0,3),vec4(testLight,1),vec4(albedo,1),fog,mr.x,mr.yENVARG);
        if(testCorrection>0.5 && tintWeight>0.5) {
#ifdef TEST_BALANCE
            color.rgb=epMaskPaintExposure(color.rgb,albedo,testLight);
#endif
            applyFog(color,testFog);
        }
        gl_FragColor=color;return;
    }
    gl_FragColor = testOutput > 0.5 ? vec4(mr, 0.0, 1.0) : vec4(albedo, 1.0);
}
'''
        fragment=fragment.replace('PRESET',preset).replace('ENVARG',',testEnv,tintWeight*testCorrection' if mode!='balance' else '')
        if mode=='balance':fragment=fragment.replace('#version 120','#version 120\n#define TEST_BALANCE')
        frag = shader(0x8B30, fragment)
        vert = shader(0x8B31, '#version 120\nvoid main() { gl_Position = gl_Vertex; }')
        program = fn('glCreateProgram', c.c_uint)()
        attach = fn('glAttachShader', None, c.c_uint, c.c_uint)
        attach(program, frag)
        attach(program, vert)
        fn('glLinkProgram', None, c.c_uint)(program)
        linked = c.c_int()
        fn('glGetProgramiv', None, c.c_uint, c.c_uint, c.POINTER(c.c_int))(program, 0x8B82, c.byref(linked))
        assert linked.value, 'GL link failed'
        fn('glUseProgram', None, c.c_uint)(program)
        location = fn('glGetUniformLocation', c.c_int, c.c_uint, c.c_char_p)
        setters = {n: fn('glUniform%df' % n, None, c.c_int, *([c.c_float] * n)) for n in (1, 3, 4)}

        def uniform(name, *values):
            setters[len(values)](location(program, name.encode('ascii')), *values)

        gl.glVertex2f.argtypes = [c.c_float, c.c_float]
        framebuffer, renderbuffer = c.c_uint(), c.c_uint()
        fn('glGenFramebuffers', None, c.c_int, c.POINTER(c.c_uint))(1, c.byref(framebuffer))
        fn('glBindFramebuffer', None, c.c_uint, c.c_uint)(0x8D40, framebuffer.value)
        fn('glGenRenderbuffers', None, c.c_int, c.POINTER(c.c_uint))(1, c.byref(renderbuffer))
        fn('glBindRenderbuffer', None, c.c_uint, c.c_uint)(0x8D41, renderbuffer.value)
        fn('glRenderbufferStorage', None, c.c_uint, c.c_uint, c.c_int, c.c_int)(0x8D41, 0x8058, 1, 1)
        fn('glFramebufferRenderbuffer', None, c.c_uint, c.c_uint, c.c_uint, c.c_uint)(0x8D40, 0x8CE0, 0x8D41, renderbuffer.value)
        assert fn('glCheckFramebufferStatus', c.c_uint, c.c_uint)(0x8D40) == 0x8CD5
        gl.glViewport(0, 0, 1, 1)

        def pixel():
            gl.glBegin(0x0007)
            for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                gl.glVertex2f(x, y)
            gl.glEnd()
            gl.glFinish()
            result = (c.c_ubyte * 4)()
            gl.glReadPixels(0, 0, 1, 1, 0x1908, 0x1401, result)
            return tuple(value / 255.0 for value in result)

        from PIL import Image
        from pbr_mask_core import region
        env = Image.open(root/'resource_pack_EP_JXK_0/textures/pbr/eplus_pbr_prefilter.png').convert('RGBA')
        env_bytes=(c.c_ubyte*(env.width*env.height*4)).from_buffer_copy(env.tobytes())
        texture=c.c_uint()
        gl.glGenTextures(1,c.byref(texture));gl.glBindTexture(0x0DE1,texture)
        gl.glTexParameteri(0x0DE1,0x2801,0x2601);gl.glTexParameteri(0x0DE1,0x2800,0x2601)
        gl.glTexParameteri(0x0DE1,0x2802,0x812F);gl.glTexParameteri(0x0DE1,0x2803,0x812F)
        gl.glTexImage2D.argtypes=[c.c_uint,c.c_int,c.c_int,c.c_int,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_void_p]
        gl.glTexImage2D(0x0DE1,0,0x8058,env.width,env.height,0,0x1908,0x1401,env_bytes)
        rollout = json.loads((reports / 'rollout.json').read_text(encoding='utf-8'))
        mask_path = next(row['mask'] for row in rollout if Path(row['mask']).name == 'basp_tf_color_mask.png')
        mask_image = Image.open(mask_path).convert('RGBA')
        samples = sorted(set(p for p in mask_image.getdata() if region(p[:3]) >= 0))
        uniform('testSource', 0.2, 0.3, 0.4)
        checked = 0
        for target in ((255, 255, 255), (141, 141, 141), (255, 0, 0)):
            encoded = target[0] + target[1]*256 + target[2]*65536
            uniform('EXTRA_ACTOR_UNIFORM1', encoded, encoded, encoded, encoded)
            uniform('EXTRA_ACTOR_UNIFORM2', encoded, 0, 31, 0)
            uniform('testOutput', 0)
            for rgba in samples:
                uniform('testMask', *(v/255 for v in rgba))
                result = pixel()
                for actual, channel in zip(result[:3], target):
                    assert abs(actual - channel/255 * max(rgba[:3])/255) < 0.009, 'Baked detail decode mismatch'
                checked += 1
        uniform('testOutput', 1)
        for rgba in samples:
            uniform('testMask', *(v/255 for v in rgba))
            assert abs(pixel()[0] - rgba[3]/255) < 0.009, 'Baked mask changed metallicity'
        uniform('testOutput', 0)
        uniform('EXTRA_ACTOR_UNIFORM2', 0, 0, 0, 0)
        for actual, original in zip(pixel()[:3], (0.2, 0.3, 0.4)):
            assert abs(actual-original) < 0.009, 'Default source color changed'
        print('Detail-mask GLSL compiled/linked; %d texture/color samples, alpha and untinted source passed.' % checked)

        uniform('EXTRA_ACTOR_UNIFORM1',16777215,16777215,16777215,16777215)
        uniform('EXTRA_ACTOR_UNIFORM2',16777215,0,31,0)
        uniform('testSource',.18,.18,.18)
        uniform('testOutput',2)
        uniform('testFog',.65,.75,.85,0)
        results=[]
        for normal in ((0,0,1),(0,1,0),(0,-1,0),(1,0,0)):
            uniform('testNormal',*normal)
            for detail in (.4,.9,.98):
                uniform('testMask',detail,0,0,.46)
                uniform('testLight',.7,.7,.7)
                uniform('testCorrection',0);before=pixel()[:3]
                uniform('testCorrection',1);after=pixel()[:3]
                assert all(a+0.009>=b for a,b in zip(after,before)), 'Paint correction darkened surface'
                results.append(dict(normal=normal,detail=detail,before=before,after=after))
        front=[r for r in results if r['normal']==(0,0,1)]
        assert sum(front[1]['after'])-sum(front[1]['before'])>.1, 'No meaningful daylight lift'
        assert sum(front[2]['after'])>sum(front[0]['after'])+.4, 'Texture contrast lost'
        if mode!='balance':
            bodies={tuple(r['normal']):r for r in results if r['detail']==.9}
            top=sum(bodies[(0,1,0)]['after'])/3
            bottom=sum(bodies[(0,-1,0)]['after'])/3
            side=sum(bodies[(1,0,0)]['after'])/3
            assert top>.80 and top-bottom>.30, 'Painted top/bottom form contrast lost'
            assert top-side>.08, 'Painted side is too flat'
            assert sum(bodies[(0,1,0)]['before'])-sum(bodies[(0,-1,0)]['before'])>.3, 'Unpainted form contrast lost'
            uniform('testNormal',0,0,1)
            uniform('testMask',.9,0,0,.46)
            uniform('EXTRA_ACTOR_UNIFORM1',9276813,9276813,9276813,9276813)
            uniform('EXTRA_ACTOR_UNIFORM2',9276813,0,31,0)
            uniform('EXTRA_ACTOR_UNIFORM4',1087,1087,1087,1087)
            responses=[]
            for level in (32,224):
                flat=(c.c_ubyte*4)(level,level,level,255)
                gl.glTexImage2D(0x0DE1,0,0x8058,1,1,0,0x1908,0x1401,flat)
                uniform('testCorrection',0);raw=pixel()[:3]
                uniform('testCorrection',1);painted=pixel()[:3]
                responses.append((sum(raw)/3,sum(painted)/3))
            raw_delta=responses[1][0]-responses[0][0]
            paint_delta=responses[1][1]-responses[0][1]
            assert paint_delta>.02 and paint_delta>=raw_delta*.65, 'Paint compressed environment reflection'
            print('Form top/side/bottom=%.3f/%.3f/%.3f; environment response raw/paint=%.3f/%.3f' % (top,side,bottom,raw_delta,paint_delta))
            scans={}
            for axis in ('metal','rough'):
                scan=[]
                for value in (1,25,50,75,90,100):
                    metal,rough=(value,25) if axis=='metal' else (100,value)
                    encoded=int(round(metal*63/100.0))+64*int(round(rough*63/100.0))
                    uniform('EXTRA_ACTOR_UNIFORM4',encoded,encoded,encoded,encoded)
                    reflect=[]
                    for level in (32,224):
                        flat=(c.c_ubyte*4)(level,level,level,255)
                        gl.glTexImage2D(0x0DE1,0,0x8058,1,1,0,0x1908,0x1401,flat)
                        uniform('testCorrection',0);raw=sum(pixel()[:3])/3
                        uniform('testCorrection',1);painted=sum(pixel()[:3])/3
                        reflect.append((raw,painted))
                    raw_change=reflect[1][0]-reflect[0][0]
                    paint_change=reflect[1][1]-reflect[0][1]
                    assert paint_change>=raw_change*.65-.005, 'Material control lost after recoloring'
                    scan.append(dict(value=value,raw_reflection=raw_change,paint_reflection=paint_change))
                changes=[item['paint_reflection'] for item in scan]
                if axis=='metal':
                    assert changes[-1]>changes[3]+.01, 'Upper metal slider flattened'
                else:
                    assert changes[0]>changes[-1]+.03, 'Roughness response too weak'
                    assert changes[3]>changes[-1]+.005, 'Upper roughness slider flattened'
                scans[axis]=scan
            print('Metal/roughness scans passed at 1/25/50/75/90/100, including high-end response.')
            scan_path=reports/'paint-lighting'/('parameter-response-'+mode+'.json')
            scan_path.write_text(json.dumps(scans,indent=2),encoding='utf-8')
            gl.glTexImage2D(0x0DE1,0,0x8058,env.width,env.height,0,0x1908,0x1401,env_bytes)
            uniform('EXTRA_ACTOR_UNIFORM1',16777215,16777215,16777215,16777215)
            uniform('EXTRA_ACTOR_UNIFORM4',0,0,0,0)
        uniform('testLight',.05,.05,.05)
        uniform('testCorrection',0);dark_before=pixel()[:3]
        uniform('testCorrection',1);dark_after=pixel()[:3]
        assert all(abs(a-b)<.009 for a,b in zip(dark_before,dark_after)), 'Dark scene was lifted'
        uniform('testLight',.7,.7,.7)
        uniform('testFog',.1,.2,.3,1)
        assert all(abs(a-b)<.009 for a,b in zip(pixel()[:3],(.1,.2,.3))), 'Fog was exposed'
        uniform('testFog',.65,.75,.85,0)
        uniform('EXTRA_ACTOR_UNIFORM2',0,0,0,0)
        uniform('testCorrection',0);unchanged=pixel()
        uniform('testCorrection',1)
        assert pixel()==unchanged, 'Unpainted material changed'
        uniform('testOutput',3);uniform('testShaded',0,0,0)
        assert max(pixel()[:3])==0, 'Zero light became emissive'
        uniform('EXTRA_ACTOR_UNIFORM2',16777215,0,31,0)
        for detail in (.3,.6,.9):
            uniform('testMask',detail,0,0,.46)
            uniform('testShaded',detail*.2,detail*.2,detail*.2)
            assert abs(pixel()[0]-detail*.8)<.009, 'Lighting lift compressed baked detail'
        destination=reports/'paint-lighting'
        destination.mkdir(parents=True,exist_ok=True)
        (destination/(mode+'.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
        print('%s PBR lighting: daylight lift, detail separation, darkness, fog and unpainted regression passed.' % mode)

    finally:
        gl.wglMakeCurrent(None, None)
        if context:
            gl.wglDeleteContext(context)
        user.ReleaseDC(window, dc)
        user.DestroyWindow(window)


if __name__ == '__main__':
    main()
