<script lang="ts">
  import "$lib/styles/docs.css";
  import { base } from "$app/paths";
  import DocNav from "$lib/components/docs/DocNav.svelte";
  import Toc from "$lib/components/docs/Toc.svelte";
  import { copyButtons } from "$lib/copy-buttons";

  let { data } = $props();
  const latest = $derived(data.versions?.find((v) => v.id === "latest"));
</script>

<svelte:head>
  {#if data.redirect !== null}
    <!-- An address from before versions: the same page in the latest release. -->
    <title>kinemo documentation</title>
    <meta http-equiv="refresh" content="0; url={data.redirect}" />
  {:else}
    <title>{data.title} — kinemo</title>
    <meta name="description" content="kinemo documentation: {data.title}." />
    {#if data.version.id !== "latest" && latest}<link rel="canonical" href="{base}{latest.url}" />{/if}
  {/if}
</svelte:head>

{#if data.redirect !== null}
  <p class="doc-redirect">This page moved to <a href={data.redirect}>the latest documentation</a>.</p>
{:else}
<div class="doc-layout">
  <DocNav groups={data.nav} current={data.url} versions={data.versions} version={data.version.id} />
  {#key data.url}
    <article class="doc prose" use:copyButtons>
      {#if data.version.id !== "latest" && latest}
        <p class="version-banner">
          {#if data.version.id === "dev"}
            These are the docs of the unreleased development version.
          {:else}
            These are the docs of kinemo {data.version.label}.
          {/if}
          <a href="{base}{latest.url}">Read this page in the latest release</a>.
        </p>
      {/if}
      {#if data.video}
        <!-- The article opens with the example's render, then the page's own content. -->
        {@html data.html.split("</h1>")[0] + "</h1>"}
        <figure class="stage stage-doc">
          <!-- svelte-ignore a11y_media_has_caption -->
          <video src="{base}/media/{data.video}.mp4" poster="{base}/media/{data.video}.png" controls muted loop playsinline preload="metadata"></video>
          <figcaption>Rendered by <code>kinemo render examples/{data.video}.py</code>.</figcaption>
        </figure>
        {@html data.html.split("</h1>").slice(1).join("</h1>")}
      {:else}
        {@html data.html}
      {/if}
      {#if data.previous || data.next}
        <nav class="pager" aria-label="Previous and next">
          {#if data.previous}<a class="pager-prev" href="{base}{data.previous.url}"><span>Previous</span>{data.previous.title}</a>{/if}
          {#if data.next}<a class="pager-next" href="{base}{data.next.url}"><span>Next</span>{data.next.title}</a>{/if}
        </nav>
      {/if}
    </article>
  {/key}
  <Toc headings={data.toc} />
</div>
{/if}
