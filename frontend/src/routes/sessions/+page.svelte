<script lang="ts">
	import { onMount } from 'svelte';
	import { API_URL } from '$lib/config';

	interface Session {
		session_id: string;
		timestamp: string;
		model: string | null;
		duration_s: number | null;
		score: number | null;
		landings: number | null;
		event_count: number;
	}

	let sessions = $state<Session[]>([]);
	let loading = $state(true);

	function formatDuration(seconds: number | null): string {
		if (seconds === null) return '-';
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}m ${secs}s`;
	}

	function formatDate(timestamp: string): string {
		if (!timestamp) return '-';
		try {
			const date = new Date(timestamp);
			return date.toLocaleString();
		} catch {
			return timestamp;
		}
	}

	function formatModel(model: string | null): string {
		if (!model) return '-';
		// Shorten long model names
		const parts = model.split('/');
		return parts[parts.length - 1];
	}

	async function fetchSessions() {
		try {
			const res = await fetch(`${API_URL}/sessions`);
			sessions = await res.json();
		} catch {
			sessions = [];
		}
		loading = false;
	}

	onMount(() => {
		fetchSessions();
	});
</script>

<div class="min-h-screen bg-gray-900 text-white">
	<nav class="bg-gray-800 border-b border-gray-700">
		<div class="max-w-7xl mx-auto px-4 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
					<a href="/" class="text-gray-400 hover:text-white">&larr; Back</a>
					<h1 class="text-xl font-bold">Sessions</h1>
				</div>
				<div class="flex gap-4">
					<a href="/live" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded">Live Monitor</a>
				</div>
			</div>
		</div>
	</nav>

	<main class="max-w-7xl mx-auto px-4 py-6">
		{#if loading}
			<p class="text-gray-400">Loading sessions...</p>
		{:else if sessions.length === 0}
			<div class="text-center py-12">
				<p class="text-gray-400 mb-4">No sessions found</p>
				<a href="/live" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded">
					Start a new session
				</a>
			</div>
		{:else}
			<div class="bg-gray-800 rounded-lg overflow-hidden">
				<table class="w-full">
					<thead class="bg-gray-700">
						<tr>
							<th class="px-4 py-3 text-left text-sm font-semibold">Session ID</th>
							<th class="px-4 py-3 text-left text-sm font-semibold">Date</th>
							<th class="px-4 py-3 text-left text-sm font-semibold">Model</th>
							<th class="px-4 py-3 text-right text-sm font-semibold">Duration</th>
							<th class="px-4 py-3 text-right text-sm font-semibold">Landings</th>
							<th class="px-4 py-3 text-right text-sm font-semibold">Score</th>
							<th class="px-4 py-3 text-right text-sm font-semibold">Events</th>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-700">
						{#each sessions as session}
							<tr class="hover:bg-gray-750">
								<td class="px-4 py-3 font-mono text-sm">{session.session_id}</td>
								<td class="px-4 py-3 text-sm text-gray-400">{formatDate(session.timestamp)}</td>
								<td class="px-4 py-3 text-sm">{formatModel(session.model)}</td>
								<td class="px-4 py-3 text-sm text-right">{formatDuration(session.duration_s)}</td>
								<td class="px-4 py-3 text-sm text-right">{session.landings ?? '-'}</td>
								<td class="px-4 py-3 text-sm text-right {(session.score ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}">
									{session.score ?? '-'}
								</td>
								<td class="px-4 py-3 text-sm text-right text-gray-400">{session.event_count}</td>
								<td class="px-4 py-3 text-right">
									<a
										href="/replay/{session.session_id}"
										class="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
									>
										Replay
									</a>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</main>
</div>
