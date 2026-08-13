# ComfyUI-FishCustom-Nodes 🐟

Custom nodes for ComfyUI: tag generation/filtering, logic routing, and batch folder saving.

ComfyUI 自定义节点：词条生成/过滤、逻辑路由、批量分文件夹保存。

---

## Nodes / 节点列表

| Node / 节点 | Category / 分类 | Description / 说明 |
|---|---|---|
| **Static Tag** | `FishCustom/tag` | Outputs fixed text unchanged. 输出固定词条。 |
| **Random Tag** | `FishCustom/tag` | Weighted random tag picker with weight cap and 3 modes (strict / relaxed / zero_allowed). 加权随机词条，支持权重上限与三种模式。 |
| **Tag Blacklist** | `FishCustom/tag` | Removes blacklisted tags. substring / exact matching, handles `(tag:1.2)` weight syntax. 黑名单删除词条，支持子串/精确匹配与权重写法。 |
| **Tag Mutual Exclusion** | `FishCustom/tag` | Keeps at most one tag per exclusive group (random / first / last). 互斥词条过滤，每组最多保留一个。 |
| **Text Analyzer** | `FishCustom/logic` | Detects keywords and outputs an INT selector signal. 关键词检测，输出选择器信号。 |
| **Smart Switch** | `FishCustom/logic` | Routes one of 10 inputs to output based on selector (lazy evaluation). 按选择器路由 10 路输入，懒求值。 |
| **Concat** | `FishCustom/utils` | Joins up to 10 STRING inputs with a configurable separator. 多文本合并，可自定义分隔符。 |
| **Save Batch Folder** | `FishCustom/save` | Saves up to 8 image inputs into one unique timestamped folder per execution. PNG / JPG, save to output / temp / custom dir. 多路图片每次执行保存到独立文件夹，支持 PNG/JPG 与自定义目录。 |

---

## Installation / 安装

**Option 1 — git clone (recommended):**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/chydbd/ComfyUI-FishCustom-Nodes.git
```

**Option 2 — manual:** download the repository and place it in `ComfyUI/custom_nodes/ComfyUI-FishCustom-Nodes`.

Then restart ComfyUI (or **Developer → Reload Custom Nodes**). No extra dependencies — only `numpy` / `Pillow` / `torch`, which ComfyUI already requires.

克隆到 `ComfyUI/custom_nodes/` 下，重启 ComfyUI（或 Developer → Reload Custom Nodes）即可。无额外依赖。

---

## Usage Examples / 使用示例

### Tag pipeline / 词条管线

```
Static Tag (base tags) ──┐
                         ├─► Concat ─► Tag Mutual Exclusion ─► Tag Blacklist ─► CLIP Text Encode
Random Tag (weighted) ───┘          (resolve conflicts)       (final cleanup)
```

- **Random Tag** picks units by weight; lines format: `content|weight,cap_cost`
- **Tag Mutual Exclusion** keeps only one member per group (groups are one per line, members comma-separated: `smiling,angry,sad`)
- **Tag Blacklist** removes unwanted tags (one per line)

### Parallel batch saving / 并行批量保存

```
KSampler 1 ─► VAEDecode ─┐
KSampler 2 ─► VAEDecode ─┼─► Save Batch Folder (images_0..images_7)
KSampler 3 ─► VAEDecode ─┤
...                       ┘
```

All images from one queue run land in a single timestamped folder like `output/batch_20260812_153012/`, so every batch is easy to archive and compare. Supports `png` (with full metadata) and `jpg` (RGBA auto-composited onto white); save location selectable: `output` / `temp` / `custom` (absolute path or relative to ComfyUI root).

一次队列运行的所有图会保存到同一时间戳文件夹（如 `output/batch_20260812_153012/`），方便按批归档对比。支持 PNG（含完整元数据）与 JPG（RGBA 自动白底合成）；保存位置可选 output / temp / 自定义目录。

---

## License / 许可证

MIT
