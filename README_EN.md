# ComfyUI-FishCustom-Nodes 🐟

**English** | [中文](README.md)

Custom nodes for ComfyUI: tag generation/filtering, recipe building, logic routing, multi-image batch sampling, and batch folder saving.

---

## Nodes

| Node | Category | Description |
|---|---|---|
| **Static Tag** | `FishCustom/tag` | Outputs fixed text unchanged. |
| **Random Tag** | `FishCustom/tag` | Weighted random tag picker with weight cap and 3 modes (strict / relaxed / zero_allowed). |
| **Tag Blacklist** | `FishCustom/tag` | Removes blacklisted tags. substring / exact matching, handles `(tag:1.2)` weight syntax. |
| **Tag Mutual Exclusion** | `FishCustom/tag` | Keeps at most one tag per exclusive group (random / first / last). |
| **Tag Chain** | `FishCustom/tag` | Derives one prompt per step from add/remove lines: line 1 is `base`, each following line is `added \| removed`. `{r0}`…`{r7}` inject external tag inputs. |
| **Style Permute** | `FishCustom/tag` | Expands style tags into every combination or permutation, one image per line (2000-line cap). |
| **Recipe Map** | `FishCustom/tag` | Appends/prepends text to recipe lines: `each` (same text everywhere), `pairwise` (1:1 with the recipe), `by_index` (`line:content`). |
| **Text Analyzer** | `FishCustom/logic` | Detects keywords and outputs an INT selector signal. |
| **Smart Switch** | `FishCustom/logic` | Routes one of 10 inputs to output based on selector (lazy evaluation). |
| **Concat** | `FishCustom/utils` | Joins up to 10 STRING inputs with a configurable separator; `newline=True` joins with newlines, handy for building multi-line recipes. |
| **Batch Sampler** | `FishCustom/sample` | Replaces N parallel sampling chains: samples one image per recipe line with per-image seed / denoise / latent source; returns one IMAGE batch plus the resolved prompt per image (`prompts`). |
| **Save Batch Folder** | `FishCustom/save` | Saves up to 8 image inputs into one unique timestamped folder per execution; with a single image it saves `{prefix}_{timestamp}.{ext}` directly. PNG / JPG, output / temp / custom dir, optional `tags` input stored as PNG metadata or a `.txt` sidecar. |

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

### Recipe nodes: Tag Chain / Style Permute / Recipe Map

A *recipe* is multi-line prompt text where every line produces one image. These three nodes build recipes and all output `recipe` + `count`, ready for Batch Sampler.

**Tag Chain** — write the base prompt once, then describe each following image as a delta:

```
base:  masterpiece, best quality, 1girl, solo, white background, looking at viewer
steps: smiling | looking at viewer
       blushing, happy
       2girls, yuri | 1girl, solo
```

Line 1 is `base` unchanged. Every following line is applied on top of the previous one: tags left of `|` are prepended, tags right of `|` are removed by substring match (same semantics as Tag Blacklist). A line without `|` only adds tags. The example above yields a 4-line recipe (4 images). The optional `r0`…`r7` inputs let you inject external random results (e.g. Random Tag) through `{r0}` placeholders in `base` and `steps`; anything else that looks like `{a|b|c}` is left for Batch Sampler to resolve at sampling time.

**Style Permute** — one style tag per line, expanded automatically:

```
styles: soft lighting
        rim lighting
        backlight
```

`combinations` emits all non-empty combinations (7 lines), `permutations` emits every full ordering (6 lines); `joiner` sets the in-line separator.

**Recipe Map** — post-process an existing recipe line by line:

- `each`: the same text is added to every line (handy for global quality tags)
- `pairwise`: `extra` has one line per recipe line, matched 1:1
- `by_index`: each `extra` line is `index:content` (1-based), so only those lines change

`mode` chooses `append` or `prepend`.

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
- Outputs: `images` (one merged IMAGE batch), `count` (image count, for debugging) and `prompts` (the prompt actually used for each image — see the save node below).

### Batch folder saving (Save Batch Folder)

```
KSampler 1 ─► VAEDecode ─┐
KSampler 2 ─► VAEDecode ─┼─► Save Batch Folder (images_0..images_7)
KSampler 3 ─► VAEDecode ─┤
...                       ┘
```

- All images from one queue run land in a single timestamped folder like `output/batch_20260812_153012/`, so every batch is easy to archive and compare. With exactly one connected image no folder is created: the file is saved as `output/{prefix}_{YYYYMMDD_HHMMSS}.{ext}`.
- Supports `png` (with full metadata) and `jpg` (RGBA auto-composited onto white, quality adjustable); save location selectable: `output` / `temp` / `custom` (absolute path or relative to ComfyUI root).
- Optional `tags` input (usually Batch Sampler's `prompts`): writes the resolved prompt for each image. PNG stores it in a `fish_tags` text chunk, visible in ComfyUI's image info panel; JPG has no metadata, so a same-name `.txt` sidecar is written instead.

### Example workflow

The repo ships [`examples/tag_recipe_batch.json`](examples/tag_recipe_batch.json):

```
Checkpoint ─┬─► Batch Sampler ─┬─ images ─► Save Batch Folder
Static Tag ─┴─► Tag Chain ─► Recipe Map ──┘
                                └─ prompts ─► tags
```

Drag the JSON into ComfyUI to load it (pick one of your own checkpoints on first open). A muted **Style Permute** node is included as well — unmute it to build the recipe from combinations/permutations instead.

---

## License

MIT
