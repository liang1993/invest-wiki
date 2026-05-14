#!/usr/bin/env python3
"""本地中文 ASR 工具（SenseVoice-Small via funasr）

用法：
    python3 transcribe.py <FILE> [--target DIR] [--language zh|auto|en|yue|ja|ko]

从本地 audio/video 文件出中文逐字稿 markdown。
默认输出到 ~/Downloads/asr-output/，传 --target 才放到指定目录（如 raw/articles/_inbox/）。
输出：终端最后一行 `TRANSCRIPT_PATH=<absolute path>`，便于下游/上游 skill 串联。
"""
import argparse
import datetime
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TARGET = Path.home() / "Downloads/asr-output"
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_")

VALID_LANGUAGES = ["zh", "auto", "en", "yue", "ja", "ko"]


def parse_args():
    p = argparse.ArgumentParser(description="本地 SenseVoice-Small 中文 ASR")
    p.add_argument("file", help="本地 audio/video 文件路径")
    p.add_argument(
        "--target",
        help=f"输出目录（默认 {DEFAULT_TARGET}；传相对路径如 raw/articles/_inbox/ 可入 wiki）",
    )
    p.add_argument(
        "--language",
        default="zh",
        choices=VALID_LANGUAGES,
        help="语言代码（默认 zh，支持粤语 yue / 英日韩等）",
    )
    return p.parse_args()


def check_deps():
    """启动时检查 ffmpeg / funasr / torch 是否就位。"""
    missing = []
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        missing.append("ffmpeg")
    try:
        import funasr  # noqa: F401
    except ImportError:
        missing.append("funasr")
    try:
        import torch  # noqa: F401
    except ImportError:
        missing.append("torch")

    if missing:
        print(f"ERROR: 缺少依赖：{missing}", file=sys.stderr)
        if "ffmpeg" in missing:
            print("  brew install ffmpeg", file=sys.stderr)
        pip_missing = [m for m in missing if m != "ffmpeg"]
        if pip_missing:
            print(
                f"  pip3 install --break-system-packages {' '.join(pip_missing)} torchaudio pyyaml",
                file=sys.stderr,
            )
        sys.exit(1)


def extract_audio(src: Path, wav: Path):
    """ffmpeg 抽 16kHz mono PCM（SenseVoice 标准输入）。"""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        check=True,
        capture_output=True,
    )


def _resolve_model_path() -> str:
    """优先使用本地缓存的 SenseVoiceSmall 目录，避免 modelscope 每次重新校验下载。

    若本地缓存完整（含 model.pt 和必要配置），返回本地绝对路径；否则回落到
    modelscope ID，让 funasr 自己负责下载。
    """
    local = Path.home() / ".cache/modelscope/hub/models/iic/SenseVoiceSmall"
    if (local / "model.pt").exists() and (local / "config.yaml").exists():
        return str(local)
    return "iic/SenseVoiceSmall"


def transcribe(wav: Path, language: str) -> str:
    """SenseVoice-Small 转写，返回纯文本（含标点和数字规整）。"""
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess

    model_arg = _resolve_model_path()
    model = AutoModel(
        model=model_arg,
        trust_remote_code=True,
        device="cpu",                        # Apple Silicon 暂未官方支持 MPS；CPU 已够快
        disable_update=True,                  # 跳过启动时联网检查 funasr 版本
        vad_model="fsmn-vad",                 # 启用 VAD 自动分段，避免长音频一次性吃显存/内存
        vad_kwargs={"max_single_segment_time": 30000},  # 单段最长 30s，控制内存峰值
    )
    result = model.generate(
        input=str(wav),
        language=language,
        use_itn=True,            # 启用文本规整（数字/标点）
        batch_size_s=60,         # 动态批处理 60s 一批
        merge_vad=True,          # 合并 VAD 切出的短片段
        merge_length_s=15,       # 合并长度阈值 15s
    )
    raw_text = result[0].get("text", "")
    return rich_transcription_postprocess(raw_text)


def render(src: Path, clean_text: str) -> str:
    import yaml

    fm = {
        "source": f"file://{src.resolve()}",
        "fetched": datetime.date.today().isoformat(),
        "title": src.stem,
        "publisher": "(本地媒体)",
        "published": None,
        "stocks": [],
        "topics": [],
        "verified": "unverified",
        "asr_engine": "funasr / SenseVoiceSmall",
        "conflicts": [],
    }

    return (
        f"---\n{yaml.dump(fm, allow_unicode=True, sort_keys=False)}---\n\n"
        f"# {src.stem}\n\n"
        f"## 逐字稿\n\n{clean_text}\n"
    )


def main():
    args = parse_args()
    check_deps()

    src = Path(args.file).resolve()
    if not src.exists():
        print(f"ERROR: 文件不存在 {src}", file=sys.stderr)
        sys.exit(1)

    target = Path(args.target) if args.target else DEFAULT_TARGET
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "audio.wav"
        print(f"→ 抽音 {src.name}", file=sys.stderr)
        extract_audio(src, wav)
        print(
            "→ 转写（首次会下载 SenseVoiceSmall ~893MB 到 ~/.cache/modelscope/）",
            file=sys.stderr,
        )
        clean_text = transcribe(wav, args.language)
        md = render(src, clean_text)

    # 避免日期前缀重复：src.stem 已含 YYYY-MM-DD_ 时直接复用
    if DATE_PREFIX_RE.match(src.stem):
        filename = f"{src.stem}.md"
    else:
        filename = f"{datetime.date.today().isoformat()}_{src.stem}.md"
    out = target / filename
    out.write_text(md, encoding="utf-8")
    print(f"TRANSCRIPT_PATH={out.resolve()}")


if __name__ == "__main__":
    main()
