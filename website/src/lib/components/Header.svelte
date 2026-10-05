<script lang="ts">
  import { base } from "$app/paths";
  import { page } from "$app/state";
  import { search } from "$lib/search.svelte";
  import Logo from "./Logo.svelte";
  import ThemeToggle from "./ThemeToggle.svelte";

  const links = [
    { label: "Guide", href: "/docs/latest/guide/getting-started/", section: "/guide/" },
    { label: "Reference", href: "/docs/latest/reference/", section: "/reference/" },
    { label: "Examples", href: "/docs/latest/examples/", section: "/examples/" },
  ];
</script>

<header class="site-header">
  <a class="brand" href="{base}/"><Logo /><span>kinemo</span></a>
  <nav class="site-nav" aria-label="Main">
    {#each links as link (link.href)}
      <a href="{base}{link.href}" aria-current={page.url.pathname.includes(link.section) ? "page" : undefined}>{link.label}</a>
    {/each}
  </nav>
  <button class="search-button" type="button" onclick={() => (search.open = true)} aria-label="Search the docs (press /)">
    <span>Search</span><kbd>/</kbd>
  </button>
  <a class="repo-link" href="https://github.com/m4nd0r4s/kinemo" rel="noopener">GitHub</a>
  <ThemeToggle />
</header>
