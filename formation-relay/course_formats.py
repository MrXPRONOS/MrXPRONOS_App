"""Course attachment identification and conservative grouping (no network)."""
import re
import unicodedata

FORMATS = {
    "video": "mp4 mkv webm mov avi m4v mpg mpeg m2ts mts ts wmv flv 3gp 3g2 ogv vob asf rm rmvb",
    "audio": "mp3 m4a aac wav flac ogg oga opus wma aiff aif amr",
    "document": "pdf epub mobi azw azw3 djvu doc docx odt rtf txt md xps",
    "spreadsheet": "xls xlsx ods csv tsv",
    "presentation": "ppt pptx odp pps ppsx",
    "archive": "zip rar 7z tar gz bz2 xz tgz tbz tbz2 txz",
    "subtitle": "srt vtt ass ssa",
    "project": "ipynb json xml psd ai svg fig blend",
}
EXTENSIONS = {ext: family for family, exts in FORMATS.items() for ext in exts.split()}
POSTER_EXT = {"jpg","jpeg","png","webp","heic","heif","bmp","tif","tiff"}
BLOCKED = {"exe","msi","bat","cmd","scr","com","apk","app","dmg","deb","rpm","dll","ps1","vbs","js","jar","iso","lnk","html","htm","docm","xlsm","pptm","xlam"}
MIME_TYPES = {
    "application/pdf":"document","application/epub+zip":"document",
    "application/msword":"document","application/rtf":"document",
    "application/zip":"archive","application/x-zip-compressed":"archive",
    "application/x-rar-compressed":"archive","application/vnd.rar":"archive",
    "application/x-7z-compressed":"archive","application/x-tar":"archive",
    "application/gzip":"archive","application/x-bzip2":"archive",
    "application/x-xz":"archive","application/vnd.ms-excel":"spreadsheet",
    "application/vnd.ms-powerpoint":"presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":"document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":"spreadsheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation":"presentation",
}
def attachment_family(name="", mime=""):
    name=(name or "").strip().lower()
    mime=(mime or "").split(";")[0].strip().lower()
    ext=name.rsplit(".",1)[-1] if "." in name else ""
    if ext in BLOCKED: return None
    if re.search(r"\.(?:zip|7z|rar)\.\d{3,}$|\.[rz]\d{2,3}$",name): return "archive"
    if ext in EXTENSIONS: return EXTENSIONS[ext]
    if ext in POSTER_EXT: return "poster"
    # Unknown named extensions are reviewed, not silently accepted via MIME.
    if ext: return None
    if mime.startswith("video/"): return "video"
    if mime.startswith("audio/"): return "audio"
    if mime.startswith("image/") and mime not in {"image/svg+xml","image/gif"}: return "poster"
    return MIME_TYPES.get(mime)

def normalized(s):
    return "".join(c for c in unicodedata.normalize("NFKD",s.lower()) if not unicodedata.combining(c))

def parts(m):
    # Filename and caption may each describe the same part; do not count twice.
    for raw in (m.get("name",""),m.get("text","")):
        raw=normalized(raw)
        match=re.search(r"\b(?:partie|module|episode|chapitre|lecon|part|video|cours|lesson)[\s._-]*0*(\d+)(?:\s*(?:/|sur|of)\s*(\d+))?",raw)
        if not match:
            match=re.search(r"\.(?:zip|7z|rar)\.(\d{3,})$",raw)
        if match:
            return int(match[1]),int(match[2]) if match.lastindex==2 and match[2] else None
    return None,None

def hints(s):
    s=normalized(s)
    return [int(n) for n in re.findall(r"\b(\d+)\s*(?:videos|pdf|fichiers|episodes|parties|modules|archives)\b",s)]

def complete(group, bounded):
    files=[m for m in group if m["kind"]=="file"]
    if not files or any(m.get("protected") or m["kind"]=="other" for m in group): return False
    first=group.index(files[0])
    if any(m["kind"]=="text" for m in group[first+1:]): return False
    # Multi-part archives (.r00/.z01) have format-specific terminators;
    # don't distribute a potentially incomplete legacy volume set.
    if any(re.search(r"\.[rz]\d{2,3}$",m.get("name",""),re.I) for m in files):
        return False
    declared=[n for m in group[:first] for n in hints(m.get("text",""))]
    numbered=[parts(m) for m in files]
    # Count by attachment family for mixed courses (PDF + videos + archive).
    for family in {m.get("family") for m in files}:
        seq=[parts(m) for m in files if m.get("family")==family]
        nums=[n for n,_ in seq if n is not None]
        totals=[n for _,n in seq if n is not None]
        if nums and nums!=list(range(1,len(nums)+1)): return False
        if totals and any(n!=len(nums) for n in totals): return False
    # A single explicit file count can prove the end of the newest group.
    explicit = bool(declared) and (len(declared)==1 and declared[0]==len(files))
    if declared and not explicit:
        # Multiple per-type counts must agree on the total.
        explicit=sum(declared)==len(files)
        if not explicit: return False
    sequence_complete=all(n is not None and t is not None for n,t in numbered)
    return bounded or explicit or sequence_complete

def groups(messages):
    current=[]
    for m in messages:
        if m["kind"]=="poster":
            # Consecutive album photos belong to the same header.
            if current and not any(x["kind"]=="file" for x in current) and m.get("album") and m.get("album")==current[0].get("album"):
                current.append(m)
                continue
            if current and complete(current,True): yield current
            current=[m]
        elif current:
            current.append(m)
    if current and complete(current,False): yield current
