<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { API_URL } from '$lib/config';

	// Props from route
	let sessionId = $derived($page.params.id);

	// Session data
	let events = $state<any[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Playback state
	let playing = $state(false);
	let currentTime = $state(0);
	let playbackSpeed = $state(1);
	let animationFrame: number | null = null;
	let lastRealTime: number | null = null;

	// Derived from events
	let maxTime = $derived(
		events.length > 0 ? Math.max(...events.map((e) => e.game_time || 0)) : 0
	);

	let snapshots = $derived(events.filter((e) => e.event_type === 'state_snapshot'));

	let decisions = $derived(events.filter((e) => e.event_type === 'decision'));

	let conflicts = $derived(events.filter((e) => e.event_type === 'conflict'));

	let sessionMeta = $derived(() => {
		const start = events.find((e) => e.event_type === 'session_start');
		const end = events.find((e) => e.event_type === 'session_end');
		return {
			model: start?.metadata?.model || 'Unknown',
			score: end?.summary?.game_score ?? 0,
			landings: end?.summary?.arrivals_landed ?? 0
		};
	});

	// Aircraft interface for type safety
	interface Aircraft {
		callsign: string;
		position: [number, number];
		altitude: number;
		heading: number;
		speed: number;
		phase?: string;
		[key: string]: unknown;
	}

	// Get current aircraft state (interpolated)
	let currentAircraft = $derived(() => {
		if (snapshots.length === 0) return [] as Aircraft[];

		// Find bracketing snapshots
		let before = snapshots[0];
		let after = snapshots[0];

		for (const snap of snapshots) {
			if (snap.game_time <= currentTime) {
				before = snap;
			}
			if (snap.game_time >= currentTime && after.game_time < currentTime) {
				after = snap;
			}
		}

		// If same snapshot or no interpolation needed
		if (before === after || !before.aircraft || !after.aircraft || before.game_time === after.game_time) {
			return (before.aircraft || []) as Aircraft[];
		}

		// Interpolate between snapshots
		const t =
			(currentTime - before.game_time) / (after.game_time - before.game_time);

		const beforeMap = new Map<string, Aircraft>(
			(before.aircraft as Aircraft[]).map((a) => [a.callsign, a])
		);
		const afterMap = new Map<string, Aircraft>(
			(after.aircraft as Aircraft[]).map((a) => [a.callsign, a])
		);

		const result: Aircraft[] = [];
		for (const [callsign, beforeAc] of beforeMap) {
			const afterAc = afterMap.get(callsign);
			if (afterAc) {
				result.push({
					...beforeAc,
					altitude: beforeAc.altitude + (afterAc.altitude - beforeAc.altitude) * t,
					heading: interpolateAngle(beforeAc.heading, afterAc.heading, t),
					speed: beforeAc.speed + (afterAc.speed - beforeAc.speed) * t,
					position: [
						beforeAc.position[0] + (afterAc.position[0] - beforeAc.position[0]) * t,
						beforeAc.position[1] + (afterAc.position[1] - beforeAc.position[1]) * t
					]
				});
			} else {
				result.push(beforeAc);
			}
		}
		return result;
	});

	// Get decisions up to current time
	let currentDecisions = $derived(
		decisions
			.filter((d) => d.game_time <= currentTime)
			.slice(-20)
			.reverse()
	);

	// Get events around current time for timeline markers
	let timelineEvents = $derived(() => {
		const markers: { time: number; type: string; label: string }[] = [];

		for (const c of conflicts) {
			markers.push({
				time: c.game_time,
				type: 'conflict',
				label: `Conflict: ${c.aircraft1} / ${c.aircraft2}`
			});
		}

		for (const e of events.filter((ev) => ev.event_type === 'ils_clearance')) {
			markers.push({
				time: e.game_time,
				type: 'ils',
				label: `ILS: ${e.callsign} → ${e.runway}`
			});
		}

		return markers.sort((a, b) => a.time - b.time);
	});

	function interpolateAngle(a: number, b: number, t: number): number {
		// Handle wrapping around 360 degrees
		let diff = b - a;
		if (diff > 180) diff -= 360;
		if (diff < -180) diff += 360;
		return (a + diff * t + 360) % 360;
	}

	function formatTime(seconds: number): string {
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	async function fetchEvents() {
		loading = true;
		error = null;
		try {
			const res = await fetch(`${API_URL}/sessions/${sessionId}/events`);
			if (!res.ok) {
				throw new Error(`Failed to load session: ${res.statusText}`);
			}
			const data = await res.json();
			events = data.events || [];
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
			events = [];
		}
		loading = false;
	}

	function play() {
		playing = true;
		lastRealTime = performance.now();
		tick();
	}

	function pause() {
		playing = false;
		if (animationFrame) {
			cancelAnimationFrame(animationFrame);
			animationFrame = null;
		}
	}

	function tick() {
		if (!playing) return;

		const now = performance.now();
		if (lastRealTime !== null) {
			const delta = (now - lastRealTime) / 1000; // Convert to seconds
			currentTime = Math.min(currentTime + delta * playbackSpeed, maxTime);

			if (currentTime >= maxTime) {
				pause();
			}
		}
		lastRealTime = now;
		animationFrame = requestAnimationFrame(tick);
	}

	function seek(time: number) {
		currentTime = Math.max(0, Math.min(time, maxTime));
	}

	function handleTimelineClick(e: MouseEvent) {
		const target = e.currentTarget as HTMLElement;
		const rect = target.getBoundingClientRect();
		const x = e.clientX - rect.left;
		const percent = x / rect.width;
		seek(percent * maxTime);
	}

	function handleKeydown(e: KeyboardEvent) {
		switch (e.key) {
			case ' ':
				e.preventDefault();
				playing ? pause() : play();
				break;
			case 'ArrowLeft':
				e.preventDefault();
				seek(currentTime - 5);
				break;
			case 'ArrowRight':
				e.preventDefault();
				seek(currentTime + 5);
				break;
			case '+':
			case '=':
				playbackSpeed = Math.min(playbackSpeed * 2, 10);
				break;
			case '-':
				playbackSpeed = Math.max(playbackSpeed / 2, 0.5);
				break;
		}
	}

	onMount(() => {
		fetchEvents();
		window.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		pause();
		window.removeEventListener('keydown', handleKeydown);
	});
</script>

<div class="min-h-screen bg-gray-900 text-white">
	<nav class="bg-gray-800 border-b border-gray-700">
		<div class="max-w-7xl mx-auto px-4 py-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
					<a href="/sessions" class="text-gray-400 hover:text-white">&larr; Sessions</a>
					<h1 class="text-xl font-bold">Replay: {sessionId}</h1>
				</div>
				<div class="text-sm text-gray-400">
					{sessionMeta().model} | Score: {sessionMeta().score} | Landings: {sessionMeta().landings}
				</div>
			</div>
		</div>
	</nav>

	<main class="max-w-7xl mx-auto px-4 py-6">
		{#if loading}
			<p class="text-gray-400">Loading session...</p>
		{:else if error}
			<div class="bg-red-900/30 border border-red-700 rounded-lg p-4">
				<p class="text-red-400">{error}</p>
				<a href="/sessions" class="text-blue-400 hover:underline">Back to sessions</a>
			</div>
		{:else}
			<!-- Playback Controls -->
			<div class="mb-6 p-4 bg-gray-800 rounded-lg">
				<div class="flex items-center gap-4 mb-4">
					<button
						onclick={() => (playing ? pause() : play())}
						class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded"
					>
						{playing ? 'Pause' : 'Play'}
					</button>

					<span class="font-mono">{formatTime(currentTime)} / {formatTime(maxTime)}</span>

					<div class="flex items-center gap-2">
						<span class="text-sm text-gray-400">Speed:</span>
						<select bind:value={playbackSpeed} class="bg-gray-700 rounded px-2 py-1 text-sm">
							<option value={0.5}>0.5x</option>
							<option value={1}>1x</option>
							<option value={2}>2x</option>
							<option value={5}>5x</option>
							<option value={10}>10x</option>
						</select>
					</div>

					<span class="text-xs text-gray-500 ml-auto">
						Space: play/pause | ←→: seek | +−: speed
					</span>
				</div>

				<!-- Timeline -->
				<div
					class="relative h-8 bg-gray-700 rounded cursor-pointer"
					onclick={handleTimelineClick}
					onkeydown={(e) => {
						if (e.key === 'ArrowLeft') seek(currentTime - 5);
						if (e.key === 'ArrowRight') seek(currentTime + 5);
					}}
					role="slider"
					tabindex="0"
					aria-valuenow={currentTime}
					aria-valuemin={0}
					aria-valuemax={maxTime}
				>
					<!-- Progress bar -->
					<div
						class="absolute top-0 left-0 h-full bg-blue-600 rounded-l"
						style="width: {maxTime > 0 ? (currentTime / maxTime) * 100 : 0}%"
					></div>

					<!-- Event markers -->
					{#each timelineEvents() as marker}
						<div
							class="absolute top-0 w-1 h-full {marker.type === 'conflict'
								? 'bg-red-500'
								: 'bg-green-500'}"
							style="left: {maxTime > 0 ? (marker.time / maxTime) * 100 : 0}%"
							title={marker.label}
						></div>
					{/each}

					<!-- Playhead -->
					<div
						class="absolute top-0 w-0.5 h-full bg-white"
						style="left: {maxTime > 0 ? (currentTime / maxTime) * 100 : 0}%"
					></div>
				</div>
			</div>

			<!-- Main Content Grid -->
			<div class="grid lg:grid-cols-2 gap-6">
				<!-- Aircraft State -->
				<div class="bg-gray-800 rounded-lg">
					<div class="p-3 border-b border-gray-700">
						<h2 class="font-semibold">Aircraft State ({currentAircraft().length})</h2>
					</div>
					<div class="p-3 h-80 overflow-y-auto">
						{#if currentAircraft().length === 0}
							<span class="text-gray-500">No aircraft data</span>
						{:else}
							<table class="w-full text-sm">
								<thead>
									<tr class="text-gray-400 text-left">
										<th class="pb-2">Callsign</th>
										<th class="pb-2 text-right">Alt (ft)</th>
										<th class="pb-2 text-right">Hdg</th>
										<th class="pb-2 text-right">Spd (kts)</th>
										<th class="pb-2">Phase</th>
									</tr>
								</thead>
								<tbody class="font-mono">
									{#each currentAircraft() as ac}
										<tr class="border-t border-gray-700">
											<td class="py-1 text-blue-400">{ac.callsign}</td>
											<td class="py-1 text-right">{Math.round(ac.altitude)}</td>
											<td class="py-1 text-right">{Math.round(ac.heading)}°</td>
											<td class="py-1 text-right">{Math.round(ac.speed)}</td>
											<td class="py-1 text-gray-400">{ac.phase || '-'}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						{/if}
					</div>
				</div>

				<!-- Decisions -->
				<div class="bg-gray-800 rounded-lg">
					<div class="p-3 border-b border-gray-700">
						<h2 class="font-semibold">
							Decisions (up to {formatTime(currentTime)})
						</h2>
					</div>
					<div class="p-3 h-80 overflow-y-auto font-mono text-sm">
						{#if currentDecisions.length === 0}
							<span class="text-gray-500">No decisions yet</span>
						{:else}
							{#each currentDecisions as decision}
								<div class="mb-1 flex gap-2">
									<span class="text-gray-500 w-12">{formatTime(decision.game_time)}</span>
									<span class="text-blue-400 w-20">{decision.callsign}</span>
									<span class="text-yellow-400">
										{decision.command_type?.toUpperCase()}
										{decision.command_value || ''}
									</span>
								</div>
							{/each}
						{/if}
					</div>
				</div>
			</div>

			<!-- Conflicts -->
			{#if conflicts.filter((c) => c.game_time <= currentTime).length > 0}
				<div class="mt-6 bg-red-900/30 border border-red-700 rounded-lg p-4">
					<h2 class="font-semibold mb-2 text-red-400">Conflicts Detected</h2>
					<div class="space-y-1 text-sm">
						{#each conflicts.filter((c) => c.game_time <= currentTime) as conflict}
							<div>
								<span class="text-gray-400">{formatTime(conflict.game_time)}</span>
								<span class="text-red-400 ml-2">
									{conflict.aircraft1} / {conflict.aircraft2}
								</span>
								<span class="text-gray-500 ml-2">
									{conflict.separation_nm?.toFixed(1)}nm (required: {conflict.required_nm}nm)
								</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		{/if}
	</main>
</div>
