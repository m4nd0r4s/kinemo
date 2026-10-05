//! Rendering: scene at time t → display list → pixels → video.

mod frame;
pub mod geom;
pub mod inspect;
pub mod media;
pub mod raster;
mod movie;
mod pipeline;
mod renderer;
pub mod segments;
pub mod sheet;
mod svg;

pub use frame::{display_list, display_list_indexed, display_list_with, morph_parts, FrameSize, MorphPart};
pub use movie::{render_movie, scene_starts, Transition};
pub use svg::{display_list_to_svg, render_svg};
pub use renderer::{render_frame, render_frame_indexed, render_frame_with_backend, render_png_frames, render_video, render_video_range, Quality, RenderError, RenderOptions};
