import time
from app.core.bot_controller import bot_controller
from app.utils.logger import logger

def main():
    logger.info("=== Starting IQ Option Bot in CLI Mode ===")
    status = bot_controller.start()
    logger.info(f"Start status: {status}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down bot...")
        bot_controller.stop()
        logger.info("Bot shut down gracefully.")

if __name__ == "__main__":
    main()
