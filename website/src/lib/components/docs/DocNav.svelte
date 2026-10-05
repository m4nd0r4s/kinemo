<script lang="ts">
  // The documentation's sections (the guides are numbered because they are read in order),
  // under a switcher between the published versions, which opens the same page in another one.
  import { goto } from "$app/navigation";
  import { base } from "$app/paths";

  interface Group {
    section: string;
    items: { url: string; title: string; number: number | null }[];
  }

  interface Version {
    id: string;
    label: string;
    url: string;
  }

  let { groups, current, versions, version }: { groups: Group[]; current: string; versions: Version[]; version: string } = $props();
  let open = $state(false);
</script>

<button class="nav-toggle" type="button" aria-expanded={open} onclick={() => (open = !open)}>Documentation menu</button>
<nav class="doc-nav" class:open aria-label="Documentation">
  <label class="version-switch">
    <span>Version</span>
    <select value={version} onchange={(e) => goto(`${base}${versions.find((v) => v.id === e.currentTarget.value)?.url ?? "/docs/latest/"}`)}>
      {#each versions as v (v.id)}<option value={v.id}>{v.label}</option>{/each}
    </select>
  </label>
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
