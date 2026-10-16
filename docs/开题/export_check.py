# -*- coding: utf-8 -*-
"""目检：开题报告首页 + PPT 第 1/5/7 页导出 PNG。"""
import win32com.client
import os

DOCX = r"e:\code\resumatch-ai\docs\开题\河北东方学院本科毕业论文（设计）开题报告.docx"
PPTX = r"e:\code\resumatch-ai\docs\开题\开题答辩PPT.pptx"
OUT = r"C:\Users\许\AppData\Local\Temp\final_check"
os.makedirs(OUT, exist_ok=True)

word = win32com.client.Dispatch("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
try:
    doc = word.Documents.Open(DOCX, ReadOnly=True)
    doc.SaveAs2(OUT + r"\ktbg.pdf", FileFormat=17)
    doc.Close(False)
finally:
    word.Quit()

app = win32com.client.Dispatch("PowerPoint.Application")
pres = app.Presentations.Open(PPTX, ReadOnly=True, WithWindow=False)
pres.SaveAs(OUT + r"\ppt", 18)
pres.Close()
app.Quit()
print("done:", os.listdir(OUT))
