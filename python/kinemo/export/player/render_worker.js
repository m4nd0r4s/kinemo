// The lesson's frames, drawn off the main thread so the answer controls stay responsive: the
// WebAssembly core (kinemo-web) turns the scene's IR and a time into RGBA pixels.
//
// Messages in: {type: "load", ir, baked, images: [{path, url}]}, {type: "frame", id, t, width,
// height}, {type: "set", signal, value}. Out: {type: "ready", duration} or {type: "error",
// message}, and {type: "frame", id, t, width, height, ms, pixels} (the buffer is transferred).
import init, { Player, add_image, bake } from "./pkg/kinemo_web.js";

let player = null;
let size = [0, 0];

async function load({ ir, baked, images }) {
  await init();
  bake(baked);
  for (const image of images) {
    const bytes = new Uint8Array(await (await fetch(image.url)).arrayBuffer());
    add_image(image.path, bytes);
  }
  player = new Player(ir, 2, 2);
  return player.duration();
}

function frame({ id, t, width, height }) {
  if (size[0] !== width || size[1] !== height) {
    player.resize(width, height);
    size = [width, height];
  }
  const start = performance.now();
  const rgba = player.render(t);
  const ms = performance.now() - start;
  const pixels = rgba.buffer.byteLength === rgba.length ? rgba.buffer : rgba.slice().buffer;
  self.postMessage({ type: "frame", id, t, width, height, ms, pixels }, [pixels]);
}

self.onmessage = async ({ data }) => {
  try {
    if (data.type === "load") self.postMessage({ type: "ready", duration: await load(data) });
    else if (data.type === "frame") frame(data);
    else if (data.type === "set") player.set_signal(data.signal, JSON.stringify(data.value));
  } catch (error) {
    self.postMessage({ type: "error", message: String(error && error.message ? error.message : error) });
  }
};
