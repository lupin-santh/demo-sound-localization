#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source ./env.sh
if [[ " $* " != *" --probe "* ]]; then
  if ! "$task_python" -c 'import tkinter' >/dev/null 2>&1; then
    desktop_python=/home/q/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
    if [[ "$(uname -m)" == x86_64 && -x "$desktop_python" ]] &&
       "$desktop_python" -c 'import tkinter, numpy' >/dev/null 2>&1; then
      task_python="$desktop_python"
      echo 'Using the available desktop Python with Tk.' >&2
    else
      echo 'Tk is unavailable. Install python3-tk or use ./run.sh --probe.' >&2
      exit 1
    fi
  fi
  if [[ " $* " != *" --demo "* ]]; then
    if ! "$task_python" -c 'import webrtcvad' >/dev/null 2>&1; then
      set -- --no-vad "$@"
      echo 'WebRTC VAD is unavailable; starting live direction without voice filtering.' >&2
    fi
    model_name=sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17
    if ! "$task_python" -c 'import sherpa_onnx' >/dev/null 2>&1 ||
       [[ ! -f "$sound_root/models/$model_name/model.int8.onnx" &&
          ! -f "$sound_root/../sound_loca_demo/models/$model_name/model.int8.onnx" ]]; then
      set -- --no-asr "$@"
      echo 'SenseVoice is unavailable; transcription is disabled.' >&2
    fi
  fi
fi
exec "$task_python" -m src.app "$@"
