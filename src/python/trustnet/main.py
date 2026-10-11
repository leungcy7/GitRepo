from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from trustnet import TRUSTNET_URL, TrustnetError, fetch_top_funds

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Trustnet Fund Performance Leaders")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=None)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/api/funds")
async def get_funds(
    period: Literal["1y", "3y", "5y"] = Query(default="5y"),
    management: Literal["active", "passive", "all"] = Query(default="all"),
):
    try:
        funds = await run_in_threadpool(fetch_top_funds, 50, period, management)
    except TrustnetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "source_url": TRUSTNET_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": period,
        "period_label": {"1y": "1 year", "3y": "3 years", "5y": "5 years"}[period],
        "management": management,
        "funds": funds,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
