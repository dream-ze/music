import subprocess

import config


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


def _r2_client():
    import boto3
    endpoint = f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=config.R2_ACCESS_KEY,
        aws_secret_access_key=config.R2_SECRET_KEY,
        region_name="auto",
    )


def upload_to_r2(local_path: str, key: str) -> str:
    """上传到 R2,返回公网 URL。"""
    client = _r2_client()
    client.upload_file(
        local_path, config.R2_BUCKET, key,
        ExtraArgs={"ContentType": "audio/mpeg"},
    )
    return f"{config.R2_PUBLIC_BASE.rstrip('/')}/{key}"
