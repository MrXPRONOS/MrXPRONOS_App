import unittest
from course_formats import attachment_family, groups, complete
from relay import classify, fingerprints

def poster(text="", **kw):
    return dict(kind="poster",text=text,name="",size=0,media="",**kw)
def description(text):
    return dict(kind="text",text=text,name="",size=0,media="")
def file(name, i=1, text="", **kw):
    return dict(kind="file",name=name,text=text,size=100+i,media=str(i),family=attachment_family(name),**kw)

class Formats(unittest.TestCase):
    def test_supported(self):
        for name, family in [("a.MKV","video"),("a.pdf","document"),("a.zip","archive"),("a.part01.rar","archive"),("a.zip.001","archive"),("a.7z","archive"),("a.flac","audio"),("a.xlsx","spreadsheet"),("a.pptx","presentation"),("a.png","poster"),("a.srt","subtitle")]:
            with self.subTest(name=name): self.assertEqual(attachment_family(name,"application/octet-stream"),family)
    def test_mime(self):
        self.assertEqual(attachment_family("","application/vnd.rar"),"archive")
        self.assertEqual(attachment_family("","video/x-matroska"),"video")
    def test_blocked(self):
        for name in ("x.exe","x.apk","x.pdf.exe","x.docm","x.unknown"):
            self.assertIsNone(attachment_family(name,"video/mp4"))
    def test_long_course(self):
        items=[poster(),description("Marketing : 25 vidéos")]+[file(f"Partie {i}.mkv",i) for i in range(1,26)]
        self.assertEqual(list(groups(items)),[items])
    def test_mixed(self):
        items=[poster("Cours business"),description("Supports"),file("support.pdf"),file("partie 1.mp4",2),file("partie 2.mp4",3),file("ressources.zip",4),poster()]
        self.assertEqual(list(groups(items)),[items[:-1]])
    def test_missing_part(self):
        items=[poster(),file("partie 1.rar"),file("partie 3.rar",3),poster()]
        self.assertEqual(list(groups(items)),[])
    def test_incomplete_tail(self):
        self.assertEqual(list(groups([poster(),file("a.pdf")])),[])
    def test_protected(self):
        self.assertEqual(list(groups([poster(),file("a.pdf",protected=True),poster()])),[])
    def test_duplicate(self):
        items=[poster("Formation marketing digital"),file("cours.pdf")]
        cid,marks=fingerprints("key",items)
        other,other_marks=fingerprints("key",[poster("Autre affiche"),file("cours.pdf")])
        self.assertEqual(cid,other)
        self.assertTrue(set(marks)&set(other_marks))
    def test_category(self):
        for text,cat in [("marketing business","business"),("bitcoin blockchain","finance"),("python programmation","digitale"),("leadership discipline","mindset")]:
            self.assertEqual(classify(text),cat)

if __name__=="__main__": unittest.main()
