# ComfyUI-FishCustom-Nodes 🐟

**English** | [中文](README.md)

Custom nodes for ComfyUI: tag generation/filtering, logic routing, batch folder saving, and batch sampling.

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
| **Concat** | `FishCustom/utils` | Joins up to 10 STRING inputs with a configurable separator; `newline=True` joins with newlines, handy for building multi-line recipes. |
| **Batch Sampler** | `FishCustom/sample` | Replaces N parallel sampling chains: samples one image per recipe line with per-image seed / denoise / latent source, returns all images as one batch. |
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

### Multi-image batch sampling (Batch Sampler)

A single **Batch Sampler** replaces N parallel KSampler / VAEDecode chains. The `recipe` holds one prompt per line; build each image's tags as usual with StaticTag / RandomTag / TagBlacklist, then join them into the recipe with **Concat (`newline=True`)**:

```
StaticTag/Blacklist... → prompt 1 ─┐
StaticTag/RandomTag... → prompt 2 ─┼─► Concat(newline=True) ─► Batch Sampler(recipe) ─► Save Batch Folder
...                                ┘
```

- `seed` / `denoise` / `latent_src` are comma lists applied per image; the last value repeats when the list is shorter (`-1` = random seed).
- `latent_src` selects the latent source per image: `blank` (empty latent), `input` (the external `latent` port), `prev` (previous image's output), `step:k` (the k-th image's output; backward references such as B→A are supported — steps run in dependency order, cycles raise an error).
- Inline random items: `{a|b|c}` is drawn each time it appears; `{name:a|b|c}` is drawn once per batch and shared.
- Optional `template` input: use `{line}` as a placeholder and write only the varying part on each recipe line.
- Output is a merged IMAGE batch (`count` is the image count, for debugging); connect it directly to Save Batch Folder to save everything.

---

## License

MIT
