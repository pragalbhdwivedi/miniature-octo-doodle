'use strict';
const root = document.querySelector('#services');
const search = document.querySelector('#search');
let services = [];
function text(tag, value, className) {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
}
function safeURL(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url : null;
  } catch { return null; }
}
function render() {
  const query = search.value.trim().toLowerCase();
  const filtered = services.filter(s => [s.name, s.description, s.group].join(' ').toLowerCase().includes(query));
  root.replaceChildren();
  const groups = new Map();
  for (const service of filtered) {
    const group = service.group || 'Services';
    if (!groups.has(group)) {
      const section = text('section', '', 'group');
      section.append(text('h2', group));
      const grid = text('div', '', 'grid');
      section.append(grid); root.append(section); groups.set(group, grid);
    }
    const url = safeURL(service.url);
    const card = text(url ? 'a' : 'article', '', 'card' + (url ? '' : ' disabled'));
    if (url) { card.href = url.href; card.target = '_blank'; card.rel = 'noopener noreferrer'; }
    const top = text('div', '', 'card-top');
    top.append(text('span', service.symbol || service.name.slice(0, 2), 'icon'), text('span', url ? '↗' : '—', 'arrow'));
    const body = text('div', ''); body.append(text('h3', service.name), text('p', service.description || ''));
    const bottom = text('div', '', 'card-bottom');
    bottom.append(text('span', url ? url.host : 'Not published', 'address'), text('span', service.status || 'Open service', service.attention ? 'pending' : 'status'));
    card.append(top, body, bottom); groups.get(group).append(card);
  }
  document.querySelector('#count').textContent = `${filtered.length} service${filtered.length === 1 ? '' : 's'}`;
  document.querySelector('#empty').hidden = filtered.length !== 0;
}
search.addEventListener('input', render);
document.addEventListener('keydown', event => {
  if (event.key === '/' && document.activeElement !== search && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault(); search.focus();
  }
});
fetch('/services.json', {cache: 'no-store'}).then(response => {
  if (!response.ok) throw new Error('Directory unavailable');
  return response.json();
}).then(data => {
  if (!Array.isArray(data.services)) throw new Error('Invalid directory');
  services = data.services.filter(s => s && typeof s.name === 'string'); render();
}).catch(() => { root.replaceChildren(text('p', 'The service directory could not be loaded. Please refresh or contact your administrator.')); });
