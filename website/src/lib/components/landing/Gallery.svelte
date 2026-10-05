<script lang="ts">
  // The repository's examples, rendered by kinemo; a video plays while hovered or focused.
  import { base } from "$app/paths";
  import { inlineCode, type Example } from "$lib/site-data";

  let { examples }: { examples: Example[] } = $props();

  const firstSentence = (about: string) => about.split(". ")[0].replace(/\.$/, "") + ".";

  function play(e: Event) {
    (e.currentTarget as HTMLElement).querySelector("video")?.play().catch(() => {});
  }
  function stop(e: Event) {
    (e.currentTarget as HTMLElement).querySelector("video")?.pause();
  }
</script>

<section class="band" id="examples">
  <div class="band-head">
    <h2>Examples</h2>
    <p>
      Complete scenes from the repository. Each one passes <code>kinemo check --strict</code>, runs
      in the test suite and was rendered by kinemo for this page. Hover to play.
    </p>
  </div>
  <ul class="gallery">
    {#each examples as example (example.name)}
      <li>
        <a href="{base}/docs/latest/examples/{example.name}/" onmouseenter={play} onfocus={play} onmouseleave={stop} onblur={stop}>
          <figure class="stage">
            <video src="{base}/media/{example.name}.mp4" poster="{base}/media/{example.name}.png" muted loop playsinline preload="none"></video>
          </figure>
          <h3>{example.title}</h3>
          <p>{@html inlineCode(firstSentence(example.about))}</p>
        </a>
      </li>
    {/each}
  </ul>
</section>
