# asr — 一次性安装说明

## 系统依赖

```bash
brew install ffmpeg
```

## Python 依赖

```bash
pip3 install --break-system-packages funasr torch torchaudio pyyaml
```

> 用户机器为 Homebrew Python（PEP 668 保护），所以需要 `--break-system-packages`。这是 invest-wiki 仓库其他 skill（akshare/yfinance）的既有约定。
> 
> `torch` + `torchaudio` 是 funasr 的运行时依赖，但 funasr 安装时**不会**自动拉取，需要显式装一遍（约 500MB-1GB）。

## 验证

```bash
ffmpeg -version
python3 -c "from funasr import AutoModel; print('funasr OK')"
```

## 首次模型下载

首次运行 `transcribe.py` 时自动从 ModelScope 下载 SenseVoiceSmall（model.pt ~893MB + 配置 ~1MB）到 `~/.cache/modelscope/hub/models/iic/SenseVoiceSmall/`。下载完成后完全离线运行。

> ModelScope CDN 单连接可能限速到几百 KB/s。若下载过慢，可手动从 [hf-mirror.com](https://hf-mirror.com/FunAudioLLM/SenseVoiceSmall) 下载 `model.pt` 放到上述缓存目录，`transcribe.py` 会优先使用本地缓存。

## 后端切换（可选）

如果 funasr 在 Apple Silicon 上遇到 PyTorch 兼容性问题，可切到更轻量的 sherpa-onnx：

```bash
pip3 install --break-system-packages sherpa-onnx
```

然后修改 `scripts/transcribe.py` 的 `transcribe()` 函数（参考 [sherpa-onnx SenseVoice 文档](https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html)）。模型文件量化后约 180MB，CoreML 加速。

本期默认使用 funasr 作为官方实现，sherpa-onnx 作为备选。
