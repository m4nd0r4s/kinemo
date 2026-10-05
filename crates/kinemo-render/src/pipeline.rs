//! Rendering and encoding at the same time: the frames of one batch are rendered in parallel
//! while a writer thread feeds the previous ones to ffmpeg, through a bounded channel so memory
//! stays bounded and the encoder always has work.

use std::ops::Range;
use std::sync::mpsc::sync_channel;

use kinemo_encode::{EncodeError, VideoEncoder};

use crate::renderer::RenderError;

/// Frames rendered together (in parallel) before they are handed to the writer.
pub(crate) const BATCH: usize = 32;

/// Renders frames `0..total` with `render_batch` (frames ready for the encoder, in order) and
/// encodes them with `encoder` on a writer thread. `progress(done, total)` follows the frames
/// handed to the writer.
pub(crate) fn render_and_encode(
    encoder: VideoEncoder,
    total: usize,
    render_batch: impl Fn(Range<usize>) -> Vec<Vec<u8>>,
    progress: &(dyn Fn(usize, usize) + Sync),
) -> Result<(), RenderError> {
    // Two batches in flight: one being encoded while the next is rendered.
    let (sender, receiver) = sync_channel::<Vec<u8>>(2 * BATCH);
    let writer = std::thread::spawn(move || -> Result<(), EncodeError> {
        let mut encoder = encoder;
        for frame in receiver {
            encoder.push_frame(&frame)?;
        }
        encoder.finish()
    });
    let mut done = 0;
    'batches: for start in (0..total).step_by(BATCH) {
        for frame in render_batch(start..(start + BATCH).min(total)) {
            // The writer stopped early (ffmpeg failed): its error is reported below.
            if sender.send(frame).is_err() {
                break 'batches;
            }
            done += 1;
            progress(done, total);
        }
    }
    drop(sender);
    writer.join().expect("encoder thread panicked")?;
    Ok(())
}
