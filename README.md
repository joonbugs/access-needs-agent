## EventListenerComponent (MVP)

This MVP processes transcript **SRT files** dropped into `input/pending/`.

### Folder layout

- `input/pending/`: newly received transcript files (`.srt`)
- `input/processed/`: successfully validated + processed transcripts
- `input/failed/`: rejected transcripts (validation/parsing errors)

### Run

From the project root:

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your OpenAI API key (recommended for local dev: `.env` file):

1) Copy the example file:

```bash
cp .env.example .env
```

2) Edit `.env` and put your real key in `OPENAI_API_KEY`.

Alternatively, you can export it in your shell:

```bash
export OPENAI_API_KEY="YOUR_KEY_HERE"
```

Then run:

```bash
python3 process_pending.py
```
