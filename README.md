# ComfyUI-FishCustom-Nodes 🐟

[English](README_EN.md) | **中文**

ComfyUI 自定义节点：词条生成/过滤、逻辑路由、批量分文件夹保存、批量采样。

---

## 节点列表

| 节点 | 分类 | 说明 |
|---|---|---|
| **Static Tag** | `FishCustom/tag` | 输出固定词条，原样透传。 |
| **Random Tag** | `FishCustom/tag` | 加权随机词条，支持权重上限与三种模式（strict / relaxed / zero_allowed）。 |
| **Tag Blacklist** | `FishCustom/tag` | 黑名单删除词条，支持子串/精确匹配，可命中 `(tag:1.2)` 权重写法。 |
| **Tag Mutual Exclusion** | `FishCustom/tag` | 互斥词条过滤，每组最多保留一个（random / first / last）。 |
| **Text Analyzer** | `FishCustom/logic` | 关键词检测，输出选择器信号（INT）。 |
| **Smart Switch** | `FishCustom/logic` | 按选择器路由 10 路输入（懒求值，只计算激活分支）。 |
| **Concat** | `FishCustom/utils` | 合并最多 10 路文本输入，可自定义分隔符；`newline=True` 时用换行连接，适合拼多行 recipe。 |
| **Batch Sampler** | `FishCustom/sample` | 一个节点替代 N 条并列采样链：多行 recipe 逐行采样，支持逐图 seed / denoise / latent 来源，输出合并后的图片 batch。 |
| **Save Batch Folder** | `FishCustom/save` | 最多 8 路图片，每次执行保存到独立时间戳文件夹。支持 PNG/JPG、输出目录可选 output/temp/自定义。 |

---

## 安装

**方式一 — git clone（推荐）：**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/chydbd/ComfyUI-FishCustom-Nodes.git
```

**方式二 — 手动下载：** 下载本仓库放入 `ComfyUI/custom_nodes/ComfyUI-FishCustom-Nodes/`。

然后重启 ComfyUI（或 **Developer → Reload Custom Nodes**）。无额外依赖——仅使用 ComfyUI 自带的 `numpy` / `Pillow` / `torch`。

---

## 使用示例

### 词条管线

```
Static Tag (基础词条) ──┐
                        ├─► Concat ─► Tag Mutual Exclusion ─► Tag Blacklist ─► CLIP Text Encode
Random Tag (加权随机) ──┘          (解决互斥冲突)            (最终净化)
```

- **Random Tag** 按权重随机抽取；每行格式：`内容|权重,权重消耗`
- **Tag Mutual Exclusion** 每组互斥词条只保留一个（每组一行，成员逗号分隔，如 `smiling,angry,sad`）
- **Tag Blacklist** 删除不想要的词条（每行一个）

### 并行批量保存

```
KSampler 1 ─► VAEDecode ─┐
KSampler 2 ─► VAEDecode ─┼─► Save Batch Folder (images_0..images_7)
KSampler 3 ─► VAEDecode ─┤
...                       ┘
```

一次队列运行的所有图片会保存到同一时间戳文件夹（如 `output/batch_20260812_153012/`），按批归档、对比都方便。支持 PNG（含完整元数据）与 JPG（RGBA 自动白底合成）；保存位置可选 `output` / `temp` / 自定义（绝对路径或相对 ComfyUI 根目录的相对路径）。

### 多图批量采样（Batch Sampler）

一个 **Batch Sampler** 替代 N 条并列的 KSampler / VAEDecode 链路。`recipe` 每行一张图；各图的词条照常用 StaticTag / RandomTag / TagBlacklist 拼好，最后用 **Concat（`newline=True`）** 汇成 recipe：

```
StaticTag/Blacklist... → 第 1 图 prompt ─┐
StaticTag/RandomTag... → 第 2 图 prompt ─┼─► Concat(newline=True) ─► Batch Sampler(recipe) ─► Save Batch Folder
...                                      ┘
```

- `seed` / `denoise` / `latent_src` 为逗号列表，逐图取值，不足时最后一个值广播（`-1` = 随机 seed）。
- `latent_src` 逐图指定 latent 来源：`blank`（空白 latent）、`input`（外部 `latent` 端口）、`prev`（上一张输出）、`step:k`（第 k 张输出；可反向引用实现 B→A 图生图，节点内部按依赖排序执行，成环会报错）。
- 行内随机项：`{a|b|c}` 每次出现独立随机；`{name:a|b|c}` 整批只抽一次、共享结果。
- 可选 `template` 输入：模板中用 `{line}` 占位，recipe 每行只写变化部分。
- 输出为合并后的 IMAGE batch（`count` 为图片数，调试用），直接接 Save Batch Folder 即可全部保存。

---

## 许可证

MIT
