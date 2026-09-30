// Run with: node tests/segment_ui_smoke.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'dashboard', 'saas.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(source, 'Dashboard script is present');
new vm.Script(source);
const legacyHtml = fs.readFileSync(path.join(__dirname, '..', 'dashboard', 'index.html'), 'utf8');
for (const match of legacyHtml.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)) {
  if (match[1].trim()) new vm.Script(match[1]);
}

const format = source.split('\n').find(line => line.startsWith('function formatDuration'));
const convert = source.split('\n').find(line => line.startsWith('function serviceDurationMinutes'));
assert.ok(format && convert, 'Duration helpers are present');

const context = {
  $: id => ({value: id === 'service-duration' ? '1.5' : 'hours'}),
};
vm.createContext(context);
vm.runInContext(`${format};${convert}`, context);
assert.equal(context.serviceDurationMinutes(), 90);
assert.equal(context.formatDuration(30), '30 min');
assert.equal(context.formatDuration(90), '1h 30min');
assert.equal(context.formatDuration(120), '2h');
assert.equal(context.formatDuration(65), '65 min');

const applySegment = source.match(/function applySegmentConfig\(\) \{[\s\S]*?\n\}/)?.[0];
assert.ok(applySegment, 'Segment navigation renderer is present');
const elements = new Map();
const nav = {
  items: [],
  replaceChildren(...items) { this.items = items; },
  querySelector(selector) { return this.items.find(item => selector.includes(item.dataset.tab)); },
};
const field = id => {
  if (id === 'main-nav') return nav;
  if (!elements.has(id)) elements.set(id, {});
  return elements.get(id);
};
const ui = {
  $: field,
  editingCustomer: false,
  editingService: false,
  editingProfessional: false,
  editingAppointment: false,
  renderExtraFields() {},
  document: {
    documentElement: {style: {setProperty() {}}},
    querySelector: () => ({id: 'overview'}),
    createElement: tag => ({tag, dataset: {}, children: [], classList: {add() {}}, setAttribute() {}, append(...items) { this.children.push(...items); }}),
  },
  window: {},
  segmentConfig: {
    name: 'Lava-rápido', theme: {accent: '#123456'},
    labels: {customer: 'Cliente', customers: 'Clientes', service: 'Serviço', services: 'Serviços',
      professional: 'Profissional', professionals: 'Equipe', appointment: 'Lavagem'},
    onboarding: {title: 'Prepare o negócio', customer_hint: 'Clientes', service_hint: 'Serviços'},
    modules: ['vehicles'], business_type: 'CAR_WASH',
    navigation: [{id: 'overview', label: 'Dashboard', icon: 'house', enabled: true},
      {id: 'vehicles', label: 'Veículos', icon: 'car', enabled: true}],
  },
};
vm.createContext(ui);
vm.runInContext(`${applySegment};applySegmentConfig()`, ui);
assert.deepEqual(nav.items.filter(item => item.dataset.tab).map(item => item.dataset.tab), ['overview', 'vehicles']);
assert.deepEqual(nav.items.filter(item => item.className === 'nav-group-label').map(item => item.textContent), ['Visão geral e agenda', 'Gestão']);
assert.equal(field('appointment-vehicle').required, true);
assert.equal(field('appointment-pet-field').hidden, true);
ui.segmentConfig = {...ui.segmentConfig, name: 'Serviços pet', modules: ['pets'], business_type: 'PET',
  navigation: [{id: 'overview', label: 'Dashboard', icon: 'house', enabled: true},
    {id: 'pets', label: 'Pets', icon: 'paw-print', enabled: true}]};
vm.runInContext('applySegmentConfig()', ui);
assert.deepEqual(nav.items.filter(item => item.dataset.tab).map(item => item.dataset.tab), ['overview', 'pets']);
assert.equal(field('appointment-pet').required, true);
assert.equal(field('appointment-vehicle-field').hidden, true);
console.log('Segment UI smoke checks passed');
