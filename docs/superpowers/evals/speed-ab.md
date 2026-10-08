# 出歌速度 A/B（ACE-Step 运行配置）

## 方法

同一首歌（「城市流行验收」，182 秒，seed 295927074）的 spec + 整理后歌词，用独立进程直接调 `song_gen.generate_song`，只改环境变量。后端服务停掉后依次运行，避免两个 ACE-Step 进程争内存。阶段按 ACE-Step 进度回调切分：LM（<0.52）、DiT（0.52–0.8）、解码（≥0.8）。

## 结果（2026-10-08，M 芯片 16GB，turbo + 0.6B LM）

| 配置 | 模型加载 | 生成总计 | LM 旋律编码 | DiT 8 步 | VAE 解码 | MLX 峰值 |
|---|---|---|---|---|---|---|
| X：`LM_BACKEND=pt` + offload + VAE FP32（原配置） | 114s | **458s** | 237s | 133s | 88s | 12.2 GB |
| Y：`LM_BACKEND=mlx` + **关 offload** + VAE FP16 | 138s | **OOM**（DiT 阶段） | — | — | — | — |
| Z：`LM_BACKEND=mlx` + offload + VAE FP16 | 135s | **254s（−45%）** | 56s（×4.3） | 129s | 70s | 10.6 GB |

- Y 失败原因：MPS 已分配 12.0 GiB + 其他 7.9 GiB > 上限 20.1 GiB。PyTorch 版 DiT 不 offload 时常驻 MPS，MLX 又转换出一份 DiT，同一模型两份。**offload 必须保留。**
- X 运行期间系统 swap 从 0.6 GB 涨到 17.7 GB：内存本身已经很紧，DiT 每步约 12 秒很可能受 swap 拖累，这是下一步提速要看的地方。
- 音频检查：两首都无 NaN、无削波（峰值 0.891，上游归一化），静音帧 0.6% / 0.7%。MLX 与 PyTorch 的 LM 采样实现不同，同 seed 旋律不逐音相同，主观质量待试听。

## 结论

线上改用 Z：`.env` 中 `ACESTEP_LM_BACKEND=mlx`、`ACESTEP_MLX_VAE_FP16=1`，offload 保持默认开启。回退：恢复 `~/zemusic-env.bak-speed`(仓库外,含密钥)（或把这两行改回 `pt` / 删除），再重启后端。

## 释放 PyTorch 版 DiT decoder（2026-10-08，同上方法）

MLX DiT 初始化后，PyTorch 主模型里的 `decoder`（约占 DiT 权重 2/3，MPS 上 float32 约 6GB）与 MLX 那份重复；出歌主路径只用 `prepare_condition`（encoder / tokenize / detokenize）。`song_gen.release_torch_decoder` 用占位模块替换它。

| 运行 | decoder | 模型加载 | LM | DiT 阶段（扩散） | 解码 | 生成总计 | MLX 峰值 | MPS 驱动 |
|---|---|---|---|---|---|---|---|---|
| Z | 保留 | 135s | 56s | 129s（94s） | 70s | 254s | 10.6 GB | 17.9 GB |
| W | 释放 | 159s | 57s | 169s（123s） | 101s | 327s | 10.6 GB | **12.4 GB** |
| Z2（重跑 Z） | 保留 | 148s | 55s | 162s（112s） | 70s | 286s | 10.6 GB | 17.9 GB |

- 释放后 PyTorch 侧少占 **5.4 GB**，确认生效。
- 速度无可测差异：同配置 Z/Z2 的扩散就相差 18s；W 慢在 MLX 计算（扩散、VAE），与 PyTorch 侧无关，属于运行间波动。
- 每次运行 swap 都上涨，主要来自 MLX 侧（峰值 10.6 GB）。机器为 **Apple M1（8 核 GPU）**，DiT 每步 12–15 秒更像算力上限，而非 swap 拖累。
- 结论：保留释放（省内存、降低 OOM 风险）；`ACESTEP_KEEP_TORCH_DIT=1` 可恢复上游行为（含 MLX 失败时的 PyTorch 回退）。
- 单次测量波动约 ±15%，后续速度对比需每个配置跑 2 次以上。
