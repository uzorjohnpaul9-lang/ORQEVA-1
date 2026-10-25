# Root entrypoint for Railway/Railpack
# Re-export FastAPI app from backend
try:
    from backend.main import app
    __all__ = ["app"]
except Exception as e:
    import logging

    logging.basicConfig(level=logging.INFO)
    logging.error(f"Failed to import backend.main: {e}")
    raise
