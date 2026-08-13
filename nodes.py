import json
import os
import random
import re
import time

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

try:
    from comfy.cli_args import args
except ImportError:  # pragma: no cover - fallback when comfy module not importable
    args = None


class AnyType(str):
    """A wildcard type that matches any connection (credit: pythongosssss)."""

    def __ne__(self, __value: object) -> bool:
        return False


any_type = AnyType("*")


class FlexibleOptionalInputType(dict):
    """Makes flexible/dynamic input types for nodes with variable port counts.

    When ComfyUI asks for a key we don't have, we return the flexible type tuple
    so it accepts any connection type.
    """

    def __init__(self, _type, data=None):
        self._type = _type
        self._data = data
        if self._data is not None:
            for k, v in self._data.items():
                self[k] = v

    def __getitem__(self, key):
        if self._data is not None and key in self._data:
            return self._data[key]
        return (self._type,)

    def __contains__(self, key):
        return True


class StaticTag:
    """Outputs fixed text unchanged. Used for base tags that don't change."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Fixed text to output (e.g. masterpiece, best quality)"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "passthrough"
    CATEGORY = "FishCustom/tag"

    def passthrough(self, text):
        return (text,)


class RandomTag:
    """Weighted random tag selector with weight cap and three modes.

    Each line in `tags` is one random unit: "content|weight".
    Picks units by weight, accumulating total weight up to `weight_cap`.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tags": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "One unit per line. Format: tag_content|weight[,cap_cost]\n"
                               "e.g. raised_arms|5,2  (prob=5, cap=2)\n"
                               "     thumbs_up|3     (prob=3, cap=3)\n"
                               "     smiling         (prob=default, cap=default)"
                }),
                "count": ("INT", {
                    "default": 2, "min": 1, "max": 50, "step": 1,
                    "tooltip": "Maximum units to pick (weight cap may stop early)"
                }),
                "weight_cap": ("FLOAT", {
                    "default": 2.0, "min": 0.1, "max": 100.0, "step": 0.1,
                    "tooltip": "Cumulative weight cap for selected units"
                }),
                "mode": (["strict", "relaxed", "zero_allowed"], {
                    "default": "strict",
                    "tooltip": "strict=fill toward cap; relaxed=allow <cap no empty; zero_allowed=allow empty"
                }),
                "seed": ("INT", {
                    "default": 0, "min": 0, "max": 0xffffffffffffffff,
                    "control_after_generate": True,
                    "tooltip": "Random seed; auto-randomize after each generation"
                }),
                "default_weight": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 100.0, "step": 0.1,
                    "tooltip": "Default probability weight AND cap_cost for entries without explicit |"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "random_pick"
    CATEGORY = "FishCustom/tag"

    def _parse_tags(self, tags_text, default_weight):
        """Parse multiline tags text into [(content, weight, cap_cost), ...] list.

        Format per line:  tag_content|weight,cap_cost
        - weight: controls probability of being selected
        - cap_cost: how much this unit counts toward weight_cap
        - If only weight given (e.g. |3), cap_cost = weight
        - If no | at all, both use default_weight
        """
        units = []
        for line in tags_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                content, values_str = line.rsplit("|", 1)
                content = content.strip()
                values_str = values_str.strip()
                parts = [v.strip() for v in values_str.split(",")]
                try:
                    weight = float(parts[0])
                except (ValueError, IndexError):
                    weight = default_weight
                if len(parts) >= 2:
                    try:
                        cap_cost = float(parts[1])
                    except ValueError:
                        cap_cost = weight
                else:
                    cap_cost = weight
            else:
                content = line
                weight = default_weight
                cap_cost = default_weight
            if content and weight > 0:
                units.append((content, weight, cap_cost))
        return units

    def random_pick(self, tags, count, weight_cap, mode, seed, default_weight=1.0):
        units = self._parse_tags(tags, default_weight)
        if not units:
            return ("",)

        rng = random.Random(seed)
        selected = []
        total_cost = 0.0
        available = list(units)

        for _ in range(count):
            if not available:
                break
            if total_cost >= weight_cap:
                break

            # Weighted random selection by probability weight (u[1])
            weights = [u[1] for u in available]
            total = sum(weights)
            if total <= 0:
                break

            r = rng.random() * total
            cumulative = 0.0
            chosen_idx = 0
            for i, w in enumerate(weights):
                cumulative += w
                if r <= cumulative:
                    chosen_idx = i
                    break

            chosen = available.pop(chosen_idx)

            # If this unit's cap_cost would exceed remaining cap:
            if total_cost + chosen[2] > weight_cap:
                if mode == "strict":
                    # Try to find a lighter unit that fits
                    lighter = [u for u in available if total_cost + u[2] <= weight_cap]
                    if lighter:
                        chosen = lighter[0]
                        available.remove(chosen)
                        selected.append(chosen[0])
                        total_cost += chosen[2]
                        continue
                # strict (no replacement) / relaxed / zero_allowed → stop
                break

            selected.append(chosen[0])
            total_cost += chosen[2]

            # Relaxed / zero_allowed: random early stop within cap
            if mode in ("relaxed", "zero_allowed") and len(selected) < count:
                # Stop probability increases with each pick
                if rng.random() < 1.0 / (count - len(selected) + 2):
                    break

        # Mode checks for empty result
        if not selected:
            if mode == "zero_allowed":
                return ("",)
            if units:
                # relaxed / strict: pick the lowest cap_cost unit
                lightest = min(units, key=lambda u: u[2])
                selected = [lightest[0]]

        result = ", ".join(selected)
        return (result,)


