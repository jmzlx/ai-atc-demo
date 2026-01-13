<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URL } from '$lib/config';

	// State
	let agentStatus = $state<{ running: boolean; session_id: string | null; mcp_running: boolean }>({
		running: false,
		session_id: null,
		mcp_running: false
	});
	let health = $state<Record<string, { status: string }>>({});
	let screenshotUrl = $state<string | null>(null);
	let events = $state<any[]>([]);
	let timewarp = $state(10);
	let starting = $state(false);
	let stopping = $state(false);

	let pollInterval: ReturnType<typeof setInterval> | null = null;

	// Derived state
	let decisions = $derived(
		events
			.filter((e) => e.event_type === 'decision')
			.slice(-25)
			.reverse()
	);

	let outcomes = $derived(
		Object.fromEntries(
			events.filter((e) => e.event_type === 'outcome').map((e) => [e.correlation_id, e])
		)
	);

	let metrics = $derived(() => {
		const landings = events.filter((e) => e.event_type === 'landing').length;
		const decisionEvents = events.filter((e) => e.event_type === 'decision');
		const outcomeEvents = events.filter((e) => e.event_type === 'outcome');
		const successes = outcomeEvents.filter((e) => e.success).length;
		const successRate = outcomeEvents.length > 0 ? (successes / outcomeEvents.length) * 100 : 0;
		const conflicts = events.filter((e) => e.event_type === 'conflict').length;
		const snapshots = events.filter((e) => e.event_type === 'state_snapshot');
		const score = snapshots.length > 0 ? snapshots[snapshots.length - 1].score || 0 : 0;
		return { landings, decisions: decisionEvents.length, successRate, conflicts, score };
	});

	async function fetchStatus() {
		try {
			const res = await fetch(`${API_URL}/agent/status`);
			agentStatus = await res.json();
		} catch {
			agentStatus = { running: false, session_id: null, mcp_running: false };
		}
	}

	async function fetchHealth() {
		try {
			const res = await fetch(`${API_URL}/health`);
			health = await res.json();
		} catch {
			health = {};
		}
	}

	async function fetchScreenshot() {
		if (!agentStatus.mcp_running) {
			screenshotUrl = null;
			return;
		}
		try {
			const res = await fetch(`${API_URL}/screenshot`);
			if (res.ok) {
				const blob = await res.blob();
				if (screenshotUrl) URL.revokeObjectURL(screenshotUrl);
				screenshotUrl = URL.createObjectURL(blob);
			}
		} catch {
			// Ignore
		}
	}

	async function fetchEvents() {
		if (!agentStatus.session_id) {
			events = [];
			return;
		}
		try {
			const res = await fetch(`${API_URL}/sessions/${agentStatus.session_id}/events`);
			if (res.ok) {
				const data = await res.json();
				events = data.events || [];
			}
		} catch {
			// Session might not have logs yet
		}
	}

	async function startAgent() {
		starting = true;
		try {
			const res = await fetch(`${API_URL}/agent/start`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ timewarp, cycles: 200 })
			});
			if (res.ok) {
				await fetchStatus();
			}
		} finally {
			starting = false;
		}
	}

	async function stopAgent() {
		stopping = true;
		try {
			await fetch(`${API_URL}/agent/stop`, { method: 'POST' });
			await fetchStatus();
			events = [];
		} finally {
			stopping = false;
		}
	}

	let polling = true;

	async function poll() {
		if (!polling) return;
		await fetchStatus();
		await fetchScreenshot();
		await fetchEvents();
		if (polling) {
			pollInterval = setTimeout(poll, 2000) as unknown as ReturnType<typeof setInterval>;
		}
	}

	onMount(async () => {
		await fetchHealth();
		await fetchStatus();
		await fetchScreenshot();
		await fetchEvents();
		poll();
	});

	onDestroy(() => {
		polling = false;
		if (pollInterval) clearTimeout(pollInterval as unknown as number);
		if (screenshotUrl) URL.revokeObjectURL(screenshotUrl);
	});
</script>

