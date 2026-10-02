//! Preview server for `kinemo dev`.
//!
//! Serves an embedded single-page UI over HTTP and answers frame and pick requests over
//! a WebSocket (`/ws`); the message format is documented in [`protocol`]. Frames are
//! rendered in Rust at draft quality and cached per (scene version, frame index); the
//! Python side only publishes scenes ([`PreviewServer::set_scene`]) and build errors.

pub mod frame_backend;
pub mod frame_cache;
mod frame_service;
mod http_routes;
mod overlay_service;
mod pick_service;
mod preview_server;
pub mod preview_state;
pub mod protocol;
mod websocket;

pub use preview_server::PreviewServer;
