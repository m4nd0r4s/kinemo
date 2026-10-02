<script lang="ts">
  import "$lib/styles/base.css";
  import "$lib/styles/code.css";
  import Footer from "$lib/components/Footer.svelte";
  import Header from "$lib/components/Header.svelte";
  import Search from "$lib/components/Search.svelte";

  let { children, data } = $props();
</script>

<a class="skip" href="#main">Skip to content</a>
<Header />
<main id="main">
  {@render children()}
</main>
<Footer version={data.version} />
<Search />
