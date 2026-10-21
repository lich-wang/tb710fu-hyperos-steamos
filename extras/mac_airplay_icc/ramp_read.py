import sys,zlib,struct
def load(p,ys):
    d=open(p,'rb').read(); i=8; idat=b''
    while i<len(d):
        l,t=struct.unpack('>I4s',d[i:i+8]); c=d[i+8:i+8+l]
        if t==b'IHDR': w,h,bd,ct=struct.unpack('>IIBB',c[:10])
        if t==b'IDAT': idat+=c
        i+=12+l
    bpp={2:3,6:4}[ct]; raw=zlib.decompress(idat); st=w*bpp; rows={}; prev=bytearray(st); p=0
    need={int(f*h) for f in ys}
    for y in range(h):
        f=raw[p]; line=bytearray(raw[p+1:p+1+st]); p+=1+st
        if f==1:
            for x in range(bpp,st): line[x]=(line[x]+line[x-bpp])&255
        elif f==2:
            for x in range(st): line[x]=(line[x]+prev[x])&255
        elif f==3:
            for x in range(st): line[x]=(line[x]+((line[x-bpp] if x>=bpp else 0)+prev[x])//2)&255
        elif f==4:
            for x in range(st):
                a=line[x-bpp] if x>=bpp else 0; b=prev[x]; c=prev[x-bpp] if x>=bpp else 0
                pa=abs(b-c);pb=abs(a-c);pc=abs(a+b-2*c)
                line[x]=(line[x]+(a if pa<=pb and pa<=pc else b if pb<=pc else c))&255
        if y in need: rows[y]=bytes(line)
        prev=line
    def g(x,yf):
        r=rows[int(yf*h)]; acc=[0,0,0]; n=0
        for dx in range(-20,21,4):
            o=(int(x*w)+dx)*bpp
            for k in range(3): acc[k]+=r[o+k]
            n+=1
        return tuple(round(a/n) for a in acc)
    return g
ys=[.146,.202,.258,.312,.394,.504]
S=sys.argv[1]; m=load(f'{S}/{sys.argv[2]}',ys); t=load(f'{S}/{sys.argv[3]}',ys)
vals=[round(i*255/31) for i in range(32)]
cols=[(255,0,0),(0,255,0),(0,0,255),(255,255,0),(0,255,255),(255,0,255),(128,0,0),(0,128,0),(0,0,128),(255,128,64),(64,128,255),(200,180,150),(120,160,90),(90,60,140),(250,220,200),(40,40,60)]
for i,v in enumerate(vals): print('grey',v, m((i%8+.5)/8,ys[i//8]), t((i%8+.5)/8,ys[i//8]))
for i,c in enumerate(cols): print('col',c, m((i%8+.5)/8,ys[4+i//8]), t((i%8+.5)/8,ys[4+i//8]))
