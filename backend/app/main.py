from __future__ import annotations
import os,tempfile
from pathlib import Path
from fastapi import FastAPI,File,Form,HTTPException,UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from .compressor import compress

MAX=int(os.getenv("MAX_UPLOAD_BYTES","100000000"))
ORIGINS=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","*").split(",") if x.strip()]
app=FastAPI(title="Target PDF Compressor API")
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"],expose_headers=["X-Original-Size-Bytes","X-Compressed-Size-Bytes","X-Target-Reached","X-Selected-DPI"])

@app.get("/health")
def health():return {"status":"ok"}

@app.post("/compress")
async def route(file:UploadFile=File(...),target_mb:float=Form(...),minimum_dpi:int=Form(90),grayscale:bool=Form(False)):
    if target_mb<=0:raise HTTPException(400,"Target size must be greater than zero.")
    if not 36<=minimum_dpi<=300:raise HTTPException(400,"Minimum DPI must be between 36 and 300.")
    name=file.filename or "document.pdf"
    if file.content_type!="application/pdf" and not name.lower().endswith(".pdf"):raise HTTPException(400,"Only PDF files are accepted.")
    td=tempfile.TemporaryDirectory();base=Path(td.name);src=base/"input.pdf";dst=base/"compressed.pdf";total=0
    try:
        with src.open("wb") as out:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>MAX:raise HTTPException(413,f"Upload exceeds {MAX/1000000:.0f} MB.")
                out.write(chunk)
        if src.read_bytes()[:5]!=b"%PDF-":raise HTTPException(400,"The uploaded file is not a valid PDF.")
        r=compress(src,dst,int(target_mb*1000000),minimum_dpi,gray=grayscale)
        return FileResponse(dst,media_type="application/pdf",filename=f"{Path(name).stem}-compressed.pdf",
          headers={"X-Original-Size-Bytes":str(r.original),"X-Compressed-Size-Bytes":str(r.compressed),
          "X-Target-Reached":str(r.reached).lower(),"X-Selected-DPI":str(r.dpi)},
          background=BackgroundTask(td.cleanup))
    except HTTPException:
        td.cleanup();raise
    except Exception as e:
        td.cleanup();raise HTTPException(500,f"Compression failed: {e}")
