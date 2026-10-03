/* Same-origin task controls. Server data is always rendered as text. */
'use strict';

const $ = (id) => document.getElementById(id);
const STAGES = [
  ['queued', 'Queued', 'New work will appear here.'],
  ['working', 'Working', 'No work is in progress right now.'],
  ['review', 'PR review ready', 'Results ready for review will appear here.'],
  ['changes', 'Changes requested', 'No changes are waiting.'],
  ['reviewed', 'Reviewed', 'Reviewed work will appear here.'],
  ['merged', 'Merged', 'Merged work will appear here.'],
  ['scope', 'Awaiting scope', 'Tasks outside the configured coding scopes will appear here.'],
  ['blocked', 'Blocked', 'Nothing needs attention here.'],
  ['closed', 'Closed', 'Closed or cancelled tasks will appear here.'],
];
const STAGE_TITLES = Object.fromEntries(STAGES.map(([key, title]) => [key, title]));
const state = {data: null, connected: false, loading: false, posting: false,
  selectedId: null, priorityDirty: false, lastUpdated: null, uncertain: new Map(), drafts: new Map()};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}
function value(text, fallback = '') { return typeof text === 'string' && text.trim() ? text : fallback; }
function tasks() { return Array.isArray(state.data?.tasks) ? state.data.tasks : []; }
function currentTask() { return tasks().find((task) => task.id === state.selectedId); }
function isPaused(task) { return Boolean(task.paused || task.task_paused || task.state === 'paused'); }
function stageOf(task) {
  const status = value(task.display_state, value(task.state)).toLowerCase();
  const review = value(task.review_state).toLowerCase();
  if (review === 'merged' || status === 'merged') return 'merged';
  if (task.execution) return 'working';
  if (['closed', 'cancelled'].includes(status) || review === 'closed') return 'closed';
  if (status === 'needs_scope') return 'scope';
  if (['blocked', 'needs_owner', 'waiting_quota', 'waiting_budget', 'reconciliation_required'].includes(status)) return 'blocked';
  if (['changes_requested', 'rerun_waiting'].includes(status) || review === 'changes_requested') return 'changes';
  if (review === 'reviewed' || status === 'reviewed') return 'reviewed';
  if (['draft_ready', 'pr_review_ready', 'review_ready'].includes(status)) return 'review';
  if (['coding', 'working', 'ready_test', 'testing', 'ready_review', 'reviewing', 'ready_publish', 'publishing'].includes(status)) return 'working';
  if (['queued', 'planned', 'pending', 'ready', 'codex_ready', 'antigravity_ready', 'local_ready', 'paused'].includes(status)) return 'queued';
  return 'blocked';
}
function statusHint(task) {
  if (task.execution) return value(task.execution.label, 'Task step in progress') + (task.execution.pause_after_step ? ' · pause next' : '');
  if (task.wait_reason) return value(task.wait_reason);
  if (isPaused(task)) return 'Paused by you';
  const hints = {planned: 'Waiting for scope checks', queued: 'Waiting to start',
    needs_scope: 'A coding scope and its tests must be registered', cancelled: 'Cancelled',
    codex_ready: 'Waiting for Codex', antigravity_ready: 'Waiting for Gemini', local_ready: 'Waiting for the local coder',
    coding: 'A coder is working', ready_test: 'Tests are next', testing: 'Running checks',
    ready_review: 'Verification is next', reviewing: 'Checking the result', ready_publish: 'Preparing a pull request',
    publishing: 'Preparing a pull request', waiting_quota: 'Waiting for model availability',
    needs_owner: 'Your input is needed', reconciliation_required: 'A saved result needs attention',
    rerun_waiting: 'A follow-up is waiting', blocked: 'Open for details', draft_ready: 'Pull request ready',
    merged: 'Merged on GitHub', closed: 'Closed without merging'};
  if (task.review_state === 'closed') return 'Pull request closed without merging';
  return hints[task.state] || STAGE_TITLES[stageOf(task)];
}
function ownerName(owner) {
  const names = {codex: 'Codex', antigravity: 'Gemini', gemini: 'Gemini', local: 'Local coder',
    devstral: 'Devstral', qwen: 'Qwen'};
  return ['unknown', 'unassigned'].includes(value(owner).toLowerCase()) ? 'Not assigned' : names[value(owner).toLowerCase()] || value(owner, 'Not assigned');
}
function modelName(model, fallback = 'Not recorded') { return ['unknown', 'unassigned'].includes(value(model).toLowerCase()) ? 'Not recorded' : value(model, fallback); }
function confidence(number) {
  return typeof number === 'number' && Number.isFinite(number) && number >= 0 && number <= 10
    ? `${Number(number.toFixed(1))}/10` : 'Not assessed';
}
function priority(task) { return Number.isInteger(task.priority) && task.priority >= 1 && task.priority <= 5 ? task.priority : 3; }
function stageMatches(stage, filter) {
  return filter === 'all' || stage === filter || (filter === 'attention' && ['blocked', 'changes'].includes(stage))
    || (filter === 'done' && ['reviewed', 'merged'].includes(stage));
}
function parsedDate(input) { const date = new Date(input); return input && Number.isFinite(date.getTime()) ? date : null; }
function fullDate(input) {
  const date = parsedDate(input);
  return date ? new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata'}).format(date)+' IST' : 'Time not recorded';
}
function relativeDate(input) {
  const date = parsedDate(input);
  if (!date) return '';
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
  if (minutes < 10080) return `${Math.floor(minutes / 1440)}d ago`;
  return new Intl.DateTimeFormat(undefined, {month: 'short', day: 'numeric'}).format(date);
}
function githubLink(input) {
  try {
    const url = new URL(input);
    if (url.protocol === 'https:' && url.hostname === 'github.com' && !url.username && !url.password
        && !url.port && /^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/[1-9][0-9]*\/?$/.test(url.pathname)) return url.href;
  } catch (_) { /* Invalid or unrelated links stay plain text. */ }
  return null;
}

