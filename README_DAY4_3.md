# Day 4.3

Adds synchronized video-frame metadata persistence using JSONL.

Files:

- `backend/app/services/video/frame_store.py`
- `backend/app/api/video.py`
- `backend/tests/test_frame_store.py`
- `docs/DAY4-3-FRAME-STORAGE.md`

Run:

```powershell
pytest -q
```

No database migration is required for this stage.
