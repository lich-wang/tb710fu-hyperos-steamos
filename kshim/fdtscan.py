import sys,struct,re
data=open(sys.argv[1],'rb').read()
pats=[p.encode() for p in sys.argv[2:]]
off=0;i=0
def parse(b):
    magic,tot,ost,ostr,omr,ver,lc,bp,szs,szst=struct.unpack('>10I',b[:40])
    st=b[ostr:ostr+szst]; p=ost; path=[]; out=[]
    def s(o): return st[o:st.index(b'\0',o)].decode()
    while True:
        tok=struct.unpack('>I',b[p:p+4])[0]; p+=4
        if tok==1:
            e=b.index(b'\0',p); path.append(b[p:e].decode()); p=(e+4)&~3
        elif tok==2: path.pop()
        elif tok==3:
            ln,no=struct.unpack('>II',b[p:p+8]); p+=8; v=b[p:p+ln]; p=(p+ln+3)&~3
            out.append(('/'.join(path) or '/', s(no), v))
        elif tok==4: continue
        elif tok==9: break
    return out
while True:
    j=data.find(b'\xd0\x0d\xfe\xed',off)
    if j<0: break
    tot=struct.unpack('>I',data[j+4:j+8])[0]
    props=parse(data[j:j+tot])
    model=[v for pth,n,v in props if pth=='/' and n in('model','compatible','qcom,board-id','qcom,msm-id')]
    print('=== dtb',i,'@',j,'size',tot, [m[:80] for m in model])
    for pth,n,v in props:
        key=(pth+':'+n).encode()
        if any(re.search(pt,key) for pt in pats):
            if all(32<=c<127 or c==0 for c in v) and v.endswith(b'\0') and len(v)>1:
                vs=v.decode().replace('\0','|')
            else: vs=v[:64].hex()
            print(' ',pth,n,'=',vs[:200])
    off=j+tot; i+=1
    if len(sys.argv)>1 and i>=int(__import__('os').environ.get('MAXDTB','2')): break
