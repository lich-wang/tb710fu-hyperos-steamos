import sys,zlib,struct
def load(p):
    d=open(p,'rb').read(); i=8; idat=b''
    while i<len(d):
        l,t=struct.unpack('>I4s',d[i:i+8]); c=d[i+8:i+8+l]
        if t==b'IHDR': w,h,bd,ct=struct.unpack('>IIBB',c[:10])
        if t==b'IDAT': idat+=c
        i+=12+l
    bpp={2:3,6:4}[ct]; raw=zlib.decompress(idat); st=w*bpp; rows={}; prev=bytearray(st); p=0
    need={int(f*h) for f in (.20,.42,.88)}
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
    return lambda x,yf: tuple(rows[int(yf*h)][int(x*w)*bpp:int(x*w)*bpp+3])
S=sys.argv[1]; fs=sys.argv[2:]
names=['#000','#101010','#202020','#404040','#808080','#c0c0c0','#ebebeb','#fff','red','green','blue','yellow','cyan','magenta','#800000','#008000']+['grad%.1f'%x for x in (.1,.2,.3,.5,.7,.8,.9)]
G=[load(f'{S}/{f}.png') for f in fs]
pts=[((i+.5)/8,.20) for i in range(8)]+[((i+.5)/8,.42) for i in range(8)]+[(x,.88) for x in (.1,.2,.3,.5,.7,.8,.9)]
print('%-9s'%'patch'+''.join('%-17s'%f for f in fs))
for n,(x,y) in zip(names,pts): print('%-9s'%n+''.join('%-17s'%str(g(x,y)) for g in G))
