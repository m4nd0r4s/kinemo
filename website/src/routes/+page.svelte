<script lang="ts">
  import "$lib/styles/landing.css";
  import { base } from "$app/paths";
  import Agents from "$lib/components/landing/Agents.svelte";
  import Budgets from "$lib/components/landing/Budgets.svelte";
  import Editor from "$lib/components/landing/Editor.svelte";
  import Gallery from "$lib/components/landing/Gallery.svelte";
  import Install from "$lib/components/landing/Install.svelte";
  import Pipeline from "$lib/components/landing/Pipeline.svelte";
  import Studio from "$lib/components/landing/Studio.svelte";
  import Terminal from "$lib/components/landing/Terminal.svelte";

  let { data } = $props();
  const site = $derived(data.site);
</script>

<svelte:head>
  <title>kinemo</title>
  <meta
    name="description"
    content="Explanatory animations in Python with a native Rust core: a timeline you can scrub, errors that carry the fix, and a preview that edits your code."
  />
</svelte:head>

<div class="landing">
  <section class="hero">
    <h1>Animation as a pure function of time.</h1>
    <div class="hero-body">
      <p class="lede">
        kinemo is a Python library for explanatory animations: math, algorithms, engineering, data.
        Your script runs once and compiles to a timeline. A Rust core evaluates any instant of it, so
        the preview scrubs without re-running your code, renders spread across cores, and the same
        source gives the same pixels.
      </p>
      <div class="actions">
        <a class="button primary" href="#install">Install</a>
        <a class="button" href="{base}/docs/guide/getting-started/">Read the guide</a>
      </div>
    </div>
  </section>

  <Studio name={site.hero.name} duration={site.hero.duration} bars={site.hero.bars} lines={data.heroLines} />

  <Pipeline timeline={site.checks.timeline} />

  <section class="band" id="diagnostics">
    <div class="band-head">
      <h2>Mistakes come with the fix</h2>
      <p>
        Every problem has a stable code, the offending line and the related one, the instant on the
        timeline and numbered fixes. <code>kinemo check --fix</code> applies the safe ones,
        <code>kinemo explain K0401</code> gives the long form, and Manim habits are recognized and translated.
      </p>
    </div>
    <div class="terminals">
      <Terminal run={site.checks.constraint} />
      <Terminal run={site.checks.manim} />
    </div>
  </section>

  <Editor edit={site.edit} example={site.hero.name} />
  <Gallery examples={site.examples} />
  <Budgets timings={site.timings} machine={site.machine} />
  <Agents report={site.checks.json} />
  <Install install={data.install} />
</div>
