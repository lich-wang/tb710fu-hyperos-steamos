#!/usr/bin/env python3
"""Closed-loop calibrated LUT display profile for the Xiaomi AirPlay receiver.

With a LUT (A2B0/B2A0) display profile the Mac's AirPlay stream follows the profile's
B2A, but with an extra transform that is not predictable, so the profile is calibrated
iteratively from measured grey ramps (content sRGB value -> value shown on the tablet).

  B2A: XYZ -> linear sRGB -> s = sRGB_enc -> s' = c(s) (per channel) -> d = sRGB_dec(s')^(1/1.961)
  A2B: inverse.  Matrix/TRC tags = the macOS default "HD 709-A" (BT.709 primaries, gamma 1.961).

usage: make_icc_iter.py <corr_in.json|-> <ramp.txt measured with corr_in | -> <corr_out.json> <out.icc> [A.json]
corr = list of (s, c(s)) points, s and c in 0..1; '-' = identity.  ramp '-' = use corr_in unchanged.
A.json = optional 3x3 gamma-domain colour mixing measured on the tablet (tablet ~= A * content);
         its inverse is applied before c to undo the receiver's YUV matrix error.
"""
import json, struct, sys

def interp(pts, x):
    if x <= pts[0][0]: return pts[0][1]
    for (x0,y0),(x1,y1) in zip(pts, pts[1:]):
        if x <= x1: return y0 + (y1-y0)*(x-x0)/(x1-x0) if x1 > x0 else y1
    return pts[-1][1]
def mono(pts, eps=0.0015):
    out=[]; last=-1
    for x,y in pts: y=max(y,last+eps); out.append((x,y)); last=y
    return out

corr = [(0,0),(1,1)] if sys.argv[1] == '-' else [tuple(p) for p in json.load(open(sys.argv[1]))]
meas = []
for line in ([] if sys.argv[2] == '-' else open(sys.argv[2])):
    if line.startswith('grey'):
        p = line.replace('(', ' ').replace(')', ' ').replace(',', ' ').split()
        meas.append((int(p[1])/255, sum(int(x) for x in p[5:8])/3/255))
t = mono(meas) if meas else [(0,0),(1,1)]       # s -> tablet, with current corr
tinv = [(y, x) for x, y in t]                    # tablet -> s
grid = [i/255 for i in range(256)]
# want tablet(s) = s: new c(s) = c_old(t^-1(s)); damp a little to avoid overshoot
newc = [(s, interp(corr, interp(tinv, s))) for s in grid]
newc = mono(newc, 1e-4); newc[0] = (0.0, max(0.0, newc[0][1])); 
newc = [(s, min(1.0, c)) for s, c in newc]
json.dump(newc, open(sys.argv[3], 'w'))

M = [[0.4360504150390625, 0.385101318359375, 0.143035888671875],
     [0.2231903076171875, 0.71771240234375, 0.0594940185546875],
     [0.01385498046875,   0.096832275390625, 0.714080810546875]]
def inv3(m):
    a,b,c=m[0];d,e,f=m[1];g,h,i=m[2]
    det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
    return [[(e*i-f*h)/det,(c*h-b*i)/det,(b*f-c*e)/det],[(f*g-d*i)/det,(a*i-c*g)/det,(c*d-a*f)/det],[(d*h-e*g)/det,(b*g-a*h)/det,(a*e-b*d)/det]]
MI = inv3(M)
AI = inv3(json.load(open(sys.argv[5]))) if len(sys.argv) > 5 else [[1,0,0],[0,1,0],[0,0,1]]
A_ = inv3(AI)
mul = lambda m,v: [sum(m[r][k]*v[k] for k in range(3)) for r in range(3)]
clip = lambda x: 0.0 if x < 0 else 1.0 if x > 1 else x
def srgb_enc(L): return 12.92*L if L <= 0.0031308 else 1.055*L**(1/2.4) - 0.055
def srgb_dec(V): return V/12.92 if V <= 0.04045 else ((V+0.055)/1.055)**2.4
cinv = [(y, x) for x, y in newc]

