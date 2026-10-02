<script lang="ts">
  import "$lib/styles/docs.css";
  import { base } from "$app/paths";
  import DocNav from "$lib/components/docs/DocNav.svelte";
  import Toc from "$lib/components/docs/Toc.svelte";
  import { copyButtons } from "$lib/copy-buttons";

  let { data } = $props();
</script>

<svelte:head>
  <title>{data.title} — kinemo</title>
  <meta name="description" content="kinemo documentation: {data.title}." />
</svelte:head>

<div class="doc-layout">
  <DocNav groups={data.nav} current={data.url} />
  {#key data.url}
    <article class="doc prose" use:copyButtons>
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
