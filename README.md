# ComfyUI-FishCustom-Nodes 🐟

[English](README_EN.md) | **中文**

ComfyUI 自定义节点：词条生成/过滤、逻辑路由、批量分文件夹保存。

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
| **Concat** | `FishCustom/utils` | 合并最多 10 路文本输入，可自定义分隔符。 |
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

---

## 许可证

MIT
