<script lang="ts">
  // Docs search: press / anywhere. Sections are scored by where the words appear: in the
  // heading first, then the page title, then the text.
  import { base } from "$app/paths";
  import { afterNavigate } from "$app/navigation";
  import { search } from "$lib/search.svelte";

  interface Entry {
    page: string;
    section: string;
    url: string;
    text: string;
  }

  let index: Entry[] | null = null;
  let query = $state("");
  let selected = $state(0);
  let input = $state<HTMLInputElement>();
  let list = $state<HTMLOListElement>();

  async function load() {
    // The index of the version being read (`/docs/<version>/...`), the latest elsewhere.
    const version = window.location.pathname.match(/\/docs\/([^/]+)\//)?.[1] ?? "latest";
    index ??= await (await fetch(`${base}/docs/${version}/search.json`)).json();
    return index!;
  }

  function score(entry: Entry, words: string[]): number {
    const heading = entry.section.toLowerCase();
    const page = entry.page.toLowerCase();
    const text = entry.text.toLowerCase();
    let total = 0;
    for (const word of words) {
      const s = (heading.includes(word) ? 6 : 0) + (page.includes(word) ? 3 : 0) + (text.includes(word) ? 1 : 0);
      if (!s) return 0;
      total += s + (heading.startsWith(word) || heading.includes(`.${word}`) ? 2 : 0);
    }
    return total;
  }

  let loaded = $state<Entry[]>([]);
  const words = $derived(query.toLowerCase().split(/\s+/).filter(Boolean));
  const results = $derived.by(() => {
    if (!words.length) return [];
    return loaded
      .map((entry) => [score(entry, words), entry] as const)
      .filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0])
      .slice(0, 12)
      .map(([, entry]) => entry);
  });

  function escapeHtml(s: string) {
    return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
  }

  function mark(text: string): string {
    let out = escapeHtml(text);
    for (const word of words) {
      if (word.length < 2) continue;
      out = out.replace(new RegExp(`(${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"), "<mark>$1</mark>");
    }
    return out;
  }

  $effect(() => {
    if (!search.open) return;
    query = "";
    selected = 0;
    load().then((entries) => (loaded = entries));
    queueMicrotask(() => input?.focus());
  });

  $effect(() => {
    void results;
    selected = 0;
  });

  afterNavigate(() => (search.open = false));

  function onWindowKey(e: KeyboardEvent) {
    const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
    if (e.key === "/" && !typing && !search.open) {
      e.preventDefault();
      search.open = true;
    } else if (e.key === "Escape" && search.open) {
      search.open = false;
    }
  }

  function onInputKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!results.length) return;
      selected = (selected + (e.key === "ArrowDown" ? 1 : -1) + results.length) % results.length;
      list?.querySelectorAll("a")[selected]?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      list?.querySelectorAll("a")[selected]?.click();
    }
  }
</script>

<svelte:window onkeydown={onWindowKey} />

{#if search.open}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="search" onclick={(e) => e.target === e.currentTarget && (search.open = false)}>
    <div class="search-box" role="dialog" aria-modal="true" aria-label="Search the documentation">
      <input
        bind:this={input}
        bind:value={query}
        onkeydown={onInputKey}
        type="search"
        placeholder="Search the docs: place, morph, K0401…"
        autocomplete="off"
        spellcheck="false"
      />
      <ol class="search-results" bind:this={list}>
        {#if query.trim() && !results.length}
          <li class="empty">
            No section mentions “{query}”. Try a function name such as <code>place</code> or a code such as <code>K0401</code>.
          </li>
        {/if}
        {#each results as entry, i (entry.url)}
          <li>
            <a href="{base}/{entry.url}" class:selected={i === selected}>
              <span class="where">{entry.page}</span>
              <span class="what">{@html mark(entry.section || entry.page)}</span>
              <span class="text">{@html mark(entry.text.slice(0, 150))}</span>
            </a>
          </li>
        {/each}
      </ol>
      <p class="search-hint">↑ ↓ to move, Enter to open, Esc to close</p>
    </div>
  </div>
{/if}
