//! Per-format video filter chains and codec arguments.

use crate::{EncoderOptions, Format};

/// Swscale flags for bit-exact, accurate colour conversion.
const SWS: &str = "bicubic+accurate_rnd+full_chroma_int+bitexact";

pub(crate) const VIDEO_IN: &str = "[0:v]";
pub(crate) const VIDEO_OUT: &str = "[vout]";

fn convert(pix_fmt: &str) -> String {
    format!("scale=flags={SWS}:out_color_matrix=bt709:out_range=tv,format={pix_fmt}")
}

fn alpha(opts: &EncoderOptions) -> bool {
    opts.transparent && opts.format.supports_alpha()
}

/// `-filter_complex` fragment turning `[0:v]` (rgba) into `[vout]`.
pub(crate) fn video_graph(opts: &EncoderOptions) -> String {
    let chain = match opts.format {
        // Frames arrive as yuv420p already (padded to even sizes by the caller).
        Format::Mp4 => "null".to_string(),
        Format::Webm => convert(if alpha(opts) { "yuva420p" } else { "yuv420p" }),
        Format::Mov => convert(if alpha(opts) { "yuva444p10le" } else { "yuv444p10le" }),
        Format::Gif => {
            let reserve = if opts.transparent { 1 } else { 0 };
            format!(
                "split[ka][kb];[ka]palettegen=stats_mode=full:reserve_transparent={reserve}[kp];\
                 [kb][kp]paletteuse=dither=sierra2_4a"
            )
        }
    };
    format!("{VIDEO_IN}{chain}{VIDEO_OUT}")
}

fn s(v: &[&str]) -> Vec<String> {
    v.iter().map(|x| x.to_string()).collect()
}

const BT709: &[&str] = &["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"];

/// Video codec + muxer arguments.
pub(crate) fn video_codec_args(opts: &EncoderOptions) -> Vec<String> {
    let mut a = Vec::new();
    match opts.format {
        Format::Mp4 => {
            let crf = opts.crf.unwrap_or(18).to_string();
            a.extend(s(&["-c:v", "libx264", "-preset", "medium", "-crf", &crf, "-pix_fmt", "yuv420p"]));
            // x264 output depends on its thread count; pin it so bytes do not vary by machine.
            a.extend(s(&["-threads", "4", "-x264-params", "threads=4:lookahead-threads=1:deterministic=1"]));
            a.extend(s(BT709));
            a.extend(s(&["-movflags", "+faststart"]));
        }
        Format::Webm => {
            let crf = opts.crf.unwrap_or(31).to_string();
            let pix = if alpha(opts) { "yuva420p" } else { "yuv420p" };
            a.extend(s(&["-c:v", "libvpx-vp9", "-crf", &crf, "-b:v", "0", "-pix_fmt", pix]));
            a.extend(s(&["-deadline", "good", "-cpu-used", "2", "-row-mt", "0", "-threads", "1"]));
            if alpha(opts) {
                a.extend(s(&["-auto-alt-ref", "0"]));
            }
            a.extend(s(BT709));
        }
        Format::Mov => {
            let pix = if alpha(opts) { "yuva444p10le" } else { "yuv444p10le" };
            a.extend(s(&["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", pix, "-vendor", "apl0"]));
            if alpha(opts) {
                a.extend(s(&["-alpha_bits", "16"]));
            }
            a.extend(s(&["-threads", "1"]));
            a.extend(s(BT709));
        }
        Format::Gif => {
            a.extend(s(&["-c:v", "gif", "-loop", "0", "-threads", "1"]));
        }
    }
    a
}

/// Audio codec arguments, or `None` when the format carries no audio.
pub(crate) fn audio_codec_args(format: Format) -> Option<Vec<String>> {
    match format {
        Format::Mp4 => Some(s(&["-c:a", "aac", "-b:a", "192k"])),
        Format::Webm => Some(s(&["-c:a", "libopus", "-b:a", "160k"])),
        Format::Mov => Some(s(&["-c:a", "pcm_s16le"])),
        Format::Gif => None,
    }
}

/// Muxer name passed to `-f` so the output does not depend on the file extension.
pub(crate) fn muxer(format: Format) -> &'static str {
    match format {
        Format::Mp4 => "mp4",
        Format::Webm => "webm",
        Format::Mov => "mov",
        Format::Gif => "gif",
    }
}

/// Frame rate as an exact rational string ("30", "30000/1001", ...).
pub(crate) fn fps_rational(fps: f64) -> String {
    if (fps - fps.round()).abs() < 1e-9 {
        return format!("{}", fps.round() as i64);
    }
    let ntsc = fps * 1001.0 / 1000.0;
    if (ntsc - ntsc.round()).abs() < 1e-6 {
        return format!("{}/1001", ntsc.round() as i64 * 1000);
    }
    let num = (fps * 1000.0).round() as i64;
    format!("{num}/1000")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fps_strings() {
        assert_eq!(fps_rational(30.0), "30");
        assert_eq!(fps_rational(29.97002997), "30000/1001");
        assert_eq!(fps_rational(23.976023976), "24000/1001");
        assert_eq!(fps_rational(12.5), "12500/1000");
    }
}