class TextAnalyzer:
    """Detects keywords in input text and outputs a selector signal.

    Returns the original text unchanged (passthrough) plus an INT selector:
    0 = no keyword matched, 1-N = index of matched keyword (priority order).
    Matching is case-insensitive substring match.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Text to analyze (receives via wire)"
                }),
                "keywords": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "One keyword per line. First match wins."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("text_out", "selector")
    FUNCTION = "analyze"
    CATEGORY = "FishCustom/logic"

    def analyze(self, text, keywords):
        lines = [k.strip() for k in keywords.splitlines() if k.strip()]
        selector = 0
        text_lower = text.lower()
        for i, kw in enumerate(lines, start=1):
            if kw.lower() in text_lower:
                selector = i
                break
        return (text, selector)


SMART_SWITCH_CASES = 10


class SmartSwitch:
    """Routes one of N inputs to output based on INT selector.

    Uses lazy evaluation so only the active branch is computed.
    selector=0 -> case_0 (fallback when no match / no connection)
    selector=1 -> case_1, selector=2 -> case_2, etc.
    10 cases available (case_0 through case_9).
    """

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "selector": ("INT", {
                    "default": 0, "min": 0, "max": SMART_SWITCH_CASES - 1, "step": 1,
                    "tooltip": "0=case_0(fallback), 1=case_1, ... 9=case_9"
                }),
            },
            "optional": {},
        }
        for i in range(SMART_SWITCH_CASES):
            inputs["optional"][f"case_{i}"] = (any_type, {"lazy": True})
        return inputs

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("*",)
    FUNCTION = "switch"
    CATEGORY = "FishCustom/logic"

    def check_lazy_status(self, selector, **kwargs):
        key = f"case_{selector}"
        if key in kwargs and kwargs.get(key) is None:
            return [key]
        # Fallback: if selected case is not connected, request case_0
        if key not in kwargs:
            fallback = "case_0"
            if fallback in kwargs and kwargs.get(fallback) is None:
                return [fallback]
        return []

    def switch(self, selector, **kwargs):
        key = f"case_{selector}"
        result = kwargs.get(key)
        # If requested case is not connected, fall back to case_0
        if result is None and key not in kwargs:
            result = kwargs.get("case_0")
        return (result,)


CONCAT_INPUTS = 10


class Concat:
    """Joins multiple STRING inputs with a configurable separator.

    Skips empty strings and None values. Default separator is comma.
    10 inputs available (string_0 through string_9).
    """

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "separator": ("STRING", {
                    "default": ",",
                    "tooltip": "Separator between strings (e.g. ',' or ' ')"
                }),
            },
            "optional": {},
        }
        for i in range(CONCAT_INPUTS):
            inputs["optional"][f"string_{i}"] = ("STRING", {"forceInput": True})
        return inputs

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "concat"
    CATEGORY = "FishCustom/utils"

    def concat(self, separator=",", **kwargs):
        parts = []
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if val is not None and val.strip():
                parts.append(val.strip())
        result = separator.join(parts)
        return (result,)


_WEIGHTED_PAREN_RE = re.compile(r"^\((.*?)(?::[0-9.]+)?\)$")
_WEIGHTED_BARE_RE = re.compile(r"^(.+?):[0-9.]+$")


def _normalize_tag(tag):
    """Strip SD weight syntax so matching works across variants.

    (tag:1.2) -> tag,  (tag) -> tag,  tag:1.2 -> tag.  Plain tags pass through.
    """
    t = tag.strip()
    m = _WEIGHTED_PAREN_RE.match(t)
    if m:
        return m.group(1).strip()
    m = _WEIGHTED_BARE_RE.match(t)
    if m:
        return m.group(1).strip()
    return t


def _split_units(text):
    """Split a comma-separated tag string into trimmed units."""
    return [u.strip() for u in text.split(",") if u.strip()]


def _join_units(units):
    return ", ".join(units)


def _unit_matches_any(unit, entries, match_mode):
    """True if unit matches any entry under the given mode (case-insensitive).

    substring: entry (normalized) is a substring of the unit (normalized).
    exact:     unit (normalized) equals the entry (normalized).
    """
    norm = _normalize_tag(unit).lower()
    if not norm:
        return False
    for e in entries:
        e_norm = _normalize_tag(e).lower()
        if not e_norm:
            continue
        if match_mode == "exact":
            if norm == e_norm:
                return True
        elif e_norm in norm:
            return True
    return False


class TagBlacklist:
    """Removes blacklisted tags from a comma-separated tag string.

    One blacklist entry per line. substring mode also catches weighted
    variants like (tag:1.2) and compound tags like tag_face.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Comma-separated tags to filter (e.g. from RandomTag output)"
                }),
                "blacklist": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "One tag per line. Matching tags are removed from text."
                }),
                "match_mode": (["substring", "exact"], {
                    "default": "substring",
                    "tooltip": "substring=entry matches inside a tag, catches (tag:1.2) and tag_face; exact=normalized tag must equal entry"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "filter_tags"
    CATEGORY = "FishCustom/tag"

    def filter_tags(self, text, blacklist, match_mode="substring"):
        entries = [t.strip() for t in blacklist.splitlines() if t.strip()]
        if not entries or not text:
            return (text,)
        units = _split_units(text)
        kept = [u for u in units if not _unit_matches_any(u, entries, match_mode)]
        return (_join_units(kept),)


class TagMutualExclusion:
    """Keeps at most one tag per mutually-exclusive group.

    One group per line, members separated by commas:
        smiling,angry,sad
    If multiple members of the same group appear in text, all but one are
    removed. Groups are processed in order, top line first.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Comma-separated tags to filter (e.g. from RandomTag output)"
                }),
                "groups": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "One exclusive group per line, members comma-separated. e.g. smiling,angry,sad"
                }),
                "keep_mode": (["random", "first", "last"], {
                    "default": "random",
                    "tooltip": "Which member survives a conflict: random=one random member, first=earliest in text, last=latest"
                }),
                "seed": ("INT", {
                    "default": 0, "min": 0, "max": 0xffffffffffffffff,
                    "control_after_generate": True,
                    "tooltip": "Seed for random keep_mode; auto-randomize after each generation"
                }),
                "match_mode": (["substring", "exact"], {
                    "default": "substring",
                    "tooltip": "substring=entry matches inside a tag, catches (tag:1.2) and tag_face; exact=normalized tag must equal entry"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "filter_tags"
    CATEGORY = "FishCustom/tag"

    def filter_tags(self, text, groups, keep_mode="random", seed=0, match_mode="substring"):
        group_lines = [g.strip() for g in groups.splitlines() if g.strip()]
        if not group_lines or not text:
            return (text,)
        units = _split_units(text)
        rng = random.Random(seed)
        for line in group_lines:
            members = [m.strip() for m in line.split(",") if m.strip()]
            if not members:
                continue
            idxs = [i for i, u in enumerate(units) if _unit_matches_any(u, members, match_mode)]
            if len(idxs) < 2:
                continue
            if keep_mode == "first":
                keep = idxs[0]
            elif keep_mode == "last":
                keep = idxs[-1]
            else:
                keep = rng.choice(idxs)
            units = [u for i, u in enumerate(units) if i == keep or i not in idxs]
        return (_join_units(units),)


SAVE_BATCH_INPUTS = 8


class SaveBatchFolder:
    """Saves up to 8 IMAGE inputs into one unique folder per execution.

    All connected images (e.g. from multiple parallel samplers in one queue
    run) are written into a single timestamped subfolder under the output
    directory, so each batch of generated images gets its own folder.
    Files are named img_{port}_{seq}_.png / .jpg. Supports png (with full
    metadata) and jpg (quality-controlled, no metadata).
    """

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.temp_dir = folder_paths.get_temp_directory()
        self.type = "output"
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "folder_prefix": ("STRING", {
                    "default": "batch",
                    "tooltip": "Prefix for the new folder. A timestamp is appended: {prefix}_{YYYYMMDD_HHMMSS}"
                }),
                "save_location": (["output", "temp", "custom"], {
                    "default": "output",
                    "tooltip": "output=ComfyUI output dir (persistent); temp=ComfyUI temp dir (cleared on restart); custom=use custom_dir"
                }),
                "custom_dir": ("STRING", {
                    "default": "",
                    "tooltip": "Only used when save_location=custom. Absolute path, or relative to the ComfyUI root. Empty falls back to output. If the path is inside output/temp, preview still works."
                }),
                "format": (["png", "jpg"], {
                    "default": "png",
                    "tooltip": "png=lossless with full metadata; jpg=smaller, no metadata"
                }),
                "jpg_quality": ("INT", {
                    "default": 95, "min": 1, "max": 100, "step": 1,
                    "tooltip": "JPEG quality (1-100). Only used when format=jpg."
                }),
            },
            "optional": {},
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }
        for i in range(SAVE_BATCH_INPUTS):
            inputs["optional"][f"images_{i}"] = ("IMAGE",)
        return inputs

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "FishCustom/save"
    DESCRIPTION = "Saves all connected images into one unique folder per execution."

    def _make_folder(self, root_dir, base_subfolder, prefix):
        """Create a unique timestamped subfolder under root_dir/base_subfolder.

        Returns the subfolder path relative to root_dir (base_subfolder joined
        with the new folder name, forward-safe on all platforms).
        """
        base = re.sub(r'[\\/:*?"<>|]', "_", prefix.strip()) or "batch"
        ts = time.strftime("%Y%m%d_%H%M%S")
        folder = f"{base}_{ts}"
        n = 1
        while os.path.exists(os.path.join(root_dir, base_subfolder, folder)):
            n += 1
            folder = f"{base}_{ts}_{n}"
        os.makedirs(os.path.join(root_dir, base_subfolder, folder), exist_ok=True)
        return os.path.join(base_subfolder, folder) if base_subfolder else folder

    def _resolve_target(self, save_location, custom_dir):
        """Resolve (root_dir, type, base_subfolder) from save_location + custom_dir.

        - output -> ComfyUI output dir, type "output"
        - temp   -> ComfyUI temp dir,  type "temp"
        - custom -> custom_dir absolute, or relative to ComfyUI base_path.
          Empty custom_dir falls back to output. If the resolved custom dir
          lives inside output/temp, preview keeps working (relative subfolder
          + matching type); otherwise preview is unavailable (type "custom").
        """
        if save_location == "temp":
            return self.temp_dir, "temp", ""
        if save_location == "custom":
            custom = (custom_dir or "").strip()
            if custom:
                if not os.path.isabs(custom):
                    custom = os.path.normpath(os.path.join(folder_paths.base_path, custom))
                out = os.path.normpath(self.output_dir)
                tmp = os.path.normpath(self.temp_dir)
                try:
                    if os.path.commonpath([out, custom]) == out:
                        return out, "output", os.path.relpath(custom, out)
                    if os.path.commonpath([tmp, custom]) == tmp:
                        return tmp, "temp", os.path.relpath(custom, tmp)
                except ValueError:
                    pass  # different drives -> not inside output/temp
                return custom, "custom", ""
        return self.output_dir, "output", ""

    def save_images(self, folder_prefix="batch", save_location="output", custom_dir="",
                    format="png", jpg_quality=95,
                    prompt=None, extra_pnginfo=None, **kwargs):
        images = []
        for i in range(SAVE_BATCH_INPUTS):
            img = kwargs.get(f"images_{i}")
            if img is not None:
                images.append((i, img))
        if not images:
            return {"ui": {"images": []}}

        root_dir, self.type, base_subfolder = self._resolve_target(save_location, custom_dir)
        subfolder = self._make_folder(root_dir, base_subfolder, folder_prefix)
        full_folder = os.path.join(root_dir, subfolder)
        ext = "jpg" if format == "jpg" else "png"
        results = []

        for port, tensor in images:
            for batch_number, image in enumerate(tensor):
                i = 255. * image.cpu().numpy()
                img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

                metadata = None
                if format == "png" and not (args is not None and getattr(args, "disable_metadata", False)):
                    metadata = PngInfo()
                    if prompt is not None:
                        metadata.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo is not None:
                        for x in extra_pnginfo:
                            metadata.add_text(x, json.dumps(extra_pnginfo[x]))

                file = f"img_{port}_{batch_number:05}_.{ext}"
                if format == "jpg":
                    # JPEG has no alpha channel: composite RGBA onto white,
                    # convert any other non-RGB mode (L/P/CMYK) as well.
                    if img.mode == "RGBA":
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[-1])
                        img = bg
                    elif img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(os.path.join(full_folder, file), quality=jpg_quality)
                else:
                    img.save(os.path.join(full_folder, file), pnginfo=metadata, compress_level=self.compress_level)

                results.append({
                    "filename": file,
                    "subfolder": subfolder,
                    "type": self.type,
                })

        return {"ui": {"images": results}}


NODE_CLASS_MAPPINGS = {
    "StaticTag (ponytail)": StaticTag,
    "RandomTag (ponytail)": RandomTag,
    "TextAnalyzer (ponytail)": TextAnalyzer,
    "SmartSwitch (ponytail)": SmartSwitch,
    "Concat (ponytail)": Concat,
    "TagBlacklist (ponytail)": TagBlacklist,
    "TagMutualExclusion (ponytail)": TagMutualExclusion,
    "SaveBatchFolder (ponytail)": SaveBatchFolder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StaticTag (ponytail)": "Static Tag 🐟",
    "RandomTag (ponytail)": "Random Tag 🐟",
    "TextAnalyzer (ponytail)": "Text Analyzer 🐟",
    "SmartSwitch (ponytail)": "Smart Switch 🐟",
    "Concat (ponytail)": "Concat 🐟",
    "TagBlacklist (ponytail)": "Tag Blacklist 🐟",
    "TagMutualExclusion (ponytail)": "Tag Mutual Exclusion 🐟",
    "SaveBatchFolder (ponytail)": "Save Batch Folder 🐟",
}
