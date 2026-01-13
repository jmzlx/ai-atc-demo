<script lang="ts">
	import { onMount } from 'svelte';
	import { API_URL } from '$lib/config';

	let health = $state<Record<string, { status: string; url: string }>>({});
	let loading = $state(true);

	async function fetchHealth() {
		try {
			const res = await fetch(`${API_URL}/health`);
			health = await res.json();
		} catch {
			health = {};
		}
		loading = false;
	}

	onMount(() => {
		fetchHealth();
	});
</script>

<div class="min-h-screen bg-gray-900 text-white">
	<nav class="bg-gray-800 border-b border-gray-700">
		<div class="max-w-7xl mx-auto px-4 py-4">
			<div class="flex items-center justify-between">
				<h1 class="text-xl font-bold">AI ATC Demo</h1>
				<div class="flex gap-4">
					<a href="/live" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded">Live Monitor</a>
					<a href="/sessions" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded">Sessions</a>
				</div>
			</div>
		</div>
	</nav>

	<main class="max-w-7xl mx-auto px-4 py-8">
		<h2 class="text-2xl font-bold mb-6">Service Status</h2>

		{#if loading}
			<p class="text-gray-400">Loading...</p>
		{:else}
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
				{#each Object.entries(health) as [name, info]}
					<div
						class="p-4 rounded-lg {info.status === 'running'
							? 'bg-green-900/30 border border-green-700'
							: 'bg-red-900/30 border border-red-700'}"
					>
						<h3 class="font-semibold capitalize">{name}</h3>
						<p
							class="text-sm {info.status === 'running' ? 'text-green-400' : 'text-red-400'}"
						>
							{info.status}
						</p>
					</div>
				{/each}
			</div>
		{/if}

		<div class="mt-12 grid md:grid-cols-2 gap-8">
			<a
				href="/live"
				class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-blue-600 transition-colors"
			>
				<h3 class="text-xl font-bold mb-2">Live Monitor</h3>
				<p class="text-gray-400">
					Watch the AI ATC agent in real-time. See decisions, screenshots, and metrics as they
					happen.
				</p>
			</a>

			<a
				href="/sessions"
				class="block p-6 bg-gray-800 rounded-lg hover:bg-gray-750 border border-gray-700 hover:border-blue-600 transition-colors"
			>
				<h3 class="text-xl font-bold mb-2">Session Replay</h3>
				<p class="text-gray-400">
					Browse past sessions and replay them with timeline controls. Analyze decisions and
					outcomes.
				</p>
			</a>
		</div>
	</main>
</div>
