# ComfyUI-FishCustom-Nodes 🐟

[English](README_EN.md) | **中文**

ComfyUI 自定义节点：词条生成/过滤、配方（recipe）编排、逻辑路由、多图批量采样、批量分文件夹保存。

---

## 节点列表

| 节点 | 分类 | 说明 |
|---|---|---|
| **Static Tag** | `FishCustom/tag` | 输出固定词条，原样透传。 |
| **Random Tag** | `FishCustom/tag` | 加权随机词条，支持权重上限与三种模式（strict / relaxed / zero_allowed）。 |
| **Tag Blacklist** | `FishCustom/tag` | 黑名单删除词条，支持子串/精确匹配，可命中 `(tag:1.2)` 权重写法。 |
| **Tag Mutual Exclusion** | `FishCustom/tag` | 互斥词条过滤，每组最多保留一个（random / first / last）。 |
| **Tag Chain** | `FishCustom/tag` | 用「加词条 / 删词条」步骤逐行推导 prompt：第 1 行用 `base`，之后每行 `新增 \| 删除` 得到下一行；可用 `{r0}`…`{r7}` 注入外部随机词条。 |
| **Style Permute** | `FishCustom/tag` | 把风格词条展开为全部组合（combinations）或全排列（permutations），一行一张图，上限 2000 行。 |
| **Recipe Map** | `FishCustom/tag` | 给多行 recipe 逐行追加/前置文本：`each` 每行加同一段、`pairwise` 逐行一一对应、`by_index` 用 `行号:内容` 精确指定。 |
| **Text Analyzer** | `FishCustom/logic` | 关键词检测，输出选择器信号（INT）。 |
| **Smart Switch** | `FishCustom/logic` | 按选择器路由 10 路输入（懒求值，只计算激活分支）。 |
| **Concat** | `FishCustom/utils` | 合并最多 10 路文本输入，可自定义分隔符；`newline=True` 时用换行连接，适合拼多行 recipe。 |
| **Batch Sampler** | `FishCustom/sample` | 一个节点替代 N 条并列采样链：多行 recipe 逐行采样，支持逐图 seed / denoise / latent 来源；输出合并后的 IMAGE batch，以及逐图解析后的 prompt（`prompts`）。 |
| **Save Batch Folder** | `FishCustom/save` | 最多 8 路图片，每次执行存到独立时间戳文件夹；只接 1 张图时直接存成 `{prefix}_{时间戳}.{ext}`。支持 PNG/JPG 与可选输出目录，可选 `tags` 输入把 prompt 写进 PNG 元数据 / JPG 同名 `.txt`。 |

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

### 配方节点：Tag Chain / Style Permute / Recipe Map

「recipe」是「一行一张图」的多行 prompt 文本。这三个节点把词条编排成 recipe，输出都是 `recipe` + `count`，直接接 Batch Sampler。

**Tag Chain** —— 写一次基础 prompt，再用增量步骤描述之后每张图的差异：

```
base:  masterpiece, best quality, 1girl, solo, white background, looking at viewer
steps: smiling | looking at viewer
       blushing, happy
       2girls, yuri | 1girl, solo
```

第 1 行原样输出 `base`，之后每行在前面一行的基础上修改：`|` 左边是新增词条（前置添加），右边是删除词条（按子串匹配，与 Tag Blacklist 一致），整行没有 `|` 就只新增。上面这个例子产出 4 行 recipe（4 张图）。可选的 `r0`…`r7` 输入能把 Random Tag 之类的外部随机结果用 `{r0}` 占位注入 `base` 和 `steps`；不认识的 `{a|b|c}` 会留给 Batch Sampler 在采样时随机。

**Style Permute** —— 风格词条每行一个，自动展开：

```
styles: soft lighting
        rim lighting
        backlight
```

`combinations` 输出全部非空组合（7 行），`permutations` 输出全排列（6 行）；`joiner` 控制行内分隔符。

**Recipe Map** —— 对已有 recipe 逐行加工：

- `each`：每行加同一段文本（常用于统一追加质量词）
- `pairwise`：`extra` 与 recipe 行数一致，逐行一一对应
- `by_index`：`extra` 每行写成 `行号:内容`（行号从 1 开始），只改指定行

`mode` 决定追加还是前置（`append` / `prepend`）。

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
- 输出 `images` 为合并后的 IMAGE batch，`count` 为图片数（调试用），`prompts` 为逐图实际使用的 prompt（下文保存节点会用到）。

### 批量保存（Save Batch Folder）

```
KSampler 1 ─► VAEDecode ─┐
KSampler 2 ─► VAEDecode ─┼─► Save Batch Folder (images_0..images_7)
KSampler 3 ─► VAEDecode ─┤
...                       ┘
```

- 一次队列运行的所有图片会保存到同一时间戳文件夹（如 `output/batch_20260812_153012/`），按批归档、对比都方便；只接了 1 张图时不建文件夹，直接存成 `output/{prefix}_{YYYYMMDD_HHMMSS}.png`。
- 支持 PNG（含完整元数据）与 JPG（RGBA 自动白底合成，质量可调）；保存位置可选 `output` / `temp` / 自定义（绝对路径或相对 ComfyUI 根目录的相对路径）。
- 可选 `tags` 输入（通常接 Batch Sampler 的 `prompts`）：逐图写入实际 prompt。PNG 写进 `fish_tags` 文本块，在 ComfyUI 的图片信息面板里可见；JPG 不支持元数据，会写同名的 `.txt` 边车文件。

### 示例工作流

仓库自带 [`examples/tag_recipe_batch.json`](examples/tag_recipe_batch.json)：

```
Checkpoint ─┬─► Batch Sampler ─┬─ images ─► Save Batch Folder
Static Tag ─┴─► Tag Chain ─► Recipe Map ──┘
                                └─ prompts ─► tags
```

把 JSON 拖进 ComfyUI 即可加载（首次打开请把 checkpoint 换成自己有的模型）。图中另有一个被静音的 **Style Permute** 节点，取消静音就能换成用组合/排列生成 recipe。

---

## 许可证

MIT