function announce(message, type = 'pending', existing = null) {
  const toast = existing || node('div', 'toast');
  toast.className = `toast ${type}`;
  toast.replaceChildren();
  toast.append(node('span', type === 'pending' ? 'spinner' : 'toast-symbol', type === 'pending' ? '' : type === 'error' ? '!' : '✓'));
  toast.firstChild.setAttribute('aria-hidden', 'true');
  toast.append(node('p', '', message));
  if (type !== 'pending') {
    const close = node('button', '', '×');
    close.type = 'button'; close.setAttribute('aria-label', 'Dismiss update');
    close.addEventListener('click', () => toast.remove()); toast.append(close);
    if (type === 'success') setTimeout(() => toast.remove(), 9500);
  }
  const dialog = document.querySelector('dialog[open]');
  let region = dialog ? dialog.querySelector('.dialog-announcements') : $('announcements');
  if (!region) {
    region = node('div', 'toast-region dialog-announcements');
    region.setAttribute('aria-live', 'polite'); region.setAttribute('aria-atomic', 'false'); dialog.append(region);
  }
  if (!existing) region.append(toast);
  while (region.children.length > 4) region.firstElementChild.remove();
  return toast;
}
function syncControls() {
  const writable = Boolean(state.data && state.connected && !state.posting && state.data.csrf_token);
  document.querySelectorAll('[data-write]').forEach((button) => { button.disabled = !writable; });
  $('refresh').disabled = state.loading || state.posting;
  if (state.data) {
    $('globalToggle').textContent = state.data.enabled ? 'Pause work' : 'Resume work';
    const active = tasks().some((task) => task.execution);
    const fallback = !state.data.enabled ? active ? 'Pausing after current work' : 'Work paused' : active ? 'Work in progress' : 'Idle · scheduling enabled';
    $('supervisorStatus').textContent = value(state.data.work_status?.label, fallback);
    $('supervisorStatus').classList.toggle('paused', !state.data.enabled);
    $('workStatusLabel').textContent = value(state.data.work_status?.label, fallback);
    $('workStatusReason').textContent = value(state.data.work_status?.reason, state.data.enabled
      ? 'Scheduling is enabled. Tasks start when their scope, capacity and budget checks pass.'
      : 'Scheduling is paused. Resume to allow eligible work to start.');
    $('generateFuture').disabled = !writable || !state.data.future || generationPending();
  }
  const task = currentTask();
  if (task) {
    const terminal = stageOf(task) === 'merged' || task.review_state === 'closed' || task.state === 'closed';
    ['taskToggle', 'savePriority', 'requestChanges', 'markReviewed'].forEach((id) => { $(id).disabled = !writable || terminal; });
  } else if ($('taskDialog').open) {
    $('taskDialog').querySelectorAll('[data-write]').forEach((button) => { button.disabled = true; });
  }
}
function generationPending() {
  return ['pending', 'requested', 'queued', 'running', 'generating'].includes(state.data?.future?.generation?.state);
}
function futureView() {
  const future = state.data?.future || {};
  const entries = Array.isArray(future.tasks) ? future.tasks.filter((task) => task && typeof task === 'object') : [];
  const size = Number.isInteger(future.next_batch_size) ? Math.max(0, Math.min(10, future.next_batch_size)) : 10;
  const next = new Set(entries.filter((task) => ['ready', 'queued'].includes(task.state)).slice(0, size).map((task) => task.id));
  const needle = $('futureSearch').value.trim().toLowerCase();
  const filter = $('futureFilter').value;
  const matching = entries.filter((task) => (filter === 'all' || (filter === 'active' && !['completed', 'cancelled'].includes(task.state))
    || filter === task.state || (filter === 'next' && next.has(task.id)))
    && (!needle || [task.id, task.title, task.project, task.prompt, task.scope_id, task.reason]
      .some((field) => typeof field === 'string' && field.toLowerCase().includes(needle))));
  return {future, entries, size, next, matching, visible: matching.slice(0, 100)};
}
function renderFuture() {
  const {future, entries, size, next, matching, visible} = futureView();
  const labels = {ready: 'Ready', queued: 'Queued for admission', planned: 'Planned', scheduled: 'Scheduled', admitted: 'Admitted',
    needs_scope: 'Awaiting coding scope', needs_owner: 'Needs your input', blocked: 'Held for recovery',
    review_ready: 'PR review ready', completed: 'Completed', cancelled: 'Cancelled'};
  const activeCount = entries.filter((task) => !['completed', 'cancelled'].includes(task.state)).length;
  $('futureCount').textContent = activeCount;
  const interval = Number.isInteger(future.interval_minutes) && future.interval_minutes > 0 ? future.interval_minutes : 5;
  $('futureCadence').textContent = `Up to ${size} tasks in the next batch · checked every ${interval} minutes`;
  const generation = future.generation || {};
  const generationLabels = {pending: 'Generation requested. Waiting for the supervisor.', requested: 'Generation requested. Waiting for the supervisor.', queued: 'Generation queued.',
    running: 'The supervisor is preparing future tasks.', generating: 'The supervisor is preparing future tasks.',
    completed: 'Future-task generation completed.', complete: 'Future-task generation completed.',
    failed: 'Generation needs attention.', blocked: 'Generation is held.'};
  const generationText = generationLabels[generation.state] || (state.data?.future ? 'Future-task record is up to date.' : 'Future-task generation is not available yet.');
  $('generationStatus').textContent = [generationText, generation.model ? `Model: ${generation.model}` : '',
    generation.requested_at ? `Requested ${fullDate(generation.requested_at)}` : '', value(generation.error)].filter(Boolean).join(' · ');
  $('futureSummary').textContent = `${visible.length} shown · ${matching.length} match · ${activeCount} active · ${entries.length} retained in this snapshot. ${next.size} ready or queued candidates for the next batch.`;
  const list = $('futureList');
  const scroll = list.scrollTop;
  const openIds = new Set(Array.from(list.querySelectorAll('details[open]')).map((row) => row.dataset.futureId));
  const focusedId = document.activeElement?.dataset?.futureId;
  const fragment = document.createDocumentFragment();
  for (const task of visible) {
    const row = node('details', 'future-task');
    row.dataset.futureId = String(task.id); row.open = openIds.has(String(task.id));
    const summary = node('summary', 'future-task-heading'); summary.dataset.futureId = String(task.id);
    const title = node('span', 'future-task-title', value(task.title, 'Untitled task'));
    title.append(node('small', '', `${value(task.id)} · ${value(task.project, 'Project')} · P${priority(task)}`));
    const badges = node('span', 'future-badges');
    badges.append(node('span', 'stage-pill', labels[task.state] || value(task.state, 'Status unavailable')));
    if (next.has(task.id)) badges.append(node('span', 'next-badge', 'Next batch candidate'));
    summary.append(title, badges); row.append(summary);
    const body = node('div', 'future-task-body');
    body.append(node('p', 'prompt-text', value(task.prompt, 'Instructions are not recorded yet.')));
    if (task.state === 'needs_scope' && !task.scope_id && task.reason === 'Scope suggestion is not registered')
      body.append(node('p', 'future-reason', 'Planned proposal. A bounded coding scope and isolated tests must be registered before it can start.'));
    else if (task.reason) body.append(node('p', 'future-reason', value(task.reason)));
    body.append(node('p', 'field-help', `Created ${fullDate(task.created_at)}`));
    if (task.not_before) body.append(node('p', 'field-help', `Scheduled no earlier than ${fullDate(task.not_before)}`));
    if (task.scope_id) body.append(node('p', 'field-help', `Scope: ${task.scope_id}`));
    row.append(body); fragment.append(row);
  }
  if (!visible.length) fragment.append(node('p', 'future-empty', entries.length ? 'No future tasks match these filters.'
    : 'No future tasks are listed yet. Generate a batch or add a task with your own instructions.'));
  list.replaceChildren(fragment); list.scrollTop = scroll;
  if (focusedId) Array.from(list.querySelectorAll('summary')).find((row) => row.dataset.futureId === focusedId)?.focus({preventScroll: true});
}
function filteredTasks() {
  const needle = $('search').value.trim().toLowerCase();
  const project = $('projectFilter').value;
  const stage = $('stageFilter').value;
  return tasks().filter((task) => (project === 'all' || task.project === project)
    && stageMatches(stageOf(task), stage)
    && (!needle || [task.id, task.title, task.project, task.owner, task.coder_model, task.reviewer_model]
      .some((field) => typeof field === 'string' && field.toLowerCase().includes(needle))))
    .sort((a, b) => priority(b) - priority(a) || (parsedDate(b.updated_at)?.getTime() || 0) - (parsedDate(a.updated_at)?.getTime() || 0));
}
function taskCard(task) {
  const card = node('button', 'task-card');
  card.type = 'button'; card.dataset.taskId = task.id;
  card.setAttribute('aria-label', `${value(task.id)}: ${value(task.title, 'Untitled task')}. ${STAGE_TITLES[stageOf(task)]}. Open details.`);
  const top = node('div', 'task-card-top');
  top.append(node('span', `project-pill${task.project === 'GatewayAI' ? ' gateway' : ''}`, value(task.project, 'Project')),
    node('span', `priority-tag${priority(task) > 3 ? ' high' : ''}`, `${priority(task) > 3 ? '↑' : '≡'} P${priority(task)}`));
  card.append(top, node('h3', '', value(task.title, 'Untitled task')), node('span', 'task-id', value(task.id)));
  const owner = node('div', 'task-owner');
  owner.append(node('span', 'owner-avatar', task.owner ? ownerName(task.owner).slice(0, 1).toUpperCase() : '·'),
    node('span', 'task-owner-name', ownerName(task.owner)));
  if (isPaused(task)) owner.append(node('span', 'paused-pill', task.execution ? 'Pause next' : 'Paused'));
  const scores = node('div', 'card-confidence');
  for (const [label, score] of [['Coder', task.coder_confidence], ['Reviewer', task.reviewer_confidence]]) {
    const part = node('span', '', `${label} `); part.append(node('strong', '', confidence(score))); scores.append(part);
  }
  const bottom = node('div', 'task-bottom');
  bottom.append(node('span', githubLink(task.pr_url) ? 'task-pr-label' : '', githubLink(task.pr_url)
    ? `PR ${Number.isInteger(task.pr_number) ? '#'+task.pr_number : 'available'} ↗` : statusHint(task)));
  const time = node('time', '', relativeDate(task.updated_at || task.created_at));
  time.title = fullDate(task.updated_at || task.created_at); bottom.append(time);
  card.append(owner, node('div', 'card-divider'), scores, bottom);
  if (task.execution) {
    const activity = node('div', 'task-state-hint execution-hint', `${statusHint(task)}\n${value(task.execution.host)}`);
    card.insertBefore(activity, scores);
  }
  card.addEventListener('click', () => openTask(task.id));
  return card;
}
function renderBoard() {
  const visible = filteredTasks();
  const stage = $('stageFilter').value;
  const board = $('taskBoard');
  const scroll = board.scrollLeft; const scrollTop = board.scrollTop;
  const focusedTask = document.activeElement?.dataset?.taskId;
  const fragment = document.createDocumentFragment();
  for (const [key, title, emptyText] of STAGES) {
    if (!stageMatches(key, stage)) continue;
    const column = node('section', `stage-column stage-${key}`);
    const entries = visible.filter((task) => stageOf(task) === key);
    const heading = node('h3', 'stage-heading', title);
    heading.append(node('span', 'stage-count', entries.length)); column.append(heading);
    if (entries.length) entries.forEach((task) => column.append(taskCard(task)));
    else column.append(node('p', 'column-empty', emptyText));
    fragment.append(column);
  }
  board.replaceChildren(fragment); board.scrollLeft = scroll; board.scrollTop = scrollTop;
  if (focusedTask) Array.from(board.querySelectorAll('[data-task-id]')).find((button) => button.dataset.taskId === focusedTask)?.focus({preventScroll: true});
  const filtering = Boolean($('search').value.trim() || $('projectFilter').value !== 'all' || stage !== 'all');
  $('clearFilters').hidden = !filtering;
  $('emptyResults').hidden = visible.length > 0 || !filtering;
  board.hidden = visible.length === 0 && filtering;
  $('filterCount').textContent = filtering ? `${visible.length} of ${tasks().length} tasks` : `${tasks().length} task${tasks().length === 1 ? '' : 's'} across your workspace`;
  $('totalTasks').textContent = tasks().length; $('navCount').textContent = tasks().length;
  const grouped = tasks().map(stageOf);
  $('metricWorking').textContent = grouped.filter((entry) => entry === 'working').length;
  $('metricReview').textContent = grouped.filter((entry) => entry === 'review').length;
  $('metricBlocked').textContent = grouped.filter((entry) => entry === 'blocked' || entry === 'changes').length;
  $('metricDone').textContent = grouped.filter((entry) => entry === 'reviewed' || entry === 'merged').length;
}
function eventText(event) {
  if (typeof event === 'string') return event;
  const supplied = value(event.summary, value(event.message, value(event.text)));
  if (supplied) return supplied;
  if (event.action === 'transition') {
    const target = value(event.detail).split(' -> ')[1]?.split(';')[0]?.trim();
    return target ? statusHint({state: target}) : 'Task progress updated';
  }
  const labels = {registered: 'Task added to the work board', pause: 'Work paused', resume: 'Work resumed within its existing scope',
    digest_due: 'An hourly progress update is ready', mark_reviewed: 'Review recorded', add_task: 'New request added to the backlog'};
  return labels[event.action] || value(event.detail, value(event.action, 'Task record updated'));
}
function eventsFor(task = null) {
  const events = Array.isArray(state.data?.events) ? state.data.events : [];
  return events.filter((event) => event && (typeof event === 'object' || typeof event === 'string')).filter((event) => !task || (typeof event === 'object' && event !== null
    && (event.task_id === task.id || event.task_id === task.key || event.task_key === task.key || event.id === task.id)))
    .sort((a, b) => (parsedDate(b.timestamp || b.at || b.created_at)?.getTime() || 0) - (parsedDate(a.timestamp || a.at || a.created_at)?.getTime() || 0));
}
function renderActivity(target, events, emptyText, maximum = 6) {
  const fragment = document.createDocumentFragment();
  for (const event of events.slice(0, maximum)) {
    const row = node('li', 'activity-item');
    const content = node('div', 'activity-content', eventText(event));
    const provenance = [value(event.actor), value(event.task_id)].filter(Boolean).join(' · ');
    if (provenance) content.append(node('strong', '', provenance));
    const stamp = event.timestamp || event.at || event.created_at;
    const time = node('time', '', relativeDate(stamp)); time.title = fullDate(stamp);
    if (parsedDate(stamp)) time.dateTime = parsedDate(stamp).toISOString();
    row.append(node('span', 'activity-marker'), content, time); fragment.append(row);
  }
  if (!events.length) fragment.append(node('li', 'muted small', emptyText));
  target.replaceChildren(fragment);
}
function openTask(id) {
  const task = tasks().find((entry) => entry.id === id);
  if (!task) { announce('This task is no longer in the current list. Refresh to check.', 'error'); return; }
  if (state.selectedId !== id) {
    if (state.selectedId) state.drafts.set(state.selectedId, {review: $('reviewNote').value, question: $('question').value,
      priority: $('detailPriority').value, priorityDirty: state.priorityDirty});
    const draft = state.drafts.get(id);
    $('reviewNote').value = draft?.review || ''; $('question').value = draft?.question || '';
    state.priorityDirty = draft?.priorityDirty || false;
    if (state.priorityDirty) $('detailPriority').value = draft.priority;
  }
  state.selectedId = id;
  renderDetail();
  if (!$('taskDialog').open) $('taskDialog').showModal();
}
function renderDetail() {
  const task = currentTask();
  if (!task) {
    if ($('taskDialog').open) {
      $('detailError').textContent = 'This task is no longer in the current list. Your notes have been kept.';
      $('detailError').hidden = false;
      $('taskDialog').querySelectorAll('[data-write]').forEach((button) => { button.disabled = true; });
    }
    return;
  }
  $('detailId').textContent = value(task.id);
  $('detailTitle').textContent = value(task.title, 'Untitled task');
  $('detailProject').textContent = value(task.project, 'Project');
  $('detailProject').classList.toggle('gateway', task.project === 'GatewayAI');
  $('detailStage').textContent = STAGE_TITLES[stageOf(task)];
  $('detailPaused').hidden = !isPaused(task);
  $('detailPaused').textContent = task.execution ? 'Pause after this step' : 'Paused';
  const meta = [`Created ${fullDate(task.created_at)}`, `Updated ${fullDate(task.updated_at)}`];
  if (Number.isInteger(task.attempt) && task.attempt > 0) meta.push(`Attempt ${task.attempt + 1}`);
  $('detailMeta').textContent = meta.join(' · ');
  $('detailExecution').hidden = !task.execution && !task.wait_reason;
  if (task.execution) {
    const execution = task.execution;
    $('detailExecutionTitle').textContent = statusHint(task);
    const details = [value(execution.host)];
    if (execution.started_at) details.push(`Started ${fullDate(execution.started_at)}`);
    if (execution.model_status === 'not_yet_reported') details.push('Current model: not yet reported. The model is recorded when this step completes.');
    else if (execution.model) details.push(`Current model: ${execution.model}`);
    $('detailExecutionText').textContent = details.filter(Boolean).join('\n');
  } else {
    $('detailExecutionTitle').textContent = 'Waiting for the cloud-work budget';
    $('detailExecutionText').textContent = value(task.wait_reason);
  }
  const pr = githubLink(task.pr_url);
  $('detailPr').hidden = !pr;
  if (pr) { $('detailPr').href = pr; $('detailPr').textContent = `Open pull request${Number.isInteger(task.pr_number) ? ' #'+task.pr_number : ''} ↗`; }
  else $('detailPr').removeAttribute('href');
  $('detailCoder').textContent = modelName(task.coder_model, ownerName(task.owner));
  $('detailReviewer').textContent = modelName(task.reviewer_model);
  $('detailCoderConfidence').textContent = `Confidence: ${confidence(task.coder_confidence)}`;
  $('detailReviewerConfidence').textContent = `Confidence: ${confidence(task.reviewer_confidence)}`;
  $('confidenceReason').textContent = value(task.confidence_reason);
  $('confidenceReason').hidden = !value(task.confidence_reason);
  $('detailPrompt').textContent = value(task.prompt, 'No instructions have been recorded for this task yet.');
  $('detailTests').hidden = typeof task.tests_passed !== 'boolean';
  const count = Number.isInteger(task.test_count) && task.test_count >= 0 ? task.test_count : null;
  $('detailTestsText').textContent = task.tests_passed === true
    ? count !== null ? `${count} isolated test${count === 1 ? '' : 's'} passed.` : 'Isolated checks passed. The test count was not recorded.'
    : count !== null ? `The recorded checks did not pass (${count} test${count === 1 ? '' : 's'}).` : 'The recorded checks did not pass.';
  $('savedReview').hidden = !value(task.review_note);
  $('savedReviewText').textContent = value(task.review_note);
  $('savedReviewDate').textContent = task.reviewed_at ? `Recorded ${fullDate(task.reviewed_at)}` : '';
  $('detailError').textContent = value(task.error);
  $('detailError').hidden = !value(task.error);
  if (!state.priorityDirty && document.activeElement !== $('detailPriority')) $('detailPriority').value = String(priority(task));
  const paused = isPaused(task);
  $('taskToggle').textContent = paused ? 'Resume task' : 'Pause task';
  $('taskPauseHelp').textContent = paused ? task.execution ? 'This step already owns its work. The pause takes effect before the next step.' : 'This task is paused. Resume when you are ready.' : 'Pause this task while you decide what comes next.';
  renderActivity($('detailActivity'), eventsFor(task), 'No separate activity has been recorded for this task yet.', 12);
  syncControls();
}
function acceptState(data) {
  if (!data || typeof data !== 'object' || !Array.isArray(data.tasks) || data.revision === undefined
      || typeof data.csrf_token !== 'string') throw new Error('The task service returned an incomplete view.');
  state.data = data; state.connected = true; state.lastUpdated = new Date();
  $('connectionDot').classList.remove('offline'); $('connectionLabel').textContent = 'Connected';
  $('connectionError').hidden = true;
  $('lastUpdated').textContent = `Updated ${new Intl.DateTimeFormat(undefined, {hour: 'numeric', minute: '2-digit'}).format(state.lastUpdated)}`;
  renderBoard(); renderFuture(); renderActivity($('activityList'), eventsFor(), 'No recent activity. New updates will appear here.');
  syncControls(); renderDetail();
}
async function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {...options, credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(value(data.message, value(data.error, response.status === 409 ? 'The task changed. Refresh and review its latest state.' : 'The task service could not complete that request.')));
      error.confirmed = true; throw error;
    }
    return data;
  } finally { clearTimeout(timeout); }
}
async function refresh(announceRefresh = false) {
  if (state.loading || state.posting) return;
  state.loading = true; syncControls();
  const toast = announceRefresh ? announce('Refresh received. Checking your latest tasks…') : null;
  try {
    acceptState(await request('/api/state'));
    if (toast) announce('Up to date. Your latest tasks are shown.', 'success', toast);
  } catch (error) {
    state.connected = false;
    $('connectionDot').classList.add('offline'); $('connectionLabel').textContent = 'Connection interrupted';
    const message = state.data ? 'Could not refresh the task service. Your last view is still shown; controls will return when the connection is restored.' : 'Could not reach the task service. Check your internal network connection, then select Refresh.';
    $('connectionError').textContent = message; $('connectionError').hidden = false;
    if (toast) announce(message, 'error', toast);
    if (!state.data) $('taskBoard').replaceChildren(node('div', 'loading-state', 'Waiting for the task service. No tasks have been loaded yet.'));
  } finally { state.loading = false; syncControls(); }
}
async function control(action, fields = {}, button = null) {
  if (state.posting) { announce('Your previous action is still being saved. Please wait for its confirmation.', 'error'); return false; }
  if (!state.connected || !state.data?.csrf_token) { announce('Reconnect to the task service before making a change. Select Refresh to check.', 'error'); return false; }
  const labels = {pause: 'Pause request received', resume: 'Resume request received', priority: 'Priority change received',
    request_changes: 'Change request received', mark_reviewed: 'Review note received', add_task: 'New task received', ask: 'Question received',
    generate_future: 'Click received: future-task generation requested', override_start: 'Click received: resume scheduling requested'};
  const toast = announce(`${labels[action] || 'Request received'}. Saving…`);
  state.posting = true; syncControls();
  const oldLabel = button?.textContent;
  if (button) { button.textContent = 'Saving…'; button.setAttribute('aria-busy', 'true'); }
  const signature = JSON.stringify({action, ...fields});
  let payload = state.uncertain.get(signature);
  if (!payload) {
    // Reuse this exact ID after an uncertain delivery instead of creating a
    // second task or question when the owner explicitly retries the same action.
    payload = {request_id: randomId(), revision: state.data.revision, action, ...fields};
  }
  let success = false;
  try {
    const result = await request('/api/control', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': state.data.csrf_token}, body: JSON.stringify(payload)});
    if (result.ok !== true) { const error = new Error(value(result.message, 'The request was not accepted.')); error.confirmed = true; throw error; }
    state.uncertain.delete(signature);
    if (result.state && Array.isArray(result.state.tasks) && typeof result.state.csrf_token === 'string') acceptState(result.state);
    const fallbackMessage = action === 'generate_future' ? 'Request saved. Generation runs in the background; watch Future tasks for progress.'
      : action === 'override_start' ? 'Scheduling resume acknowledged. Blocked claims, scope checks, tests and budgets remain in force.'
      : action === 'ask' ? 'Question saved. Watch the task activity for the response.' : 'Saved. Your request has been acknowledged.';
    announce(value(result.message, fallbackMessage), 'success', toast);
    success = true;
  } catch (error) {
    if (error.confirmed) state.uncertain.delete(signature);
    else state.uncertain.set(signature, payload);
    announce(error.confirmed ? error.message : 'Delivery could not be confirmed. Your input is kept. Refresh to check before retrying; the same request will not be sent as a new action.', 'error', toast);
  } finally {
    state.posting = false;
    if (button) { button.textContent = oldLabel; button.removeAttribute('aria-busy'); }
    syncControls();
    await refresh();
  }
  return success;
}
function randomId() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Internal HTTP hosts are not secure contexts in every browser. Keep IDs
  // cryptographically random without requiring a package or falling to Math.random.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
function resetFilters() {
  $('search').value = ''; $('projectFilter').value = 'all'; $('stageFilter').value = 'all';
  renderBoard(); $('taskBoard').scrollLeft = 0;
}
function taskAction(action, fields, button) {
  const task = currentTask();
  if (!task) { announce('The task is no longer available. Refresh the task list.', 'error'); return Promise.resolve(false); }
  return control(action, {task_id: task.id, ...fields}, button);
}

$('refresh').addEventListener('click', () => refresh(true));
$('globalToggle').addEventListener('click', (event) => control(state.data?.enabled ? 'pause' : 'resume', {}, event.currentTarget));
$('generateFuture').addEventListener('click', (event) => control('generate_future', {}, event.currentTarget));
$('overrideStart').addEventListener('click', (event) => control('override_start', {}, event.currentTarget));
for (const id of ['futureSearch', 'futureFilter']) $(id).addEventListener(id === 'futureSearch' ? 'input' : 'change', () => {
  renderFuture(); $('futureList').scrollTop = 0;
});
$('openAdd').addEventListener('click', () => { $('addDialog').showModal(); $('newTitle').focus(); });
$('openGuides').addEventListener('click', () => $('guidesDialog').showModal());
document.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => $(button.dataset.close).close()));
document.querySelectorAll('dialog').forEach((dialog) => dialog.addEventListener('close', () => {
  const region = dialog.querySelector('.dialog-announcements');
  if (region) { while (region.firstChild) $('announcements').append(region.firstChild); region.remove(); }
}));
document.querySelectorAll('.document-list a').forEach((link) => link.addEventListener('click', () => announce('Download requested. Your browser will open or save the task record.', 'success')));
for (const id of ['search', 'projectFilter', 'stageFilter']) $(id).addEventListener(id === 'search' ? 'input' : 'change', () => { if (state.data) { renderBoard(); $('taskBoard').scrollLeft = 0; } });
$('clearFilters').addEventListener('click', resetFilters); $('emptyClear').addEventListener('click', resetFilters);
document.querySelectorAll('[data-summary]').forEach((button) => button.addEventListener('click', () => {
  const selected = button.dataset.summary;
  $('stageFilter').value = selected === 'blocked' ? 'attention' : selected;
  if (state.data) renderBoard();
  $('board').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
}));
$('detailPriority').addEventListener('change', () => { state.priorityDirty = true; });
$('savePriority').addEventListener('click', async (event) => {
  const saved = await taskAction('priority', {priority: Number($('detailPriority').value)}, event.currentTarget);
  if (saved) { state.priorityDirty = false; renderDetail(); }
});
$('taskToggle').addEventListener('click', (event) => {
  const task = currentTask(); if (task) taskAction(isPaused(task) ? 'resume' : 'pause', {}, event.currentTarget);
});
for (const [id, action] of [['requestChanges', 'request_changes'], ['markReviewed', 'mark_reviewed']]) {
  $(id).addEventListener('click', async (event) => {
    const text = $('reviewNote').value.trim();
    if (!text) { announce('Add a short note so the supervisor knows what you decided.', 'error'); $('reviewNote').focus(); return; }
    if (await taskAction(action, {text}, event.currentTarget)) $('reviewNote').value = '';
  });
}
$('askForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!$('askForm').reportValidity()) return;
  const text = $('question').value.trim();
  if (!text) { $('question').focus(); return; }
  if (await taskAction('ask', {text}, event.submitter || $('askForm').querySelector('button'))) $('question').value = '';
});
$('addForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!$('addForm').reportValidity()) return;
  const title = $('newTitle').value.trim(); const text = $('newText').value.trim();
  if (!title || !text) { announce('Add a title and instructions before sending this task.', 'error'); return; }
  if (await control('add_task', {project: $('newProject').value, title, text}, event.submitter || $('addForm').querySelector('[type="submit"]'))) {
    $('addForm').reset(); $('addDialog').close();
  }
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
setInterval(() => { if (!document.hidden) refresh(); }, 15000);
syncControls();
refresh();
