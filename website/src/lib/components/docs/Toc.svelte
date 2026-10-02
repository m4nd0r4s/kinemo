<script lang="ts">
  // The page's sections; the one being read is marked as you scroll.
  interface Heading {
    level: number;
    id: string;
    text: string;
  }

  let { headings }: { headings: Heading[] } = $props();
  let here = $state("");

  $effect(() => {
    if (!("IntersectionObserver" in window)) return;
    const targets = headings.map((h) => document.getElementById(h.id)).filter((el): el is HTMLElement => el !== null);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length) here = visible[0].target.id;
      },
      { rootMargin: "-70px 0px -70% 0px" }
    );
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  });
</script>

<aside class="doc-toc" aria-label="On this page">
  {#if headings.length >= 2}
    <h2>On this page</h2>
    <ol>
      {#each headings as heading (heading.id)}
        <li class="toc-{heading.level}"><a href="#{heading.id}" class:here={here === heading.id}>{heading.text}</a></li>
      {/each}
    </ol>
  {/if}
</aside>
