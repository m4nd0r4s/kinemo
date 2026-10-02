// WebSocket to the preview server (protocol: crates/kinemo-server/src/protocol.rs).
// JSON messages are dispatched by `type`; binary messages are frames.
"use strict";

import { emit, view } from "./state.js";

let socket = null;
let nextId = 1;

export function requestId() {
  return nextId++;
}

export function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
    return true;
  }
  return false;
}

export function connect() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.binaryType = "arraybuffer";
  socket.onopen = () => {
    view.connection.classList.add("online");
    emit("connected");
  };
  socket.onclose = () => {
    view.connection.classList.remove("online");
    socket = null;
    setTimeout(connect, 800);
  };
  socket.onmessage = (event) => {
    if (typeof event.data === "string") {
      const message = JSON.parse(event.data);
      emit(`message:${message.type}`, message);
    } else {
      emit("message:frame", event.data);
    }
  };
}
