"""Backward compatibility: `python web.py` still works."""
from key_manager.web import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18001)
