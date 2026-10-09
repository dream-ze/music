import subprocess
import re
import shutil
from pathlib import Path

import config


def storage_backend() -> str:
    mode = config.AUDIO_STORAGE
    if mode not in {"auto", "local", "r2"}:
        raise ValueError("AUDIO_STORAGE must be auto/local/r2")
    if mode == "local":
        return mode
    values = [config.R2_ACCOUNT_ID, config.R2_ACCESS_KEY, config.R2_SECRET_KEY,
              config.R2_BUCKET, config.R2_PUBLIC_BASE]
    if all(values):
        return "r2"
    if mode == "r2" or any(values):
        raise ValueError("R2 配置不完整；请补全配置或设置 AUDIO_STORAGE=local")
    return "local"


def local_audio_path(key: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.mp3", key):
        raise ValueError("无效的音频文件名")
    root = Path(config.LOCAL_AUDIO_DIR).resolve()
    path = (root / key).resolve()
    if path.parent != root:
        raise ValueError("无效的音频路径")
    return path


def save_audio(local_path: str, key: str) -> str:
    if storage_backend() == "r2":
        return upload_to_r2(local_path, key)
    target = local_audio_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_path, target)
    return f"/api/media/{key}"


def delete_audio(url: str) -> None:
    if url.startswith("/api/media/"):
        local_audio_path(url.removeprefix("/api/media/")).unlink(missing_ok=True)
    else:
        delete_from_r2(url.rsplit("/", 1)[-1])


def wav_to_mp3(wav_path: str, mp3_path: str) -> str:
    """用 ffmpeg 把 WAV 转 128k MP3。失败抛 RuntimeError。"""
    cmd = ["ffmpeg", "-y", "-i", wav_path, "-b:a", "128k", mp3_path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode(errors="ignore")[:300]
        raise RuntimeError(f"ffmpeg 转码失败: {stderr}")
    return mp3_path


def probe_duration(path: str) -> float:
    """ffprobe 读音频时长(秒);失败返回 0.0。"""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        return 0.0
    try:
        return float(proc.stdout.decode().strip())
    except ValueError:
        return 0.0


_client = None  # 进程内只建一次,复用底层连接池;每次都新建的话每次操作都要重新走一遍 TCP+TLS 握手


def _r2_client():
    global _client
    if _client is None:
        import boto3
        endpoint = f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        _client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=config.R2_ACCESS_KEY,
            aws_secret_access_key=config.R2_SECRET_KEY,
            region_name="auto",
        )
    return _client


def upload_to_r2(local_path: str, key: str) -> str:
    """上传到 R2,返回公网 URL。"""
    client = _r2_client()
    client.upload_file(
        local_path, config.R2_BUCKET, key,
        ExtraArgs={"ContentType": "audio/mpeg"},
    )
    return f"{config.R2_PUBLIC_BASE.rstrip('/')}/{key}"


def delete_from_r2(key: str) -> None:
    """删 R2 上的文件。key 不存在时 S3 API 本身就是幂等的,不报错。"""
    client = _r2_client()
    client.delete_object(Bucket=config.R2_BUCKET, Key=key)
