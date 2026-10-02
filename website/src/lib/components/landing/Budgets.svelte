<script lang="ts">
  // The performance budgets the test suite asserts, next to what the export measured.
  import type { Timing } from "$lib/site-data";

  let { timings, machine }: { timings: Timing[]; machine: string } = $props();

  const bound = (budget: string) => (budget.startsWith("real") ? `≥ ${budget}` : `< ${budget}`);
</script>

{#if timings.length}
  <section class="band" id="performance">
    <div class="band-head">
      <h2>Budgets, measured</h2>
      <p>
        The test suite fails when kinemo misses these. The right column was measured when this site's
        data was exported ({machine}, best of several runs).
      </p>
    </div>
    <div class="table-wrap">
      <table class="budgets">
        <thead><tr><th>What</th><th class="num">Budget</th><th class="num">This build</th></tr></thead>
        <tbody>
          {#each timings as row (row.what)}
            <tr>
              <td>{row.what}</td>
              <td class="num">{bound(row.budget)}</td>
              <td class="num" class:ok={row.ok} class:over={!row.ok}>{row.measured}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/if}
