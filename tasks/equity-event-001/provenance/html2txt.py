import re, sys
from html.parser import HTMLParser

BLOCK = {"p","div","tr","table","section","article","h1","h2","h3","h4","h5","h6","li","ul","ol","br","hr","title","center","blockquote","thead","tbody","tfoot"}
SKIP = {"script","style","head","meta","link","ix:header","ix:hidden"}
VOID = {"br","hr","img","meta","link","input","col","area","base","source","wbr","embed","param","track"}

class T(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out=[]; self.skip_stack=[]; self.cellbuf=None
        self.rowdepth=0
    def _hidden(self, attrs):
        for k,v in attrs:
            if k=="style" and v and re.search(r"display\s*:\s*none", v, re.I): return True
            if k=="hidden": return True
        return False
    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        if self.skip_stack:
            if tag not in VOID: self.skip_stack.append(tag)
            return
        if tag in SKIP or self._hidden(attrs):
            self.skip_stack=[tag]; return
        if tag=="tr":
            self.flush(); self.out.append("\n")
        elif tag in ("td","th"):
            self.flush(); self.cellbuf=[]
        elif tag=="br":
            self.flush(); self.out.append("\n")
        elif tag in BLOCK:
            self.flush(); self.out.append("\n")
        elif tag=="li":
            self.flush(); self.out.append("\n• ")
    def handle_startendtag(self, tag, attrs):
        if not self.skip_stack and tag.lower()=="br": self.flush(); self.out.append("\n")
    def handle_endtag(self, tag):
        tag=tag.lower()
        if self.skip_stack:
            if self.skip_stack[-1]==tag: self.skip_stack.pop()
            return
        if tag=="tr":
            self.flush(); self.out.append("\n")
        elif tag in ("td","th"):
            self.flush()
        elif tag in BLOCK:
            self.out.append("\n")
    def flush(self):
        if self.cellbuf is not None:
            s=re.sub(r"\s+"," ","".join(self.cellbuf)).strip()
            if s: self.out.append(" | "+s+" | ")
            self.cellbuf=None
    def handle_data(self, d):
        if self.skip_stack: return
        if self.cellbuf is not None: self.cellbuf.append(d)
        else: self.out.append(d)
    def text(self):
        self.flush()
        s="".join(self.out).replace("\xa0"," ")
        s=re.sub(r"\|[ \t]*\|","|",s)
        lines=[]
        for ln in s.split("\n"):
            ln=re.sub(r"[ \t]+"," ",ln).strip()
            ln=re.sub(r"^\| ?","",ln); ln=re.sub(r" ?\|$","",ln)
            if ln: lines.append(ln)
        out=[]; prev=None
        for ln in lines:
            if ln==prev: continue
            out.append(ln); prev=ln
        return "\n".join(out)+"\n"

def convert(path):
    raw=open(path,"rb").read().decode("utf-8","replace")
    t=T(); t.feed(raw); return t.text()

if __name__=="__main__":
    txt=convert(sys.argv[1]); open(sys.argv[2],"w").write(txt); print(sys.argv[2], len(txt))
