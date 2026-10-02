<script lang="ts">
  // The four phases from a scene function to frames, in order, with the code that runs each.
  import type { Run } from "$lib/site-data";
  import Terminal from "./Terminal.svelte";

  let { timeline }: { timeline: Run } = $props();

  const phases = [
    {
      name: "Build",
      text: "Python runs your scene function once. <code>s.play</code> and <code>s.wait</code> move a cursor; objects, signals and animations are recorded, not drawn.",
      where: "python/kinemo",
    },
    {
      name: "Resolve",
      text: "Events and handlers (<code>k.when</code>, <code>s.wait_for</code>, simulations) are settled to a fixed point, then visual lints sample the result.",
      where: "kinemo-resolve",
    },
    {
      name: "Evaluate",
      text: "Any instant, on demand: timelines and easing, traced expressions, constraint layout, shaped text, LaTeX through typst.",
      where: "kinemo-eval, kinemo-layout, kinemo-text, kinemo-math",
    },
    {
      name: "Render",
      text: "A display list rasterized by tiny-skia (Vello on the GPU for the preview), encoded by ffmpeg to MP4, WebM, MOV or GIF.",
      where: "kinemo-render, kinemo-encode",
    },
  ];
</script>

<section class="band model" id="model">
  <div class="band-head">
    <h2>One build, then any frame</h2>
    <p>
      The scene function is not a render loop. It runs once and produces data: a serializable scene
      of signals with timelines. Everything after that is native code reading that data.
    </p>
  </div>
  <ol class="pipeline">
    {#each phases as phase (phase.name)}
      <li>
        <h3>{phase.name}</h3>
        <p>{@html phase.text}</p>
        <p class="where">{phase.where}</p>
      </li>
    {/each}
  </ol>
  <div class="split">
    <div class="prose">
      <h3>What that buys you</h3>
      <p>
        <strong>Scrubbing is free.</strong> The preview asks the Rust server for the frame at
        <code>t</code>; Python is not involved until you save.
      </p>
      <p>
        <strong>Lambdas are compiled, not called.</strong>
        <code>{'k.Text(lambda: f"{x():.1f}")'}</code> and <code>.map(...)</code> are traced once into
        native expressions. Opaque Python is allowed, explicitly, through <code>k.python(fn)</code>.
      </p>
      <p>
        <strong>Reproducible to the byte.</strong> The CPU renderer is the reference: the golden frames
        in the test suite are compared byte for byte, and video uses bitexact encoder flags.
      </p>
    </div>
    <Terminal run={timeline} title="The timeline, without rendering" />
  </div>
</section>
