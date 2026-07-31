from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_user
from ..db import get_db
from ..extraction import parse_eml, parse_pasted
from ..imap_poller import state as imap_state
from ..ingest import ingest_parsed
from ..schemas import IngestRequest, IngestResponse

router = APIRouter(prefix="/api/emails", tags=["emails"], dependencies=[Depends(require_user)])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(body: IngestRequest, db: AsyncSession = Depends(get_db)):
    return await ingest_parsed(parse_pasted(body.raw_text), db)


@router.post("/ingest-eml", response_model=IngestResponse)
async def ingest_eml(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await ingest_parsed(parse_eml(await file.read()), db)


@router.get("/imap-status")
async def imap_status():
    return imap_state