def u16(x): return max(0, min(65535, int(round(x))))
def s15(x): return struct.pack('>i', int(round(x*65536)))
def pad4(b): return b + b'\0'*(-len(b) % 4)
def lut16(grid, intab, nodefn, nin=4096):
    h = b'mft2' + b'\0'*4 + bytes([3, 3, grid, 0]) + b''.join(s15(v) for v in (1,0,0,0,1,0,0,0,1))
    h += struct.pack('>HH', nin, 2)
    h += b''.join(struct.pack('>H', u16(intab(i/(nin-1))*65535)) for _ in range(3) for i in range(nin))
    cl = bytearray()
    for i in range(grid):
        for j in range(grid):
            for k in range(grid):
                for v in nodefn(i/(grid-1), j/(grid-1), k/(grid-1)): cl += struct.pack('>H', u16(v*65535))
    return h + bytes(cl) + struct.pack('>HH', 0, 65535)*3
XYZMAX = 1 + 32767/32768
def a2b(r,g,b):
    s2=[interp(cinv, srgb_enc(x**1.961)) for x in (r,g,b)]
    L=[srgb_dec(clip(x)) for x in mul(A_, s2)]
    return [x/XYZMAX for x in mul(M, L)]
B2A_IN = lambda e: clip(e*XYZMAX) ** (1/2.4)
def b2a(p,q,s):
    L=[clip(x) for x in mul(MI, [p**2.4, q**2.4, s**2.4])]
    s2=[clip(x) for x in mul(AI, [srgb_enc(x) for x in L])]
    return [srgb_dec(interp(newc, x))**(1/1.961) for x in s2]
def text(t): return b'text' + b'\0'*4 + t.encode() + b'\0'
def desc(t):
    a=t.encode()+b'\0'
    return b'desc'+b'\0'*4+struct.pack('>I',len(a))+a+b'\0'*8+b'\0'*3+b'\0'*67
def xyz(v): return b'XYZ '+b'\0'*4+b''.join(s15(x) for x in v)
def curv_gamma(g): return b'curv'+b'\0'*4+struct.pack('>IH',1,int(round(g*256)))
tags = [(b'desc', desc('Xiaomi Pad AirPlay (calibrated)')), (b'cprt', text('No copyright, tb710fu project')),
        (b'wtpt', xyz([0.9642, 1.0, 0.8249])),
        (b'rXYZ', xyz([M[0][0],M[1][0],M[2][0]])), (b'gXYZ', xyz([M[0][1],M[1][1],M[2][1]])), (b'bXYZ', xyz([M[0][2],M[1][2],M[2][2]])),
        (b'rTRC', curv_gamma(1.961)), (b'gTRC', curv_gamma(1.961)), (b'bTRC', curv_gamma(1.961)),
        (b'A2B0', lut16(33, lambda x:x, a2b)), (b'B2A0', lut16(33, B2A_IN, b2a))]
body=b''; table=[]; off=128+4+12*len(tags)
for sig,data in tags:
    data=pad4(data); table.append((sig,off,len(data))); body+=data; off+=len(data)
hdr = struct.pack('>I4sI4s4s4s', off, b'appl', 0x02400000, b'mntr', b'RGB ', b'XYZ ')
hdr += struct.pack('>6H', 2026,10,12,0,0,0) + b'acsp' + b'APPL' + b'\0'*12 + b'\0'*8
hdr += b'\0'*4 + s15(0.9642)+s15(1.0)+s15(0.8249) + b'\0'*48
open(sys.argv[4],'wb').write(hdr + struct.pack('>I',len(tags)) + b''.join(struct.pack('>4sII',*t) for t in table) + body)
if meas: print('max |tablet-s| in input ramp: %.1f' % (255*max(abs(y-x) for x,y in meas[2:30])))
print('c:', ' '.join('%d->%.0f' % (round(s*255), c*255) for s, c in newc[::32]))
