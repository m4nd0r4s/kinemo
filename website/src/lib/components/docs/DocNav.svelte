<script lang="ts">
  // The documentation's sections; the guides are numbered because they are read in order.
  import { base } from "$app/paths";

  interface Group {
    section: string;
    items: { url: string; title: string; number: number | null }[];
  }

  let { groups, current }: { groups: Group[]; current: string } = $props();
  let open = $state(false);
</script>

<button class="nav-toggle" type="button" aria-expanded={open} onclick={() => (open = !open)}>Documentation menu</button>
<nav class="doc-nav" class:open aria-label="Documentation">
  {#each groups as group (group.section)}
    <div class="nav-group">
      <h2>{group.section}</h2>
      <ul>
        {#each group.items as item (item.url)}
          <li>
            <a href="{base}{item.url}" aria-current={item.url === current ? "page" : undefined}>
              {#if item.number}<span class="nav-number">{item.number}</span>{/if}{item.title}
            </a>
          </li>
        {/each}
      </ul>
    </div>
  {/each}
</nav>
