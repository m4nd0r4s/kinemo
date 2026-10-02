//! Rendering: scene at time t → display list → pixels → video.

mod frame;
pub mod geom;
pub mod inspect;
pub mod media;
pub mod raster;
mod movie;
mod renderer;
pub mod segments;
mod svg;

pub use frame::{display_list, morph_parts, FrameSize, MorphPart};
pub use movie::{render_movie, scene_starts, Transition};
pub use svg::{display_list_to_svg, render_svg};
pub use renderer::{render_frame, render_frame_with_backend, render_video, render_video_range, Quality, RenderError, RenderOptions};
