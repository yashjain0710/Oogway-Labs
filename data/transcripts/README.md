# Transcripts

This folder holds Lenny's Podcast transcript files.

## Official source (evaluator)

Clone the official repo and copy `.txt`/`.md` files here:

```bash
git clone https://github.com/ChatPRD/lennys-podcast-transcripts /tmp/lenny-tx
cp /tmp/lenny-tx/*.txt data/transcripts/   # adjust to the repo's actual layout
python -m backend.scripts.ingest --force
```

Then restart the backend so retrieval picks up the new `data/index/chunks.json`.

## Bundled samples (so the demo works offline)

`data/transcripts/samples/*.txt` contains short paraphrased sample episodes used
when the official transcripts are not present. They cover product-market fit,
growth loops, and onboarding. Replace or extend them with real transcripts —
the pipeline reads every `.txt/.md/.srt/.vtt/.json` file under this folder.
