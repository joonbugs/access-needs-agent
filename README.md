## EventListenerComponent (MVP)

This MVP processes transcript **chunk JSON files** dropped into `input/pending/`.

### Folder layout

- `input/pending/`: newly received transcript chunks (JSON files)
- `input/processed/`: successfully validated + processed chunks
- `input/failed/`: rejected chunks (validation/parsing errors)

### Run (process once)

From the project root:

```bash
python3 process_pending.py --once
```

### Run (watch / continuous polling)

```bash
python3 process_pending.py --watch --poll-seconds 1
```

### Notes

- **File size limit**: rejects files larger than 5MB (configurable via `--max-mb`)
- **Ordering**: by default it processes chunks **strictly in increasing `chunk_id` order per `session_id`**. If a chunk arrives out of order (gap), it is left in `pending` until the missing chunk arrives.
