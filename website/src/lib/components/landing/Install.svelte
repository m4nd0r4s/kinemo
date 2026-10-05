<script lang="ts">
  // Installing kinemo: a real sequence of steps, so they are numbered.
  import { base } from "$app/paths";

  let { install }: { install: { pip: string; start: string; run: string; source: string } } = $props();
</script>

<section class="band" id="install">
  <div class="band-head">
    <h2>Install</h2>
    <p>Wheels for Linux, macOS and Windows, Python 3.11 or newer. Video output needs <code>ffmpeg</code> on your path.</p>
  </div>
  <ol class="steps">
    <li>
      <h3>Install kinemo</h3>
      {@html install.pip}
      <p>The extras <code>kinemo[numpy]</code> and <code>kinemo[polars]</code> pull in the data libraries the charts can read.</p>
    </li>
    <li>
      <h3>Start a project</h3>
      {@html install.start}
      <p>It creates <code>scene.py</code>, <code>kinemo.toml</code> and a strict <code>pyrightconfig.json</code>.</p>
    </li>
    <li>
      <h3>Preview, check, render</h3>
      {@html install.run}
    </li>
  </ol>
  <details class="from-source">
    <summary>Build from source</summary>
    <p>
      With a stable Rust toolchain and <a href="https://github.com/astral-sh/uv" rel="noopener">uv</a>,
      from a checkout of <a href="https://github.com/m4nd0r4s/kinemo" rel="noopener">the repository</a>
      (<code>--features gpu</code> adds the GPU preview):
    </p>
    {@html install.source}
  </details>
  <p class="next">
    Next: <a href="{base}/docs/latest/guide/getting-started/">Getting started</a>, the first of fifteen short
    guides, or the <a href="{base}/docs/latest/reference/">API reference</a>.
  </p>
</section>
