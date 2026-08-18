# Day 5.5.2 — Resumable Sewer-ML Range Downloader

The downloader reads the train00 ZIP central-directory plan and fetches only
selected PNG members using HTTP byte ranges.

It does not download the full `train00.zip`.

Features:

- HTTP Range requests
- Basic authentication
- range-length and `Content-Range` verification
- raw-deflate ZIP member decompression
- uncompressed-size verification
- `.part` temporary files
- resumable `.download_state.json`
- retry with exponential backoff

## First smoke test

Do not start all 11,192 images immediately.

Run a single image:

```powershell
python scripts\download_sewer_subset.py `
  --username username `
  --password "YOUR_PASSWORD" `
  --max-images 1
```

After it succeeds, inspect:

```text
approved-data/sewer-ml/images/train00_subset/
```

Only then increase the run size.
