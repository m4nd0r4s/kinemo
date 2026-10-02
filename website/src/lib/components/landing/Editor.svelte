<script lang="ts">
  // The preview that edits code: real screenshots and the line its engine rewrote.
  import { base } from "$app/paths";
  import type { SiteData } from "$lib/site-data";

  let { edit, example }: { edit: SiteData["edit"]; example: string } = $props();
</script>

<section class="band" id="editor">
  <div class="band-head">
    <h2>Edit the code from the preview</h2>
    <p>
      <code>kinemo dev scene.py</code> opens a browser preview with hot reload. Click an object and
      every prop says where it came from: the line that wrote it, or <em>default</em>. Literals are
      editable with a widget for their type, and the edit goes back to your file.
    </p>
  </div>
  <figure class="screenshot">
    <img
      src="{base}/img/editor-inspector.png"
      width="1600"
      height="1000"
      loading="lazy"
      alt="The kinemo dev preview: the outliner, the frame of a tangent sliding on a curve with the dot selected, the inspector listing the dot's props with their source lines, and the timeline below."
    />
  </figure>
  <div class="split">
    <div class="prose">
      <ul class="facts">
        <li>Drag a number and the scene rebuilds from the edited text as you move; the file is written once, when you let go.</li>
        <li>Selects for enumerations, a palette for colors (written as <code>k.RED</code>), two fields for points, the <code>k.ease</code> curves for easings.</li>
        <li>Only the literal's characters change. Formatting and comments stay yours, and a value your code computes is shown, not overwritten.</li>
        <li>Drag the selected object on the frame to rewrite the position that places it.</li>
      </ul>
    </div>
    <figure class="diff" aria-label="The change the preview made">
      <figcaption>examples/{example}.py, line {edit.line}, after dragging the dot's radius</figcaption>
      <pre><code><span class="del">-{edit.before}</span><span class="add">+{edit.after}</span></code></pre>
    </figure>
  </div>
  <figure class="screenshot">
    <img
      src="{base}/img/editor-bar.png"
      width="1600"
      height="1000"
      loading="lazy"
      alt="The preview with a timeline bar selected: the inspector shows the code of the play call, the arguments of the animation and of the play call, each editable."
    />
    <figcaption>
      Click a timeline bar for the arguments of its call and of the <code>s.play</code> that scheduled
      it, including the ones it leaves out, with their defaults.
    </figcaption>
  </figure>
</section>
