# ComfyUI-FishCustom-Nodes 🐟

**English** | [中文](README.md)

Custom nodes for ComfyUI: tag generation/filtering, logic routing, and batch folder saving.

---

## Nodes

| Node | Category | Description |
|---|---|---|
| **Static Tag** | `FishCustom/tag` | Outputs fixed text unchanged. |
| **Random Tag** | `FishCustom/tag` | Weighted random tag picker with weight cap and 3 modes (strict / relaxed / zero_allowed). |
| **Tag Blacklist** | `FishCustom/tag` | Removes blacklisted tags. substring / exact matching, handles `(tag:1.2)` weight syntax. |
| **Tag Mutual Exclusion** | `FishCustom/tag` | Keeps at most one tag per exclusive group (random / first / last). |
| **Text Analyzer** | `FishCustom/logic` | Detects keywords and outputs an INT selector signal. |
| **Smart Switch** | `FishCustom/logic` | Routes one of 10 inputs to output based on selector (lazy evaluation). |
| **Concat** | `FishCustom/utils` | Joins up to 10 STRING inputs with a configurable separator. |
| **Save Batch Folder** | `FishCustom/save` | Saves up to 8 image inputs into one unique timestamped folder per execution. PNG / JPG, save to output / temp / custom dir. |

---

## Installation

**Option 1 — git clone (recommended):**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/chydbd/ComfyUI-FishCustom-Nodes.git
```

**Option 2 — manual:** download the repository and place it in `ComfyUI/custom_nodes/ComfyUI-FishCustom-Nodes/`.

Then restart ComfyUI (or **Developer → Reload Custom Nodes**). No extra dependencies — only `numpy` / `Pillow` / `torch`, which ComfyUI already requires.

---

## Usage Examples

### Tag pipeline

```
Static Tag (base tags) ──┐
                         ├─► Concat ─► Tag Mutual Exclusion ─► Tag Blacklist ─► CLIP Text Encode
Random Tag (weighted) ───┘          (resolve conflicts)       (final cleanup)
```

- **Random Tag** picks units by weight; lines format: `content|weight,cap_cost`
- **Tag Mutual Exclusion** keeps only one member per group (groups are one per line, members comma-separated: `smiling,angry,sad`)
- **Tag Blacklist** removes unwanted tags (one per line)

### Parallel batch saving

```
KSampler 1 ─► VAEDecode ─┐
KSampler 2 ─► VAEDecode ─┼─► Save Batch Folder (images_0..images_7)
KSampler 3 ─► VAEDecode ─┤
...                       ┘
```

All images from one queue run land in a single timestamped folder like `output/batch_20260812_153012/`, so every batch is easy to archive and compare. Supports `png` (with full metadata) and `jpg` (RGBA auto-composited onto white); save location selectable: `output` / `temp` / `custom` (absolute path or relative to ComfyUI root).

---

## License

MIT
