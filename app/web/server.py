import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from app.config import config, Config
from app.core.client import iq_client
from app.core.bot_controller import bot_controller
from app.core.executor import get_recent_trades
from app.core.scanner import scanner
from app.risk.money_manager import money_manager
from app.utils.logger import get_recent_logs, logger

app = FastAPI(title="IQ Option Trading Bot Dashboard")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

class ConfigUpdateModel(BaseModel):
    iq_email: Optional[str] = None
    iq_password: Optional[str] = None
    account_mode: Optional[str] = None
    base_bet: Optional[float] = None
    martingale_steps: Optional[int] = None
    min_payout: Optional[float] = None
    top_pairs_count: Optional[int] = None
    rsi_period: Optional[int] = None
    rsi_oversold: Optional[float] = None
    rsi_overbought: Optional[float] = None
    daily_stop_loss: Optional[float] = None
    daily_take_profit: Optional[float] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None

class LoginModel(BaseModel):
    email: str
    password: str
    mode: str = "PRACTICE"

class TwoFactorModel(BaseModel):
    code: str

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"config": config}
    )

@app.get("/api/status")
async def get_status():
    return bot_controller.get_status()

@app.post("/api/bot/start")
async def start_bot():
    res = bot_controller.start()
    return res

@app.post("/api/bot/stop")
async def stop_bot():
    res = bot_controller.stop()
    return res

@app.get("/api/trades")
async def get_trades():
    return get_recent_trades()

@app.get("/api/logs")
async def get_logs():
    return get_recent_logs()

@app.get("/api/scanner")
async def get_scanner():
    return scanner.get_high_payout_pairs()

@app.post("/api/connect")
async def connect_iq(payload: LoginModel):
    config.IQ_EMAIL = payload.email
    config.IQ_PASSWORD = payload.password
    config.ACCOUNT_MODE = payload.mode
    iq_client.set_mode(payload.mode)
    success, reason = iq_client.connect(payload.email, payload.password)
    return {
        "success": success,
        "reason": reason,
        "two_factor_required": iq_client.two_factor_required,
        "balance": iq_client.get_balance() if success else 0.0,
        "mode": iq_client.current_mode
    }

@app.post("/api/2fa")
async def submit_2fa(payload: TwoFactorModel):
    success, msg = iq_client.submit_2fa(payload.code)
    return {"success": success, "message": msg, "balance": iq_client.get_balance() if success else 0.0}

@app.post("/api/config")
async def update_config(payload: ConfigUpdateModel):
    if payload.account_mode:
        config.ACCOUNT_MODE = payload.account_mode.upper()
        iq_client.set_mode(payload.account_mode)
        Config.save_setting("ACCOUNT_MODE", config.ACCOUNT_MODE)
    if payload.base_bet is not None:
        config.BASE_BET = float(payload.base_bet)
        Config.save_setting("BASE_BET", str(config.BASE_BET))
    if payload.martingale_steps is not None:
        config.MARTINGALE_STEPS = int(payload.martingale_steps)
        Config.save_setting("MARTINGALE_STEPS", str(config.MARTINGALE_STEPS))
    if payload.min_payout is not None:
        val = payload.min_payout
        config.MIN_PAYOUT = (val / 100.0) if val > 1 else val
        scanner.min_payout = config.MIN_PAYOUT
        Config.save_setting("MIN_PAYOUT", str(int(round(config.MIN_PAYOUT * 100))))
    if payload.top_pairs_count is not None:
        config.TOP_PAIRS_COUNT = int(payload.top_pairs_count)
        Config.save_setting("TOP_PAIRS_COUNT", str(config.TOP_PAIRS_COUNT))
    if payload.rsi_period is not None:
        config.RSI_PERIOD = int(payload.rsi_period)
        Config.save_setting("RSI_PERIOD", str(config.RSI_PERIOD))
    if payload.rsi_oversold is not None:
        config.RSI_OVERSOLD = float(payload.rsi_oversold)
        Config.save_setting("RSI_OVERSOLD", str(config.RSI_OVERSOLD))
    if payload.rsi_overbought is not None:
        config.RSI_OVERBOUGHT = float(payload.rsi_overbought)
        Config.save_setting("RSI_OVERBOUGHT", str(config.RSI_OVERBOUGHT))
    if payload.daily_stop_loss is not None:
        config.DAILY_STOP_LOSS = float(payload.daily_stop_loss)
        Config.save_setting("DAILY_STOP_LOSS", str(config.DAILY_STOP_LOSS))
    if payload.daily_take_profit is not None:
        config.DAILY_TAKE_PROFIT = float(payload.daily_take_profit)
        Config.save_setting("DAILY_TAKE_PROFIT", str(config.DAILY_TAKE_PROFIT))
    if payload.telegram_bot_token is not None:
        config.TELEGRAM_BOT_TOKEN = payload.telegram_bot_token
        Config.save_setting("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN)
    if payload.telegram_chat_id is not None:
        config.TELEGRAM_CHAT_ID = payload.telegram_chat_id
        Config.save_setting("TELEGRAM_CHAT_ID", config.TELEGRAM_CHAT_ID)
    if payload.telegram_enabled is not None:
        config.TELEGRAM_ENABLED = payload.telegram_enabled
        Config.save_setting("TELEGRAM_ENABLED", str(config.TELEGRAM_ENABLED).lower())

    # Keep custom steps synced with new ladder
    new_ladder = config.get_martingale_ladder()
    config.CUSTOM_STEPS_STR = ",".join(str(x) for x in new_ladder)
    Config.save_setting("CUSTOM_STEPS", config.CUSTOM_STEPS_STR)

    money_manager.reload_config()
    logger.info(f"[Web] Configuration updated via dashboard (Base Bet: ${config.BASE_BET}, Ladder: {new_ladder}, Min Payout: {config.MIN_PAYOUT:.0%}, Top Pairs: {config.TOP_PAIRS_COUNT}).")
    return {"status": "success", "message": "Settings updated", "base_bet": config.BASE_BET, "ladder": new_ladder}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Broadcast snapshot every second
            payload = {
                "status": bot_controller.get_status(),
                "trades": get_recent_trades()[:10],
                "logs": get_recent_logs()[-20:],
                "scanner": scanner.get_top_pairs(limit=config.TOP_PAIRS_COUNT)
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
