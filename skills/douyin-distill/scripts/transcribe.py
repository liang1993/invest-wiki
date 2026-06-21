#!/usr/bin/env python3
"""批量转写 workdir/media/*.mp4 → workdir/transcripts/*.md，SenseVoice 模型只加载一次。

复用 asr skill 的 SenseVoice-Small 配置，但批量化（model-once），比逐个调 asr 快得多。
标题/日期从 workdir/enum.json 回填（若存在）。断点续传：已存在的 transcript 跳过。

用法：
    python3.14 transcribe.py --workdir DIR
依赖：funasr / torch / ffmpeg（见 asr skill README）。
"""
import argparse, json, re, subprocess, sys, tempfile, datetime
from pathlib import Path


def model_path():
    local = Path.home() / ".cache/modelscope/hub/models/iic/SenseVoiceSmall"
    return str(local) if (local / "model.pt").exists() and (local / "config.yaml").exists() else "iic/SenseVoiceSmall"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    a = ap.parse_args()
    wd = Path(a.workdir); media = wd / "media"; out = wd / "transcripts"; out.mkdir(parents=True, exist_ok=True)
    meta = {}
    if (wd / "enum.json").exists():
        meta = {r["aweme_id"]: r for r in json.loads((wd / "enum.json").read_text())}

    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    print("→ 加载 SenseVoice（一次）", file=sys.stderr, flush=True)
    model = AutoModel(model=model_path(), trust_remote_code=True, device="cpu",
                      disable_update=True, vad_model="fsmn-vad",
                      vad_kwargs={"max_single_segment_time": 30000})
    mp4s = sorted(media.glob("*.mp4"))
    print(f"→ {len(mp4s)} 个 mp4 待转写", file=sys.stderr, flush=True)
    for i, src in enumerate(mp4s, 1):
        m = re.search(r"_(\d{15,})\.mp4$", src.name)
        aid = m.group(1) if m else src.stem
        r = meta.get(aid, {})
        date = r.get("date") or datetime.date.today().isoformat()
        dst = out / f"{date}_{aid}.md"
        if dst.exists():
            print(f"[{i}/{len(mp4s)}] skip {aid}", file=sys.stderr, flush=True); continue
        try:
            with tempfile.TemporaryDirectory() as td:
                wav = Path(td) / "a.wav"
                subprocess.run(["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                               check=True, capture_output=True)
                res = model.generate(input=str(wav), language="zh", use_itn=True,
                                     batch_size_s=60, merge_vad=True, merge_length_s=15)
            text = rich_transcription_postprocess(res[0].get("text", ""))
        except Exception as e:
            print(f"[{i}/{len(mp4s)}] FAIL {aid}: {e}", file=sys.stderr, flush=True); continue
        fm = {"aweme_id": aid, "date": date, "title": r.get("desc", "")[:80], "duration_s": r.get("duration_s")}
        dst.write_text("---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items())
                       + f"\n---\n\n# {r.get('desc','')}\n\n## 逐字稿\n\n{text}\n", encoding="utf-8")
        print(f"[{i}/{len(mp4s)}] ok {aid} ({len(text)}字)", file=sys.stderr, flush=True)
    print(f"DONE transcripts={len(list(out.glob('*.md')))}")


if __name__ == "__main__":
    main()
