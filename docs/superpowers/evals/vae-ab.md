# VAE A/B：official vs ScragVAE

## 流程

1. 用 DB 里已有歌曲的 `spec_json` + `structured_lyrics`（不过 LLM，避免 planner 非确定性），固定 seed 出一次歌，截获 `extra_outputs["pred_latents"]`。
2. 同一份 latent 分别用 official / ScragVAE 解码，都走上游 `dit.tiled_decode`（MPS 上即 MLX VAE）；换 VAE 后重建 `mlx_vae`。唯一变量是解码器权重。
3. 指标对齐 ScragVAE 模型卡：高频能量占比、频带相对能量、95% 滚降、谱质心、峰均比。试听文件 RMS 对齐到 -16 dBFS。
4. ScragVAE 权重：HF 本机不通，用 `HF_ENDPOINT=https://hf-mirror.com`，只下 `config.json` + `diffusion_pytorch_model.safetensors`（644MB，F32）到 `ACE-Step-1.5/checkpoints/scragvae/`。config 与官方 VAE 完全一致。

## 记录

### 2026-10-05 · 《诞生以前》(9ea006bd) · seed 1001 · 112s · turbo + 0.6B LM

| 指标 | official | scragvae | 差值 |
|---|---|---|---|
| RMS dBFS | -14.36 | -14.81 | -0.44 |
| 峰均比 dB | 14.36 | 14.81 | +0.44 |
| 帧响度跨度 dB (p95/p5) | 16.18 | 16.06 | -0.12 |
| >8kHz 能量占比 % | 1.07 | 1.54 | +0.46（相对 +43%） |
| >12kHz 能量占比 % | 0.14 | 0.28 | +0.13（约 2 倍） |
| 6–12kHz 相对 dB | -18.55 | -17.45 | +1.11 |
| 12–24kHz 相对 dB | -28.42 | -25.54 | +2.88 |
| 95% 滚降 Hz | 1945 | 2859 | +914 |
| 谱质心 Hz | 530 | 606 | +76 |

- 两路波形相关 0.974：整体一致，差异集中在高频细节。
- 削波（\|x\|≥0.999）：official 24 样本，scragvae 74 样本，均 <0.001%，上游出歌路径会做峰值归一化（pipeline 峰值 0.891），可忽略。
- 对照路径校验：pipeline 原输出与 official 重解码相关 0.9999999（差异来自上游峰值归一化）。
- 未见模型卡宣称的 +29dB 动态范围；本例帧响度跨度基本不变。
- 主观打分：待填（人声齿音/镲片/空气感是否变好，有无刺耳）。

文件：`outputs/vae_ab/`（`listen_official.wav` / `listen_scragvae.wav` / `latents.pt` / `meta.json`）。
