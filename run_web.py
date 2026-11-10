import uvicorn
from app.config import config
from app.utils.logger import logger

if __name__ == "__main__":
    logger.info(f"Starting IQ Option Web Dashboard on http://{config.WEB_HOST}:{config.WEB_PORT}")
    uvicorn.run(
        "app.web.server:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        reload=False,
        log_level="info"
    )
