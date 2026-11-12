// H3 动作迁移预处理: grey out the face-blur level and detector while the face-blur
// switch is off, and show the blurred preview video of the block on the node.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE = "FeiHouEasyH3RHMotionPreprocess";
const TOGGLE = "face_blur_on";
const DEPENDENT = ["face_blur", "face_detector"];

function sync(node) {
  const toggle = node.widgets?.find((w) => w.name === TOGGLE);
  if (!toggle) return;
  const off = !toggle.value;
  for (const name of DEPENDENT) {
    const widget = node.widgets.find((w) => w.name === name);
    if (!widget) continue;
    widget.disabled = off;
    widget.options = widget.options || {};
    widget.options.disabled = off;
  }
  node.setDirtyCanvas?.(true, true);
}

function watch(node) {
  const toggle = node.widgets?.find((w) => w.name === TOGGLE);
  if (!toggle || toggle.__h3PreprocessWatched) return;
  toggle.__h3PreprocessWatched = true;
  const callback = toggle.callback;
  toggle.callback = function (...args) {
    const result = callback?.apply(this, args);
    sync(node);
    return result;
  };
}

function previewWidget(node) {
  if (node.__h3Preview) return node.__h3Preview;
  if (typeof document === "undefined" || typeof node.addDOMWidget !== "function") return null;
  // The box fills exactly the height the node gives the widget; the video takes
  // what is left under the summary and is letterboxed inside it (never overflows).
  const box = document.createElement("div");
  box.style.cssText = "display:flex;flex-direction:column;gap:4px;width:100%;height:100%;box-sizing:border-box;overflow:hidden;";
  const label = document.createElement("div");
  label.style.cssText = "flex:0 0 auto;height:30px;overflow:hidden;font-size:11px;line-height:15px;color:var(--descrip-text,#aaa);white-space:normal;display:none;";
  const video = document.createElement("video");
  video.controls = true;
  video.loop = true;
  video.muted = true;
  video.playsInline = true;
  video.style.cssText = "flex:1 1 auto;min-height:0;width:100%;height:100%;object-fit:contain;background:#000;border-radius:4px;display:none;";
  box.append(label, video);
  const preview = { label, video };
  // Height this widget wants at the node's current width: the video at its own aspect ratio plus the summary.
  const wanted = () => {
    const labelHeight = label.style.display === "none" ? 0 : 34;   // two lines of summary + gap
    if (video.style.display === "none") return labelHeight;
    const width = Math.max(120, (node.size?.[0] || 320) - 20);
    const ratio = video.videoWidth ? video.videoHeight / video.videoWidth : 16 / 9;
    return labelHeight + Math.round(Math.min(900, width * ratio));
  };
  const widget = node.addDOMWidget("blur_preview", "blur_preview", box, {
    serialize: false, hideOnZoom: false,
    getMinHeight: () => wanted(), getMaxHeight: () => wanted(),
  });
  widget.computeSize = (width) => [width, wanted()];
  preview.widget = widget;
  preview.fit = () => fitNode(node);
  video.addEventListener("loadedmetadata", preview.fit);
  node.__h3Preview = preview;
  return preview;
}

// Grow or shrink the node to the widgets' height, keeping the width the user set.
function fitNode(node) {
  setTimeout(() => {
    const size = node.computeSize?.([node.size[0], node.size[1]]);
    if (size) node.setSize([node.size[0], size[1]]);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
  }, 0);
}

function showPreview(node, info) {
  const preview = previewWidget(node);
  if (!preview || !info) return;
  preview.label.textContent = info.summary || "";
  preview.label.style.display = info.summary ? "block" : "none";
  if (!info.filename) {
    preview.video.pause?.();
    preview.video.removeAttribute("src");
    preview.video.style.display = "none";
  } else {
    const query = new URLSearchParams({ filename: info.filename, subfolder: info.subfolder || "",
      type: info.type || "temp", t: String(Date.now()) });
    preview.video.src = api.apiURL(`/view?${query}`);
    preview.video.style.display = "block";
    preview.video.play?.().catch(() => {});
  }
  preview.fit();
}

app.registerExtension({
  name: "FeiHou.EasyH3RH.MotionPreprocess",
  // RH change --start--
  rh: {
    type: "nodes",
    nodes: ["FeiHouEasyH3RHMotionPreprocess"],
  },
  // RH change --end--
  setup() {
    api.addEventListener("executed", (event) => {
      const info = event?.detail?.output?.feihou_rh_preprocess?.[0];
      if (!info) return;
      const node = app.graph?.getNodeById?.(event?.detail?.display_node ?? event?.detail?.node);
      if (node?.type === NODE) showPreview(node, info);
    });
  },
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE) return;
    const created = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = created?.apply(this, arguments);
      watch(this);
      sync(this);
      previewWidget(this);
      return result;
    };
    // Dragging the node wider or narrower keeps the preview at the video's aspect ratio.
    const resized = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
      const result = resized?.apply(this, arguments);
      const video = this.__h3Preview?.video;
      const width = Math.round(size?.[0] ?? this.size?.[0] ?? 0);
      if (video && video.style.display !== "none" && width && width !== this.__h3FitWidth) {
        this.__h3FitWidth = width;   // fitting keeps the width, so it does not loop
        fitNode(this);
      }
      return result;
    };
    const configure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = configure?.apply(this, arguments);
      watch(this);
      sync(this);
      // Some frontends re-apply widgets_values after onConfigure.
      setTimeout(() => sync(this), 0);
      return result;
    };
  },
});