<div class="min-h-screen bg-gray-900 text-white">
	<nav class="bg-gray-800 border-b border-gray-700">
		<div class="max-w-7xl mx-auto px-4 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
					<a href="/" class="text-gray-400 hover:text-white">&larr; Back</a>
					<h1 class="text-xl font-bold">Live Monitor</h1>
				</div>
				<div class="flex gap-4">
					<a href="/sessions" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded">Sessions</a>
				</div>
			</div>
		</div>
	</nav>

	<main class="max-w-7xl mx-auto px-4 py-6">
		<!-- Service Status -->
		<div class="mb-6">
			<div class="flex gap-4 text-sm">
				{#each Object.entries(health) as [name, info]}
					<span class={info.status === 'running' ? 'text-green-400' : 'text-red-400'}>
						{name}: {info.status}
					</span>
				{/each}
			</div>
		</div>

		<!-- Agent Controls -->
		<div class="mb-6 p-4 bg-gray-800 rounded-lg">
			<div class="flex items-center gap-6">
				<div class="flex items-center gap-2">
					<label for="timewarp" class="text-sm">Timewarp:</label>
					<input
						id="timewarp"
						type="range"
						min="1"
						max="50"
						bind:value={timewarp}
						disabled={agentStatus.running}
						class="w-32"
					/>
					<span class="text-sm w-8">{timewarp}x</span>
				</div>

				{#if agentStatus.running}
					<button
						onclick={stopAgent}
						disabled={stopping}
						class="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded"
					>
						{stopping ? 'Stopping...' : 'Stop Agent'}
					</button>
					<span class="text-green-400">Running: {agentStatus.session_id}</span>
				{:else}
					<button
						onclick={startAgent}
						disabled={starting || health.openscope?.status !== 'running'}
						class="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded"
					>
						{starting ? 'Starting...' : 'Start Agent'}
					</button>
					{#if health.openscope?.status !== 'running'}
						<span class="text-red-400 text-sm">OpenScope not running</span>
					{/if}
				{/if}
			</div>
		</div>

		<!-- Main Content Grid -->
		<div class="grid lg:grid-cols-2 gap-6">
			<!-- Screenshot -->
			<div class="bg-gray-800 rounded-lg overflow-hidden">
				<div class="p-3 border-b border-gray-700">
					<h2 class="font-semibold">Radar View</h2>
				</div>
				<div class="aspect-video bg-black flex items-center justify-center">
					{#if screenshotUrl}
						<img src={screenshotUrl} alt="OpenScope radar" class="w-full h-full object-contain" />
					{:else if agentStatus.running}
						<span class="text-gray-500">Waiting for screenshot...</span>
					{:else}
						<span class="text-gray-500">Start agent to see radar</span>
					{/if}
				</div>
			</div>

			<!-- Decisions & Metrics -->
			<div class="space-y-6">
				<!-- Metrics -->
				<div class="bg-gray-800 rounded-lg p-4">
					<h2 class="font-semibold mb-3">Metrics</h2>
					<div class="grid grid-cols-4 gap-4 text-center">
						<div>
							<div class="text-2xl font-bold">{metrics().landings}</div>
							<div class="text-xs text-gray-400">Landings</div>
						</div>
						<div>
							<div class="text-2xl font-bold">{metrics().successRate.toFixed(0)}%</div>
							<div class="text-xs text-gray-400">Success</div>
						</div>
						<div>
							<div class="text-2xl font-bold">{metrics().conflicts}</div>
							<div class="text-xs text-gray-400">Conflicts</div>
						</div>
						<div>
							<div class="text-2xl font-bold">{metrics().score}</div>
							<div class="text-xs text-gray-400">Score</div>
						</div>
					</div>
				</div>

				<!-- Decisions -->
				<div class="bg-gray-800 rounded-lg">
					<div class="p-3 border-b border-gray-700">
						<h2 class="font-semibold">Agent Decisions</h2>
					</div>
					<div class="p-3 h-64 overflow-y-auto font-mono text-sm">
						{#if decisions.length === 0}
							<span class="text-gray-500">Waiting for decisions...</span>
						{:else}
							{#each decisions as decision}
								{@const outcome = outcomes[decision.correlation_id]}
								<div class="mb-1">
									{#if outcome?.success === true}
										<span class="text-green-400">✓</span>
									{:else if outcome?.success === false}
										<span class="text-red-400">✗</span>
									{:else}
										<span class="text-gray-400">⋯</span>
									{/if}
									<span class="text-blue-400">{decision.callsign?.padEnd(8) || '???     '}</span>
									<span>{decision.command_type?.toUpperCase() || '???'}</span>
									{#if decision.command_value}
										<span class="text-yellow-400">{decision.command_value}</span>
									{/if}
								</div>
							{/each}
						{/if}
					</div>
				</div>
			</div>
		</div>
	</main>
</div>
