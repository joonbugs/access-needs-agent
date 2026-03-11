## EventListenerComponent (MVP)

This MVP processes transcript **SRT files** dropped into `input/pending/`.

### Folder layout

- `input/pending/`: newly received transcript files (`.srt`)
- `input/processed/`: successfully validated + processed transcripts
- `input/failed/`: rejected transcripts (validation/parsing errors)

### Run

From the project root:

```bash
python3 process_pending.py
```
