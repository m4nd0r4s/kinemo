//! The quiz camera: while a question's quiz stretch plays, the scene shrinks into the part of
//! the frame its band leaves free (and grows back as the band leaves), so a scene can use the
//! whole frame and still never sit under the band.

use kurbo::{Affine, Vec2};

use kinemo_ir::{ObjectId, Quiz, QuizSide, Scene, QUIZ_INTRO, QUIZ_OUTRO};

use crate::raster::DrawItem;

use super::FrameSize;

/// Room kept between the band and the shrunk scene, in scene units.
const GAP: f64 = 0.3;

/// The quiz stretch playing at `t`, and how far in its camera is (0 to 1, eased).
fn active(scene: &Scene, t: f64) -> Option<(&Quiz, f64)> {
    let quiz = scene.questions.iter().filter_map(|q| q.quiz.as_ref()).find(|z| z.t0 <= t && t < z.t1)?;
    let into = ((t - quiz.t0) / QUIZ_INTRO).min((quiz.t1 - t) / QUIZ_OUTRO).clamp(0.0, 1.0);
    Some((quiz, into * into * (3.0 - 2.0 * into)))
}

/// The scene-unit transform (a scale, then a move) that fits what the scene shows into what the
/// band leaves free; never larger than it is.
fn fit(scene: &Scene, quiz: &Quiz) -> (f64, Vec2) {
    let (fw, fh) = (scene.config.frame_w, scene.config.frame_h);
    let [left, bottom, right, top] = quiz.rect;
    let (x0, y0, x1, y1) = match quiz.at {
        QuizSide::Bottom => (-fw / 2.0, top + GAP, fw / 2.0, fh / 2.0),
        QuizSide::Top => (-fw / 2.0, -fh / 2.0, fw / 2.0, bottom - GAP),
        QuizSide::Left => (right + GAP, -fh / 2.0, fw / 2.0, fh / 2.0),
        QuizSide::Right => (-fw / 2.0, -fh / 2.0, left - GAP, fh / 2.0),
    };
    let [c0, d0, c1, d1] = quiz.content;
    let (c0, d0, c1, d1) = if c1 > c0 && d1 > d0 { (c0, d0, c1, d1) } else { (-fw / 2.0, -fh / 2.0, fw / 2.0, fh / 2.0) };
    let scale = ((x1 - x0) / (c1 - c0)).min((y1 - y0) / (d1 - d0)).clamp(0.1, 1.0);
    // The content's center lands on the free part's center.
    let shift = Vec2::new((x0 + x1) / 2.0, (y0 + y1) / 2.0) - Vec2::new((c0 + c1) / 2.0, (d0 + d1) / 2.0) * scale;
    (scale, shift)
}

/// The pixel transform for the scene at `t` (outside a quiz stretch, none), and the objects
/// of the band, which it leaves alone.
pub(crate) fn quiz_camera(scene: &Scene, t: f64, size: FrameSize) -> Option<(Affine, f64, [ObjectId; 2])> {
    let (quiz, amount) = active(scene, t)?;
    if amount <= 0.0 {
        return None;
    }
    let (scale, shift) = fit(scene, quiz);
    let k = 1.0 + (scale - 1.0) * amount;
    let units = Affine::translate(shift * amount) * Affine::scale(k);
    let pixels = size.pixel_affine(scene);
    Some((pixels * units * pixels.inverse(), k, quiz.objects))
}

/// Moves and scales one item by the camera (`k`: its scale, for widths and radii).
pub(crate) fn transform_item(item: &mut DrawItem, camera: Affine, k: f64) {
    item.path = camera * item.path.clone();
    if let Some(clip) = item.clip.as_mut() {
        *clip = camera * clip.clone();
    }
    if let Some(stroke) = item.stroke.as_mut() {
        stroke.width *= k;
        if let Some(dash) = stroke.dash.as_mut() {
            dash.iter_mut().for_each(|d| *d *= k);
        }
    }
    if let Some(image) = item.image.as_mut() {
        image.transform = camera * image.transform;
    }
    if let Some(dots) = item.dots.as_mut() {
        for (center, radius) in dots.centers.iter_mut().zip(dots.radii.iter_mut()) {
            let p = camera * kurbo::Point::new(center[0] as f64, center[1] as f64);
            *center = [p.x as f32, p.y as f32];
            *radius *= k as f32;
        }
    }
    if let Some(glow) = item.glow.as_mut() {
        glow.radius *= k;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kinemo_ir::{Answer, Question, SceneConfig, Span};

    fn scene_with(at: QuizSide, rect: [f64; 4]) -> Scene {
        let mut scene = Scene::new(SceneConfig::default());
        scene.questions.push(Question {
            id: "q1".into(),
            t: 1.0,
            prompt: "?".into(),
            answer: Answer::Text { correct: vec!["x".into()] },
            signal: None,
            default: serde_json::Value::Null,
            branches: vec![],
            resume: 5.0,
            quiz: Some(Quiz { t0: 1.0, reveal: 3.0, t1: 5.0, at, rect, content: [0.0; 4], objects: [10, 20] }),
            span: Span::default(),
        });
        scene
    }

    #[test]
    fn the_scene_fits_beside_a_side_band_and_eases_in_and_out() {
        let scene = scene_with(QuizSide::Right, [3.0, -3.0, 7.5, 3.0]);
        let size = FrameSize { width: 1600, height: 900 };
        assert!(quiz_camera(&scene, 0.5, size).is_none());
        let (_, k, objects) = quiz_camera(&scene, 3.0, size).unwrap();
        // The free part is 16/2 + 3 - 0.3 = 10.7 units wide out of 16.
        assert!((k - 10.7 / 16.0).abs() < 1e-9 && objects == [10, 20]);
        let (_, halfway, _) = quiz_camera(&scene, 1.25, size).unwrap();
        assert!(halfway > k && halfway < 1.0);
        assert!(quiz_camera(&scene, 5.0, size).is_none());
    }

    #[test]
    fn content_smaller_than_the_frame_shrinks_less() {
        let mut scene = scene_with(QuizSide::Bottom, [-5.0, -4.5, 5.0, -1.5]);
        scene.questions[0].quiz.as_mut().unwrap().content = [-6.0, -3.0, 6.0, 4.0];
        let size = FrameSize { width: 1600, height: 900 };
        let (camera, k, _) = quiz_camera(&scene, 3.0, size).unwrap();
        // Free: y from -1.2 to 4.5 (5.7 tall), content 7 tall; width is no limit.
        assert!((k - 5.7 / 7.0).abs() < 1e-9);
        let pixels = size.pixel_affine(&scene);
        let bottom = pixels.inverse() * (camera * (pixels * kurbo::Point::new(0.0, -3.0)));
        assert!((bottom.y - (-1.2)).abs() < 1e-9, "the content's bottom sits just above the band");
    }

    #[test]
    fn under_a_bottom_band_the_frame_shrinks_into_the_top() {
        let scene = scene_with(QuizSide::Bottom, [-5.0, -4.5, 5.0, -1.5]);
        let size = FrameSize { width: 1600, height: 900 };
        let (camera, k, _) = quiz_camera(&scene, 3.0, size).unwrap();
        assert!((k - (4.5 + 1.5 - 0.3) / 9.0).abs() < 1e-9);
        // The frame's bottom edge lands just above the band.
        let pixels = size.pixel_affine(&scene);
        let edge = pixels.inverse() * (camera * (pixels * kurbo::Point::new(0.0, -4.5)));
        assert!((edge.y - (-1.5 + 0.3)).abs() < 1e-9);
    }
}
